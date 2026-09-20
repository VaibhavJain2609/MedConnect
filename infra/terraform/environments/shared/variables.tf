variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "azs" {
  description = "Exactly 2 availability zones to spread subnets across"
  type        = list(string)
  default     = ["ap-south-1a", "ap-south-1b"]
}

variable "cluster_version" {
  type    = string
  default = "1.31"
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t3.large"]
}

variable "node_min_size" {
  type    = number
  default = 2
}

variable "node_max_size" {
  description = "Upper bound the Cluster Autoscaler can scale the shared node group to — both namespaces' HPAs compete for capacity within this ceiling"
  type        = number
  default     = 6
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "eks_endpoint_public_access_cidrs" {
  description = <<-EOT
    CIDRs allowed to reach the EKS public API endpoint. Defaults to 0.0.0.0/0
    because the deploy pipeline runs on GitHub-hosted runners whose egress IPs
    span GitHub's published ranges — restricting this breaks `kubectl apply`
    in CI unless runners are self-hosted (or you allowlist GitHub's egress
    ranges, which rotate). Tighten to office/VPN/self-hosted-runner CIDRs if
    the API surface should not be world-reachable; the endpoint is always
    TLS + IAM-authenticated regardless.
  EOT
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "github_org" {
  description = "GitHub org/user that owns the MedConnect repo, e.g. \"VaibhavJain2609\""
  type        = string
}

variable "github_repo" {
  type    = string
  default = "MedConnect"
}

variable "deploy_branch" {
  type    = string
  default = "master"
}

variable "tags" {
  type    = map(string)
  default = {}
}
