variable "cluster_name" {
  type = string
}

variable "region" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "oidc_provider_arn" {
  description = "ARN of the EKS cluster's IAM OIDC provider (from the eks module)"
  type        = string
}

variable "oidc_provider_url" {
  description = "OIDC provider URL without the https:// prefix (from the eks module)"
  type        = string
}

variable "enable_cert_manager_route53" {
  description = "Grant cert-manager's IRSA role Route53 DNS-01 permissions"
  type        = bool
  default     = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
