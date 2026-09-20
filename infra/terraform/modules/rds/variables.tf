variable "identifier" {
  description = "RDS instance identifier, e.g. medconnect-staging-db"
  type        = string
}

variable "environment" {
  type = string
}

variable "engine_version" {
  description = "Postgres 16.x engine version"
  type        = string
  default     = "16.4"
}

variable "instance_class" {
  type = string
}

variable "allocated_storage" {
  type = number
}

variable "max_allocated_storage" {
  description = "Upper bound for RDS storage autoscaling"
  type        = number
  default     = null
}

variable "multi_az" {
  type = bool
}

variable "deletion_protection" {
  type = bool
}

variable "skip_final_snapshot" {
  description = "Skip the final snapshot on destroy. Should be false in prod."
  type        = bool
  default     = true
}

variable "master_username" {
  type    = string
  default = "medconnect_admin"
}

variable "master_password" {
  description = "Master password, generated via random_password in the environment root and read from Secrets Manager thereafter"
  type        = string
  sensitive   = true
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  description = "Private subnet ids for the DB subnet group"
  type        = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security groups allowed to connect to Postgres on 5432 (e.g. the EKS node security group)"
  type        = list(string)
  default     = []
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to connect to Postgres on 5432"
  type        = list(string)
  default     = []
}

variable "db_name" {
  description = "Initial database RDS creates at provision time. `medconnect` is the app's main DB; the second logical database (`medconnect_medicines`) and the `keycloak` schema are created post-apply by the in-cluster db-bootstrap Job (infra/k8s/base/migrations/db-bootstrap-job.yaml)."
  type        = string
  default     = "medconnect"
}

variable "backup_retention_period" {
  type    = number
  default = 7
}

variable "backup_window" {
  description = "Daily UTC window for automated backups, HH:MM-HH:MM (e.g. \"20:00-21:00\" ≈ 01:30-02:30 IST). null lets AWS pick — fine for staging, set an explicit low-traffic window for prod."
  type        = string
  default     = null
}

variable "performance_insights_enabled" {
  type    = bool
  default = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
