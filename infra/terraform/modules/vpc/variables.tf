variable "name" {
  description = "Name prefix for VPC resources"
  type        = string
  default     = "medconnect"
}

variable "cluster_name" {
  description = "EKS cluster name used for the kubernetes.io/cluster/<name> discovery tag"
  type        = string
  default     = "medconnect"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.20.0.0/16"
}

variable "azs" {
  description = "Availability zones to spread subnets across (exactly 2)"
  type        = list(string)
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets, one per AZ"
  type        = list(string)
  default     = ["10.20.0.0/20", "10.20.16.0/20"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets, one per AZ"
  type        = list(string)
  default     = ["10.20.128.0/20", "10.20.144.0/20"]
}

variable "tags" {
  description = "Additional tags applied to all resources"
  type        = map(string)
  default     = {}
}
