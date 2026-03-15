"""Allow multiple patients to share email/phone (family accounts)

Revision ID: 016_family_accounts
Revises: 015_rx_appointment_id
"""
from alembic import op

revision = "016_family_accounts"
down_revision = "015_rx_appointment_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("users_email_key", "users", type_="unique")
    op.drop_constraint("users_phone_key", "users", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("users_email_key", "users", ["email"])
    op.create_unique_constraint("users_phone_key", "users", ["phone"])
