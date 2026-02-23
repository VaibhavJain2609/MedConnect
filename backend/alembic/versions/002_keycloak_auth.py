"""Replace password_hash with keycloak_sub

Revision ID: 002
Revises: 001
Create Date: 2026-02-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add keycloak_sub column (nullable initially so we can clean up first)
    op.add_column("users", sa.Column("keycloak_sub", sa.String(255), nullable=True))

    # Fresh start: delete all existing users (they used password auth)
    # This also cascades through doctors, records, prescriptions via FK constraints
    op.execute("DELETE FROM prescriptions")
    op.execute("DELETE FROM medical_records")
    op.execute("DELETE FROM doctors")
    op.execute("DELETE FROM audit_log WHERE user_id IS NOT NULL")
    op.execute("DELETE FROM users")

    # Drop password_hash column
    op.drop_column("users", "password_hash")

    # Make keycloak_sub NOT NULL now that table is empty
    op.alter_column("users", "keycloak_sub", nullable=False)

    # Add unique index on keycloak_sub
    op.create_index("idx_users_keycloak_sub", "users", ["keycloak_sub"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_users_keycloak_sub", table_name="users")
    op.drop_column("users", "keycloak_sub")
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=False, server_default=""))
