variable "environment" {
  type = string
}

variable "secrets" {
  description = "Map of secret name suffix (e.g. \"rds\", \"redis\", \"keycloak-admin\") to its key/value body. Stored at medconnect/<environment>/<suffix> as JSON, matching the key layout each k8s ExternalSecret's dataFrom.extract expects."
  type        = map(map(string))
  sensitive   = true
}

variable "recovery_window_in_days" {
  description = "Secrets Manager deletion recovery window. 0 allows immediate hard-delete (useful for a staging environment that gets torn down and recreated); prod should keep the default so a bad `terraform destroy` is recoverable."
  type        = number
  default     = 30
}

variable "tags" {
  type    = map(string)
  default = {}
}
