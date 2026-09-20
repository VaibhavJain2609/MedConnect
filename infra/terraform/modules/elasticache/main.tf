locals {
  tags = merge(
    {
      Project     = "medconnect"
      Environment = var.environment
    },
    var.tags,
  )

  automatic_failover = var.num_cache_nodes > 1
}

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.replication_group_id}-subnets"
  subnet_ids = var.subnet_ids
  tags       = local.tags
}

resource "aws_security_group" "this" {
  name        = "${var.replication_group_id}-sg"
  description = "Redis access for ${var.replication_group_id}"
  vpc_id      = var.vpc_id
  tags        = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "sg" {
  count                        = length(var.allowed_security_group_ids)
  security_group_id            = aws_security_group.this.id
  referenced_security_group_id = var.allowed_security_group_ids[count.index]
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "cidr" {
  count             = length(var.allowed_cidr_blocks)
  security_group_id = aws_security_group.this.id
  cidr_ipv4         = var.allowed_cidr_blocks[count.index]
  from_port         = 6379
  to_port           = 6379
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.this.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id = var.replication_group_id
  description          = "MedConnect Redis (${var.environment})"

  engine         = "redis"
  engine_version = var.engine_version
  node_type      = var.node_type
  port           = 6379

  num_cache_clusters = var.num_cache_nodes

  automatic_failover_enabled = local.automatic_failover
  multi_az_enabled           = local.automatic_failover

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = [aws_security_group.this.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = var.auth_token

  auto_minor_version_upgrade = true
  apply_immediately          = var.environment != "prod"

  tags = local.tags

  lifecycle {
    ignore_changes = [auth_token]
  }
}
