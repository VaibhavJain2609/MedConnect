terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.60"
    }
    helm = {
      source = "hashicorp/helm"
      # Pinned off v3: this module's helm_release resources below use v2's
      # `set { name = ... value = ... }` block syntax throughout, which v3
      # replaced with a `set = [{ name = ..., value = ... }]` list attribute.
      version = "~> 2.13"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.31"
    }
  }
}
