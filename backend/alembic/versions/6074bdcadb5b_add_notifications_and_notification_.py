"""Add notifications and notification preferences tables

Revision ID: 6074bdcadb5b
Revises: 003
Create Date: 2026-02-28 09:28:39.310027
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6074bdcadb5b'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create notification_preferences table
    op.create_table('notification_preferences',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notification_preferences_user_id'), 'notification_preferences', ['user_id'], unique=True)

    # Create notifications table
    op.create_table('notifications',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('type', sa.String(length=20), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('read', sa.Boolean(), nullable=False),
    sa.Column('action_url', sa.String(length=512), nullable=True),
    sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for notifications table
    op.create_index('idx_notifications_user_created', 'notifications', ['user_id', 'created_at'], unique=False, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index('idx_notifications_user_read', 'notifications', ['user_id', 'read'], unique=False, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index('idx_notifications_user_type', 'notifications', ['user_id', 'type'], unique=False, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)
    op.create_index(op.f('ix_notifications_read'), 'notifications', ['read'], unique=False)
    op.create_index(op.f('ix_notifications_type'), 'notifications', ['type'], unique=False)
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)


def downgrade() -> None:
    # Drop notifications table and its indexes
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_type'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_read'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_index('idx_notifications_user_type', table_name='notifications', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index('idx_notifications_user_read', table_name='notifications', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index('idx_notifications_user_created', table_name='notifications', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_table('notifications')

    # Drop notification_preferences table and its indexes
    op.drop_index(op.f('ix_notification_preferences_user_id'), table_name='notification_preferences')
    op.drop_table('notification_preferences')
