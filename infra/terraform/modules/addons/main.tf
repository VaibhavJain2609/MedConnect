# ---------------------------------------------------------------------------
# aws-load-balancer-controller
# ---------------------------------------------------------------------------

# Every helm_release pins `version` — unpinned releases resolve to whatever
# the repo's latest is at apply time, which makes `terraform apply` output
# non-reproducible and lets a surprise chart-major upgrade break the cluster
# without any diff in this repo. Bump these deliberately.

resource "helm_release" "aws_load_balancer_controller" {
  name             = "aws-load-balancer-controller"
  repository       = "https://aws.github.io/eks-charts"
  chart            = "aws-load-balancer-controller"
  version          = "3.5.0"
  namespace        = "kube-system"
  create_namespace = false

  set {
    name  = "clusterName"
    value = var.cluster_name
  }

  set {
    name  = "region"
    value = var.region
  }

  set {
    name  = "vpcId"
    value = var.vpc_id
  }

  set {
    name  = "serviceAccount.create"
    value = "true"
  }

  set {
    name  = "serviceAccount.name"
    value = local.irsa_service_accounts.alb_controller.service_account
  }

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.irsa["alb_controller"].arn
  }
}

# ---------------------------------------------------------------------------
# external-secrets
# ---------------------------------------------------------------------------

# Chart 2.x serves only the stable external-secrets.io/v1 API (v1beta1 was
# dropped in ESO 2.0) — the k8s manifests under infra/k8s use v1 to match.
resource "helm_release" "external_secrets" {
  name             = "external-secrets"
  repository       = "https://charts.external-secrets.io"
  chart            = "external-secrets"
  version          = "2.10.0"
  namespace        = local.irsa_service_accounts.external_secrets.namespace
  create_namespace = true

  set {
    name  = "serviceAccount.create"
    value = "true"
  }

  set {
    name  = "serviceAccount.name"
    value = local.irsa_service_accounts.external_secrets.service_account
  }

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.irsa["external_secrets"].arn
  }
}

# ---------------------------------------------------------------------------
# cluster-autoscaler
# ---------------------------------------------------------------------------

resource "helm_release" "cluster_autoscaler" {
  name       = "cluster-autoscaler"
  repository = "https://kubernetes.github.io/autoscaler"
  chart      = "cluster-autoscaler"
  version    = "9.59.0"
  namespace  = "kube-system"

  set {
    name  = "autoDiscovery.clusterName"
    value = var.cluster_name
  }

  set {
    name  = "awsRegion"
    value = var.region
  }

  set {
    name  = "rbac.serviceAccount.create"
    value = "true"
  }

  set {
    name  = "rbac.serviceAccount.name"
    value = local.irsa_service_accounts.cluster_autoscaler.service_account
  }

  set {
    name  = "rbac.serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.irsa["cluster_autoscaler"].arn
  }
}

# ---------------------------------------------------------------------------
# metrics-server — no AWS permissions required, no IRSA
# ---------------------------------------------------------------------------

resource "helm_release" "metrics_server" {
  name       = "metrics-server"
  repository = "https://kubernetes-sigs.github.io/metrics-server/"
  chart      = "metrics-server"
  version    = "3.14.0"
  namespace  = "kube-system"
}

# ---------------------------------------------------------------------------
# kube-prometheus-stack (Prometheus, Grafana, Alertmanager)
# ---------------------------------------------------------------------------

resource "helm_release" "kube_prometheus_stack" {
  name             = "kube-prometheus-stack"
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  version          = "91.4.1"
  namespace        = "monitoring"
  create_namespace = true

  set {
    name  = "grafana.defaultDashboardsTimezone"
    value = "UTC"
  }
}

# ---------------------------------------------------------------------------
# cert-manager
# ---------------------------------------------------------------------------

resource "helm_release" "cert_manager" {
  name       = "cert-manager"
  repository = "https://charts.jetstack.io"
  chart      = "cert-manager"
  # cert-manager's chart version carries a literal `v` prefix.
  version          = "v1.21.2"
  namespace        = local.irsa_service_accounts.cert_manager.namespace
  create_namespace = true

  set {
    name  = "installCRDs"
    value = "true"
  }

  set {
    name  = "serviceAccount.create"
    value = "true"
  }

  set {
    name  = "serviceAccount.name"
    value = local.irsa_service_accounts.cert_manager.service_account
  }

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.irsa["cert_manager"].arn
  }
}
