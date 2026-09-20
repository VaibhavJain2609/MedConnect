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

output "db_name" {
  description = "The database RDS created at provision (var.db_name, default `medconnect`). `medconnect_medicines` + the `keycloak` schema are created by the in-cluster db-bootstrap Job — see module main.tf."
  value       = aws_db_instance.this.db_name
}
