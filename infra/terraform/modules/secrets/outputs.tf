output "secret_arns" {
  description = "Map of medconnect/<environment>/<suffix> secret name to its ARN"
  value       = { for k, v in aws_secretsmanager_secret.this : v.name => v.arn }
}
