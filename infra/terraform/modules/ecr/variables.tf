variable "repository_names" {
  description = "ECR repositories to create — one build per repo, promoted through environments via immutable git-SHA tags"
  type        = list(string)
  default     = ["medconnect-backend", "medconnect-frontend", "medconnect-keycloak"]
}

variable "untagged_image_expiry_days" {
  type    = number
  default = 14
}

variable "tags" {
  type    = map(string)
  default = {}
}
