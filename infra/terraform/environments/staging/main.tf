data "aws_caller_identity" "current" {}

data "terraform_remote_state" "shared" {
  backend = "s3"
  config = {
    bucket = "medconnect-terraform-state"
    key    = "shared/terraform.tfstate"
    region = "ap-south-1"
  }
}

locals {
  environment = "staging"
  db_username = "medconnect_admin"
}

# ---------------------------------------------------------------------------
# Generated credentials. random_password is stable across applies (no
# `keepers`), so this only ever generates once per environment; the RDS and
# ElastiCache modules themselves ignore_changes on their password/auth_token
# fields so that a future manual rotation isn't clobbered by Terraform.
# ---------------------------------------------------------------------------

resource "random_password" "rds_master" {
  length  = 32
  special = false
}

resource "random_password" "redis_auth" {
  length  = 32
  special = false
}

resource "random_password" "keycloak_admin" {
  length  = 24
  special = false
}

# ---------------------------------------------------------------------------
# Data stores — one RDS instance hosting both the medconnect and
# medconnect_medicines logical databases (Keycloak's `keycloak` schema lives
# inside medconnect) plus one ElastiCache replication group.
# ---------------------------------------------------------------------------

module "rds" {
  source = "../../modules/rds"

  identifier                 = "medconnect-${local.environment}-db"
  environment                = local.environment
  instance_class             = var.rds_instance_class
  allocated_storage          = var.rds_allocated_storage
  max_allocated_storage      = var.rds_max_allocated_storage
  multi_az                   = false
  deletion_protection        = false
  skip_final_snapshot        = true
  master_username            = local.db_username
  master_password            = random_password.rds_master.result
  vpc_id                     = data.terraform_remote_state.shared.outputs.vpc_id
  subnet_ids                 = data.terraform_remote_state.shared.outputs.private_subnet_ids
  allowed_security_group_ids = [data.terraform_remote_state.shared.outputs.cluster_security_group_id]
  tags                       = var.tags
}

module "elasticache" {
  source = "../../modules/elasticache"

  replication_group_id       = "medconnect-${local.environment}-redis"
  environment                = local.environment
  node_type                  = var.redis_node_type
  num_cache_nodes            = var.redis_num_cache_nodes
  auth_token                 = random_password.redis_auth.result
  vpc_id                     = data.terraform_remote_state.shared.outputs.vpc_id
  subnet_ids                 = data.terraform_remote_state.shared.outputs.private_subnet_ids
  allowed_security_group_ids = [data.terraform_remote_state.shared.outputs.cluster_security_group_id]
  tags                       = var.tags
}

module "s3" {
  source = "../../modules/s3"

  environment = local.environment
  account_id  = data.aws_caller_identity.current.account_id
  tags        = var.tags
}

module "waf" {
  source = "../../modules/waf"

  name        = "medconnect-${local.environment}"
  environment = local.environment
  tags        = var.tags
}

# ---------------------------------------------------------------------------
# Secrets Manager — JSON key names match what each k8s ExternalSecret's
# dataFrom.extract expects (infra/k8s/base/external-secrets/*.yaml) and what
# the app's own Settings class reads (backend/app/config.py).
# ---------------------------------------------------------------------------

locals {
  rds_secret = {
    DATABASE_URL         = "postgresql+asyncpg://${local.db_username}:${urlencode(random_password.rds_master.result)}@${module.rds.endpoint}:${module.rds.port}/medconnect"
    DATABASE_URL_SYNC    = "postgresql://${local.db_username}:${urlencode(random_password.rds_master.result)}@${module.rds.endpoint}:${module.rds.port}/medconnect"
    MEDICINE_DB_URL      = "postgresql+asyncpg://${local.db_username}:${urlencode(random_password.rds_master.result)}@${module.rds.endpoint}:${module.rds.port}/medconnect_medicines"
    MEDICINE_DB_URL_SYNC = "postgresql://${local.db_username}:${urlencode(random_password.rds_master.result)}@${module.rds.endpoint}:${module.rds.port}/medconnect_medicines"
    SENTRY_DSN           = var.sentry_dsn

    # Keycloak reads these three directly (KC_DB_URL/KC_DB_USERNAME/
    # KC_DB_PASSWORD), not DATABASE_URL — its JDBC URL has no credentials
    # embedded and always points at the `medconnect` database, since
    # KC_DB_SCHEMA=keycloak (keycloak/deployment.yaml) puts it in a schema
    # inside that same logical database, not a separate one.
    KC_DB_URL      = "jdbc:postgresql://${module.rds.endpoint}:${module.rds.port}/medconnect"
    KC_DB_USERNAME = local.db_username
    KC_DB_PASSWORD = random_password.rds_master.result
  }

  redis_secret = {
    # rediss:// (TLS) — the elasticache module sets transit_encryption_enabled=true,
    # so a plain redis:// client would be refused at the transport level.
    # `?ssl_cert_reqs=none` is required: ElastiCache's TLS cert is signed by an
    # AWS-internal CA absent from the container trust store, so default cert
    # verification fails. redis.asyncio.from_url (rate limiter, health check)
    # honours the param; TLS stays on, only CA verification is relaxed.
    #
    # KNOWN GAP: arq's RedisSettings.from_dsn (arq==0.26.1,
    # backend/app/workers/reminder_worker.py) ignores every query param except
    # `db`, so the reminder worker still verifies the cert and will fail to
    # connect until the app passes ssl_cert_reqs='none' explicitly (or mounts
    # the ElastiCache CA bundle). App-code follow-up — out of infra scope.
    REDIS_URL = "rediss://:${urlencode(random_password.redis_auth.result)}@${module.elasticache.primary_endpoint}:${module.elasticache.port}/0?ssl_cert_reqs=none"
  }

  # KEYCLOAK_ADMIN is read by the Keycloak container itself (bootstrap admin
  # user); KEYCLOAK_ADMIN_USER/KEYCLOAK_ADMIN_PASSWORD are read by the backend
  # (app/config.py) so it can call Keycloak's admin REST API as that same user.
  keycloak_admin_secret = {
    KEYCLOAK_ADMIN          = var.keycloak_admin_username
    KEYCLOAK_ADMIN_USER     = var.keycloak_admin_username
    KEYCLOAK_ADMIN_PASSWORD = random_password.keycloak_admin.result
  }
}

module "secrets" {
  source = "../../modules/secrets"

  environment             = local.environment
  recovery_window_in_days = 0 # staging gets torn down/recreated; skip the recovery window
  secrets = {
    rds              = local.rds_secret
    redis            = local.redis_secret
    "keycloak-admin" = local.keycloak_admin_secret
  }
  tags = var.tags
}
