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
# Database/schema creation for `medconnect`, `medconnect_medicines`, and the
# `keycloak` schema is intentionally NOT done via a Terraform provisioner.
# `aws_db_instance` provisioners would need network-level access to the RDS
# endpoint from wherever `terraform apply` runs, which is a CI runner outside
# the VPC here — that access does not reliably exist, and provisioners hide
# an imperative step inside declarative state with no idempotency guarantee
# on retry. Instead this is a documented post-apply CI step: the deploy
# pipeline (running inside the cluster, which already has network access)
# applies backend/*/migrations against this instance before the app rolls
# out. See infra/terraform/README.md for the exact command.
# ---------------------------------------------------------------------------
