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
  description = "Patch this into infra/k8s/overlays/staging's ingress alb.ingress.kubernetes.io/wafv2-acl-arn annotation"
  value       = module.waf.web_acl_arn
}

output "secret_arns" {
  value = module.secrets.secret_arns
}
