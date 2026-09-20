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

  identifier                 = "medconnect-${local.environment}-db"
  environment                = local.environment
  instance_class             = var.rds_instance_class
  allocated_storage          = var.rds_allocated_storage
  max_allocated_storage      = var.rds_max_allocated_storage
  multi_az                   = true
  deletion_protection        = true
  skip_final_snapshot        = false
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
    REDIS_URL = "redis://:${urlencode(random_password.redis_auth.result)}@${module.elasticache.primary_endpoint}:${module.elasticache.port}/0"
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
