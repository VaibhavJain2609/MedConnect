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

variable "rds_multi_az" {
  type    = bool
  default = true
}

variable "rds_deletion_protection" {
  type    = bool
  default = true
}

variable "rds_skip_final_snapshot" {
  type    = bool
  default = false
}

variable "rds_backup_retention_period" {
  type    = number
  default = 30
}

variable "secrets_recovery_window_in_days" {
  description = "0 allows immediate hard-delete — keep the 30d default for real production, override in tfvars for throwaway test deployments"
  type        = number
  default     = 30
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
  description = "Keycloak's public hostname for this environment, e.g. auth.medconnect.example.com"
  type        = string
}

variable "app_hostname" {
  description = "Frontend/backend public hostname for this environment, e.g. medconnect.example.com"
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
