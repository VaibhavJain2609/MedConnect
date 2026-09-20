data "aws_caller_identity" "current" {}

# ---------------------------------------------------------------------------
# Network + cluster — created once. Both medconnect-staging and
# medconnect-prod namespaces run on this same VPC/EKS cluster (see
# infra/README.md for the reasoning: data isolation via separate RDS/Redis
# per environment matters more than compute isolation for a project this size).
# ---------------------------------------------------------------------------

module "vpc" {
  source = "../../modules/vpc"

  name         = "medconnect"
  cluster_name = "medconnect"
  azs          = var.azs
  tags         = var.tags
}

module "eks" {
  source = "../../modules/eks"

  cluster_name        = "medconnect"
  cluster_version     = var.cluster_version
  vpc_id              = module.vpc.vpc_id
  private_subnet_ids  = module.vpc.private_subnet_ids
  public_subnet_ids   = module.vpc.public_subnet_ids
  node_instance_types = var.node_instance_types
  node_min_size       = var.node_min_size
  node_max_size       = var.node_max_size
  node_desired_size   = var.node_desired_size
  tags                = var.tags
}

module "addons" {
  source = "../../modules/addons"

  cluster_name      = module.eks.cluster_name
  region            = var.region
  vpc_id            = module.vpc.vpc_id
  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_provider_url = module.eks.oidc_provider_url
  tags              = var.tags

  depends_on = [module.eks]
}

# ---------------------------------------------------------------------------
# ECR — one registry, shared by both environments. Images are promoted
# between staging/prod by tag (immutable, git-SHA), not by separate registries.
# ---------------------------------------------------------------------------

module "ecr" {
  source = "../../modules/ecr"
  tags   = var.tags
}

# ---------------------------------------------------------------------------
# GitHub Actions OIDC role
# ---------------------------------------------------------------------------

module "iam_oidc_github" {
  source = "../../modules/iam-oidc-github"

  github_org          = var.github_org
  github_repo         = var.github_repo
  deploy_branch       = var.deploy_branch
  ecr_repository_arns = values(module.ecr.repository_arns)
  eks_cluster_arn     = module.eks.cluster_arn
  tags                = var.tags
}

# Grants the GitHub Actions role kubectl access scoped to just the two
# MedConnect namespaces — not cluster-admin. Edit policy covers everything
# the CD pipeline does (apply Deployments/Jobs/Services, roll back, read
# logs for the smoke-test step); it cannot touch cluster-scoped objects
# (Nodes, ClusterRoles, the ClusterSecretStore) or other namespaces.
resource "aws_eks_access_entry" "github_actions" {
  cluster_name  = module.eks.cluster_name
  principal_arn = module.iam_oidc_github.role_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "github_actions_edit" {
  cluster_name  = module.eks.cluster_name
  principal_arn = module.iam_oidc_github.role_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSEditPolicy"

  access_scope {
    type       = "namespace"
    namespaces = ["medconnect-staging", "medconnect-prod"]
  }
}
