output "irsa_role_arns" {
  description = "Map of addon key to its IRSA IAM role ARN"
  value       = { for k, v in aws_iam_role.irsa : k => v.arn }
}
