variable "github_org" {
  description = "GitHub organization or username that owns the repo"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name (without the org prefix)"
  type        = string
}

variable "deploy_branch" {
  description = "Branch allowed to assume this role outside of a GitHub Environment context (the CD workflow's push trigger)"
  type        = string
  default     = "master"
}

variable "create_oidc_provider" {
  description = "Whether to create the token.actions.githubusercontent.com OIDC provider. AWS allows only one per account+URL — set false and supply existing_oidc_provider_arn if a provider already exists (e.g. from another project's Terraform state)."
  type        = bool
  default     = true
}

variable "existing_oidc_provider_arn" {
  description = "ARN of an existing GitHub OIDC provider, used when create_oidc_provider = false"
  type        = string
  default     = null
}

variable "ecr_repository_arns" {
  description = "ECR repository ARNs the role may push images to"
  type        = list(string)
}

variable "eks_cluster_arn" {
  description = "EKS cluster ARN the role is allowed to describe (needed for `aws eks update-kubeconfig`)"
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
