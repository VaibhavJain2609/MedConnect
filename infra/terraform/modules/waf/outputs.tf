output "web_acl_arn" {
  description = "ARN to patch into the environment's Ingress alb.ingress.kubernetes.io/wafv2-acl-arn annotation"
  value       = aws_wafv2_web_acl.this.arn
}
