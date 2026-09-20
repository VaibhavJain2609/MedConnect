variable "replication_group_id" {
  description = "e.g. medconnect-staging-redis"
  type        = string
}

variable "environment" {
  type = string
}

variable "node_type" {
  type = string
}

variable "num_cache_nodes" {
  description = "Number of nodes total (1 = primary only, >1 adds replicas)"
  type        = number
}

variable "engine_version" {
  type    = string
  default = "7.1"
}

variable "auth_token" {
  description = "Redis AUTH token, generated via random_password in the environment root"
  type        = string
  sensitive   = true
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "allowed_security_group_ids" {
  type    = list(string)
  default = []
}

variable "allowed_cidr_blocks" {
  type    = list(string)
  default = []
}

variable "snapshot_retention_limit" {
  description = "Days to retain automatic ElastiCache snapshots. 0 disables snapshots entirely — a cache loss is then unrecoverable, so keep at least a few days even in staging."
  type        = number
  default     = 7
}

variable "tags" {
  type    = map(string)
  default = {}
}
