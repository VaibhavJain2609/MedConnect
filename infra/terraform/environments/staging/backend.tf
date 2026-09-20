# See environments/shared/backend.tf for the bootstrap note — same bucket/table.
terraform {
  backend "s3" {
    bucket         = "medconnect-terraform-state"
    key            = "staging/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "medconnect-terraform-locks"
    encrypt        = true
  }
}
