output "rds_endpoint" {
  value = module.rds.endpoint
}

output "redis_primary_endpoint" {
  value = module.elasticache.primary_endpoint
}

output "s3_bucket_name" {
  value = module.s3.bucket_name
}

output "waf_web_acl_arn" {
  description = "Patch this into infra/k8s/overlays/prod's ingress alb.ingress.kubernetes.io/wafv2-acl-arn annotation"
  value       = module.waf.web_acl_arn
}

# These three variables don't feed any Terraform resource — the Ingress that
# consumes them lives in the k8s overlays, which Terraform doesn't apply.
# They exist here so `terraform apply` validates that the operator actually
# has a real domain + cert before the stack is provisioned, and so this
# output prints exactly the values the CD pipeline (or a manual deployer)
# must substitute for the PLACEHOLDER_* strings in
# infra/k8s/overlays/prod/kustomization.yaml.
output "ingress_config" {
  description = "Values to substitute into the k8s overlay Ingress/ConfigMap placeholders (ACM cert ARN + hostnames)"
  value = {
    acm_certificate_arn = var.acm_certificate_arn
    auth_hostname       = var.auth_hostname
    app_hostname        = var.app_hostname
  }
}

output "secret_arns" {
  value = module.secrets.secret_arns
}
