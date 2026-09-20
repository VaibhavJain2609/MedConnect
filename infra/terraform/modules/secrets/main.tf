locals {
  tags = merge(
    {
      Project     = "medconnect"
      Environment = var.environment
    },
    var.tags,
  )

  # var.secrets is marked sensitive as a whole, which taints anything
  # derived from it — including its own keys — for use in for_each
  # ("Invalid for_each argument: has a sensitive value", caught by
  # `terraform validate`). The suffixes themselves ("rds", "redis",
  # "keycloak-admin") aren't secret material, only the nested map values
  # are, so nonsensitive() here is narrowly scoped to just the key set.
  secret_suffixes = toset(nonsensitive(keys(var.secrets)))
}

resource "aws_secretsmanager_secret" "this" {
  for_each = local.secret_suffixes

  name                    = "medconnect/${var.environment}/${each.key}"
  recovery_window_in_days = var.recovery_window_in_days
  tags                    = local.tags
}

resource "aws_secretsmanager_secret_version" "this" {
  for_each = local.secret_suffixes

  secret_id     = aws_secretsmanager_secret.this[each.key].id
  secret_string = jsonencode(var.secrets[each.key])
}
