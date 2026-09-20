output "endpoint" {
  value = aws_db_instance.this.address
}

output "port" {
  value = aws_db_instance.this.port
}

output "identifier" {
  value = aws_db_instance.this.identifier
}

output "security_group_id" {
  value = aws_security_group.this.id
}

output "db_name_placeholder" {
  description = "RDS itself has no default database beyond `postgres`; medconnect/medconnect_medicines/keycloak schema creation is a post-apply CI step — see module main.tf"
  value       = "postgres"
}
