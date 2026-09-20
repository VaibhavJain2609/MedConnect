locals {
  tags = merge({ Project = "medconnect" }, var.tags)

  irsa_service_accounts = {
    alb_controller = {
      namespace       = "kube-system"
      service_account = "aws-load-balancer-controller"
    }
    external_secrets = {
      namespace       = "external-secrets"
      service_account = "external-secrets"
    }
    cluster_autoscaler = {
      namespace       = "kube-system"
      service_account = "cluster-autoscaler"
    }
    cert_manager = {
      namespace       = "cert-manager"
      service_account = "cert-manager"
    }
  }
}

data "aws_iam_policy_document" "irsa_assume" {
  for_each = local.irsa_service_accounts

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:${each.value.namespace}:${each.value.service_account}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "irsa" {
  for_each = local.irsa_service_accounts

  name               = "${var.cluster_name}-${replace(each.key, "_", "-")}"
  assume_role_policy = data.aws_iam_policy_document.irsa_assume[each.key].json
  tags               = local.tags
}

# ---------------------------------------------------------------------------
# aws-load-balancer-controller — well-known AWS reference IAM policy
# (https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/main/docs/install/iam_policy.json)
# ---------------------------------------------------------------------------

resource "aws_iam_role_policy" "alb_controller" {
  name   = "aws-load-balancer-controller"
  role   = aws_iam_role.irsa["alb_controller"].id
  policy = file("${path.module}/policies/aws-load-balancer-controller.json")
}

# ---------------------------------------------------------------------------
# external-secrets — read-only access to MedConnect's Secrets Manager tree
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "external_secrets" {
  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = ["arn:aws:secretsmanager:${var.region}:*:secret:medconnect/*"]
  }

  statement {
    effect    = "Allow"
    actions   = ["secretsmanager:ListSecrets"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "external_secrets" {
  name   = "external-secrets-read"
  role   = aws_iam_role.irsa["external_secrets"].id
  policy = data.aws_iam_policy_document.external_secrets.json
}

# ---------------------------------------------------------------------------
# cluster-autoscaler — scoped to this cluster's ASGs via the discovery tag
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "cluster_autoscaler" {
  statement {
    effect = "Allow"
    actions = [
      "autoscaling:DescribeAutoScalingGroups",
      "autoscaling:DescribeAutoScalingInstances",
      "autoscaling:DescribeLaunchConfigurations",
      "autoscaling:DescribeScalingActivities",
      "autoscaling:DescribeTags",
      "ec2:DescribeInstanceTypes",
      "ec2:DescribeLaunchTemplateVersions",
    ]
    resources = ["*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "autoscaling:SetDesiredCapacity",
      "autoscaling:TerminateInstanceInAutoScalingGroup",
      "autoscaling:UpdateAutoScalingGroup",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/k8s.io/cluster-autoscaler/${var.cluster_name}"
      values   = ["owned"]
    }
  }
}

resource "aws_iam_role_policy" "cluster_autoscaler" {
  name   = "cluster-autoscaler"
  role   = aws_iam_role.irsa["cluster_autoscaler"].id
  policy = data.aws_iam_policy_document.cluster_autoscaler.json
}

# ---------------------------------------------------------------------------
# cert-manager — Route53 DNS-01 solver, optional
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "cert_manager" {
  count = var.enable_cert_manager_route53 ? 1 : 0

  statement {
    effect    = "Allow"
    actions   = ["route53:GetChange"]
    resources = ["arn:aws:route53:::change/*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "route53:ChangeResourceRecordSets",
      "route53:ListResourceRecordSets",
    ]
    resources = ["arn:aws:route53:::hostedzone/*"]
  }

  statement {
    effect    = "Allow"
    actions   = ["route53:ListHostedZonesByName"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "cert_manager" {
  count  = var.enable_cert_manager_route53 ? 1 : 0
  name   = "cert-manager-route53-dns01"
  role   = aws_iam_role.irsa["cert_manager"].id
  policy = data.aws_iam_policy_document.cert_manager[0].json
}
