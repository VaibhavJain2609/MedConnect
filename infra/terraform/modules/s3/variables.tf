variable "environment" {
  type = string
}

variable "account_id" {
  description = "AWS account id, interpolated into the bucket name for global uniqueness"
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
