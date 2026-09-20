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
  environment = "prod"
  db_username = "medconnect_admin"
}

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

module "rds" {
  source = "../../modules/rds"

  identifier              = "medconnect-${local.environment}-db"
  environment             = local.environment
  instance_class          = var.rds_instance_class
  allocated_storage       = var.rds_allocated_storage
  max_allocated_storage   = var.rds_max_allocated_storage
  multi_az                = true
  deletion_protection     = true
  skip_final_snapshot     = false
  backup_retention_period = 30
  # UTC; 20:00-21:00 UTC ≈ 01:30-02:30 IST — the lowest-traffic hour for an
  # India-facing app. Staging leaves this null (AWS picks).
  backup_window              = "20:00-21:00"
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

locals {
  rds_secret = {
    DATABASE_URL         = "postgresql+asyncpg://${local.db_username}:${urlencode(random_password.rds_master.result)}@${module.rds.endpoint}:${module.rds.port}/medconnect"
    DATABASE_URL_SYNC    = "postgresql://${local.db_username}:${urlencode(random_password.rds_master.result)}@${module.rds.endpoint}:${module.rds.port}/medconnect"
    MEDICINE_DB_URL      = "postgresql+asyncpg://${local.db_username}:${urlencode(random_password.rds_master.result)}@${module.rds.endpoint}:${module.rds.port}/medconnect_medicines"
    MEDICINE_DB_URL_SYNC = "postgresql://${local.db_username}:${urlencode(random_password.rds_master.result)}@${module.rds.endpoint}:${module.rds.port}/medconnect_medicines"
    SENTRY_DSN           = var.sentry_dsn

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

  keycloak_admin_secret = {
    KEYCLOAK_ADMIN          = var.keycloak_admin_username
    KEYCLOAK_ADMIN_USER     = var.keycloak_admin_username
    KEYCLOAK_ADMIN_PASSWORD = random_password.keycloak_admin.result
  }
}

module "secrets" {
  source = "../../modules/secrets"

  environment = local.environment
  secrets = {
    rds              = local.rds_secret
    redis            = local.redis_secret
    "keycloak-admin" = local.keycloak_admin_secret
  }
  tags = var.tags
}
