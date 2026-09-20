variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "rds_instance_class" {
  type    = string
  default = "db.r6g.large"
}

variable "rds_allocated_storage" {
  type    = number
  default = 100
}

variable "rds_max_allocated_storage" {
  type    = number
  default = 500
}

variable "redis_node_type" {
  type    = string
  default = "cache.r6g.large"
}

variable "redis_num_cache_nodes" {
  description = "2 = primary + one replica, automatic failover enabled"
  type        = number
  default     = 2
}

variable "keycloak_admin_username" {
  type    = string
  default = "admin"
}

variable "sentry_dsn" {
  type      = string
  default   = ""
  sensitive = true
}

variable "auth_hostname" {
  type = string
}

variable "app_hostname" {
  type = string
}

variable "acm_certificate_arn" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
