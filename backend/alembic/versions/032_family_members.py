"""Family members (dependent profiles) + medical_records.family_member_id

Revision ID: 032_family_members
Revises: 031_clinic_holidays
Create Date: 2026-10-28

- Create ``family_members``: dependent profiles (children/elders) owned by a
  patient account. Dependents are data profiles, not full users — they carry
  no credentials. ``relationship`` is constrained to
  child|spouse|parent|sibling|other at the DB level too.
- Add nullable ``medical_records.family_member_id`` FK so a patient can attach
  a self-uploaded record to a dependent. ON DELETE SET NULL keeps records
  attached to the owner if the member row is ever hard-deleted.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "032_family_members"
down_revision = "031_clinic_holidays"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "family_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("dob", sa.Date(), nullable=False),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("relationship", sa.String(20), nullable=False),
        sa.Column("blood_group", sa.String(5), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "relationship IN ('child', 'spouse', 'parent', 'sibling', 'other')",
            name="ck_family_members_relationship",
        ),
    )
    op.create_index(
        "idx_family_members_owner",
        "family_members",
        ["owner_user_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.add_column(
        "medical_records",
        sa.Column(
            "family_member_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("family_members.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_records_family_member",
        "medical_records",
        ["family_member_id"],
        postgresql_where=sa.text("family_member_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_records_family_member", table_name="medical_records")
    op.drop_column("medical_records", "family_member_id")
    op.drop_index("idx_family_members_owner", table_name="family_members")
    op.drop_table("family_members")
