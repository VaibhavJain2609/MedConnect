"""doctor credentials + patient demographics — NMC-compliant prescriptions

Revision ID: 039_doctor_credentials
Revises: 038_hot_path_indexes
Create Date: 2026-11-16

- ``doctors.qualifications`` — free-text degrees (e.g. "MBBS, MD (Medicine)")
  rendered on the prescription PDF per NMC telemedicine/practice guidelines.
- ``doctors.registration_number`` — NMC / State Medical Council registration
  number printed next to the doctor's name on Rx PDFs.
- ``doctors.signature_url`` — object key (or https URL) of an uploaded
  signature image; the PDF embeds it when resolvable from local storage,
  otherwise renders a "signature on file" line.
- ``users.date_of_birth`` / ``users.sex`` — patient demographics used to
  render age + sex on prescriptions (values kept simple: male/female/other).
"""
import sqlalchemy as sa
from alembic import op

revision = "039_doctor_credentials"
down_revision = "038_hot_path_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("doctors", sa.Column("qualifications", sa.String(255), nullable=True))
    op.add_column("doctors", sa.Column("registration_number", sa.String(50), nullable=True))
    op.add_column("doctors", sa.Column("signature_url", sa.String(500), nullable=True))
    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("sex", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "sex")
    op.drop_column("users", "date_of_birth")
    op.drop_column("doctors", "signature_url")
    op.drop_column("doctors", "registration_number")
    op.drop_column("doctors", "qualifications")
