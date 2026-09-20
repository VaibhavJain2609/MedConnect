variable "cluster_name" {
  description = "Name of the shared EKS cluster"
  type        = string
  default     = "medconnect"
}

variable "cluster_version" {
  description = "Kubernetes version for the EKS control plane"
  type        = string
  default     = "1.31"
}

variable "vpc_id" {
  description = "VPC id the cluster runs in"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet ids for the control plane ENIs and worker nodes"
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "Public subnet ids (needed if public endpoint access or public-facing load balancers require them)"
  type        = list(string)
}

variable "cluster_log_types" {
  description = "EKS control plane log types to ship to CloudWatch"
  type        = list(string)
  default     = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
}

variable "cluster_log_retention_days" {
  description = "CloudWatch log retention for EKS control plane logs"
  type        = number
  default     = 30
}

variable "node_instance_types" {
  description = "Instance types for the managed node group"
  type        = list(string)
  default     = ["t3.large"]
}

variable "node_capacity_type" {
  description = "ON_DEMAND or SPOT"
  type        = string
  default     = "ON_DEMAND"
}

variable "node_min_size" {
  description = "Minimum node count for the managed node group"
  type        = number
}

variable "node_max_size" {
  description = "Maximum node count for the managed node group"
  type        = number
}

variable "node_desired_size" {
  description = "Desired node count for the managed node group"
  type        = number
}

variable "node_disk_size" {
  description = "EBS root volume size (GiB) for worker nodes"
  type        = number
  default     = 50
}

variable "endpoint_public_access" {
  description = "Whether the EKS API server endpoint is reachable publicly (CI/CD needs this unless it runs inside the VPC)"
  type        = bool
  default     = true
}

variable "endpoint_public_access_cidrs" {
  description = "CIDRs allowed to reach the public API server endpoint"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "tags" {
  description = "Additional tags applied to cluster resources"
  type        = map(string)
  default     = {}
}
