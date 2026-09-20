terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.60, < 7.0"
    }
    helm = {
      source = "hashicorp/helm"
      # Pinned to the v2 major line deliberately: v3 replaced the nested
      # `kubernetes { ... }` / `exec { ... }` provider-config blocks below
      # with flattened object-type attributes — a real breaking change,
      # caught by `terraform validate` failing against v3.2.0 with "Blocks
      # of type kubernetes are not expected here."
      version = "~> 2.13"
    }
    kubernetes = {
      source = "hashicorp/kubernetes"
      # Same reasoning as helm above — pinned off v3 to keep the `exec { }`
      # block syntax this file uses.
      version = "~> 2.31"
    }
  }
}

provider "aws" {
  region = var.region
}

# Both the helm and kubernetes providers authenticate to the cluster this
# same apply creates — via the `aws eks get-token` exec plugin rather than a
# static kubeconfig, so a fresh `terraform apply` from a clean checkout works
# without a prior `aws eks update-kubeconfig` step.
provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name, "--region", var.region]
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name, "--region", var.region]
    }
  }
}
