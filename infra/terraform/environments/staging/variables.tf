variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "rds_instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "rds_allocated_storage" {
  type    = number
  default = 50
}

variable "rds_max_allocated_storage" {
  type    = number
  default = 100
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.small"
}

variable "redis_num_cache_nodes" {
  description = "1 = primary only, no replica — acceptable for staging"
  type        = number
  default     = 1
}

variable "keycloak_admin_username" {
  type    = string
  default = "admin"
}

variable "sentry_dsn" {
  description = "Optional Sentry DSN for the backend; empty disables Sentry (sentry_sdk.init is skipped when SENTRY_DSN is falsy)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "auth_hostname" {
  description = "Keycloak's public hostname for this environment, e.g. auth-staging.medconnect.example.com"
  type        = string
}

variable "app_hostname" {
  description = "Frontend/backend public hostname for this environment, e.g. staging.medconnect.example.com"
  type        = string
}

variable "acm_certificate_arn" {
  description = "ACM cert covering both auth_hostname and app_hostname (or a wildcard), provisioned manually or via a separate ACM+Route53 module — out of scope here since it depends on a real owned domain"
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
