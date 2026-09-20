locals {
  tags = merge({ Project = "medconnect" }, var.tags)

  oidc_provider_arn = var.create_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : var.existing_oidc_provider_arn

  # GitHub's sub claim differs by trigger context: a push to a protected branch
  # carries `ref:refs/heads/<branch>`, while a job gated by a GitHub Environment
  # (production, behind required reviewers) carries `environment:<name>`
  # instead — both must be allowlisted or the prod deploy job's token is rejected.
  # The Environment names must match the workflows exactly: cd.yml/deploy.yml/
  # rollback.yml all gate on `environment: production` (not `prod`).
  allowed_subs = [
    "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/${var.deploy_branch}",
    "repo:${var.github_org}/${var.github_repo}:environment:staging",
    "repo:${var.github_org}/${var.github_repo}:environment:production",
  ]
}

# GitHub's OIDC thumbprint is well-known and stable, but fetching it live
# avoids hardcoding a value that silently goes stale if GitHub ever rotates
# their intermediate CA.
data "tls_certificate" "github" {
  url = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_oidc_provider ? 1 : 0

  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.github.certificates[0].sha1_fingerprint]
  tags            = local.tags
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"

    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = local.allowed_subs
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "medconnect-github-actions"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = local.tags
}

# ECR push — immutable-tag repos, so no delete/overwrite permission is needed.
data "aws_iam_policy_document" "permissions" {
  statement {
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:PutImage",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
    ]
    resources = var.ecr_repository_arns
  }

  # `aws eks update-kubeconfig` only needs DescribeCluster; actual kubectl
  # authorization comes from the cluster's own EKS access entry for this role
  # (see environments/shared/main.tf), not from IAM.
  statement {
    effect    = "Allow"
    actions   = ["eks:DescribeCluster"]
    resources = [var.eks_cluster_arn]
  }
}

resource "aws_iam_role_policy" "github_actions" {
  name   = "medconnect-github-actions"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.permissions.json
}
