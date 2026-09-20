locals {
  tags = merge(
    {
      Project     = "medconnect"
      Environment = var.environment
    },
    var.tags,
  )
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.identifier}-subnets"
  subnet_ids = var.subnet_ids
  tags       = local.tags
}

resource "aws_security_group" "this" {
  name        = "${var.identifier}-sg"
  description = "Postgres access for ${var.identifier}"
  vpc_id      = var.vpc_id
  tags        = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "sg" {
  count                        = length(var.allowed_security_group_ids)
  security_group_id            = aws_security_group.this.id
  referenced_security_group_id = var.allowed_security_group_ids[count.index]
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "cidr" {
  count             = length(var.allowed_cidr_blocks)
  security_group_id = aws_security_group.this.id
  cidr_ipv4         = var.allowed_cidr_blocks[count.index]
  from_port         = 5432
  to_port           = 5432
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.this.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

# Postgres 16 family. pgvector ships in the RDS-managed extension set for
# Postgres >= 15 and is enabled per-database with `CREATE EXTENSION vector`,
# so no shared_preload_libraries change is required — this group exists to
# hold that extension allowlist and any future tuning explicitly, rather than
# relying on the default parameter group.
resource "aws_db_parameter_group" "this" {
  name   = "${var.identifier}-pg16"
  family = "postgres16"
  tags   = local.tags

  # force_ssl=1 makes the server reject non-TLS connections outright. Every
  # client here defaults to SSL anyway — libpq/psycopg2 (alembic, db-bootstrap
  # Job's psql) and asyncpg both use sslmode=prefer (attempt TLS first), and
  # pgjdbc (Keycloak's KC_DB_URL) likewise — so no URL changes are needed; the
  # db-bootstrap Job passes sslmode=require explicitly to fail closed rather
  # than silently downgrade. See infra/README.md.
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
}

resource "aws_db_instance" "this" {
  identifier     = var.identifier
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  # Creates the `medconnect` database at provision time — without db_name RDS
  # provisions only the `postgres` admin database and every app connection
  # (DATABASE_URL, KC_DB_URL, alembic) targets a database that does not exist.
  db_name = var.db_name

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.this.id]
  parameter_group_name   = aws_db_parameter_group.this.name

  username = var.master_username
  password = var.master_password
  port     = 5432

  multi_az                     = var.multi_az
  deletion_protection          = var.deletion_protection
  skip_final_snapshot          = var.skip_final_snapshot
  final_snapshot_identifier    = var.skip_final_snapshot ? null : "${var.identifier}-final-${formatdate("YYYYMMDDhhmmss", timestamp())}"
  backup_retention_period      = var.backup_retention_period
  backup_window                = var.backup_window
  performance_insights_enabled = var.performance_insights_enabled
  auto_minor_version_upgrade   = true
  copy_tags_to_snapshot        = true
  apply_immediately            = var.environment != "prod"

  tags = local.tags

  lifecycle {
    ignore_changes = [password]
  }
}

# ---------------------------------------------------------------------------
# `db_name` above gets Terraform to create the `medconnect` database at
# provision. The second logical database (`medconnect_medicines`), the
# `keycloak` schema inside `medconnect`, and the pg_trgm/pgvector extensions
# are intentionally NOT done via a Terraform provisioner: provisioners would
# need network access to the RDS endpoint from wherever `terraform apply`
# runs (a CI runner outside the VPC — that access does not reliably exist),
# and they hide an imperative step inside declarative state with no
# idempotency guarantee on retry. Instead the in-cluster db-bootstrap Job
# (infra/k8s/base/migrations/db-bootstrap-job.yaml, applied as part of the
# k8s overlays before the alembic Job) creates them idempotently from inside
# the VPC. See infra/README.md for the apply order.
# ---------------------------------------------------------------------------
