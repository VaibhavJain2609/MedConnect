# Bootstrap chicken-and-egg: an S3 backend bucket can't create itself.
# Before the first `terraform init` anywhere in infra/terraform, create the
# bucket (versioning enabled) and DynamoDB lock table once by hand — see
# infra/README.md for the exact commands. Every environment shares the same
# bucket/table and is namespaced by `key`.
terraform {
  backend "s3" {
    bucket         = "medconnect-terraform-state"
    key            = "shared/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "medconnect-terraform-locks"
    encrypt        = true
  }
}
