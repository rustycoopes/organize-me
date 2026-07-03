"""create processing_runs, processing_steps and events tables

Revision ID: e5f6a7b8c9d0
Revises: d3e4f5a6b7c8
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

import fastapi_users_db_sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'processing_runs',
        sa.Column('id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column('user_id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column('filename', sa.Text(), nullable=False),
        sa.Column(
            'status',
            sa.Enum(
                'pending', 'in_progress', 'success', 'failed', name='processing_run_status'
            ),
            nullable=False,
        ),
        sa.Column(
            'events_extracted_count', sa.Integer(), server_default='0', nullable=False
        ),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='cascade'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'processing_steps',
        sa.Column('id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column('run_id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('step_name', sa.Text(), nullable=False),
        sa.Column(
            'status',
            sa.Enum(
                'pending', 'in_progress', 'success', 'failed', 'skipped',
                name='processing_step_status',
            ),
            nullable=False,
        ),
        sa.Column(
            'log_lines', postgresql.JSONB(astext_type=sa.Text()),
            server_default='[]', nullable=False,
        ),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['processing_runs.id'], ondelete='cascade'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'events',
        sa.Column('id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column('user_id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column('run_id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column('type', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('resolved_date', sa.Text(), nullable=False),
        sa.Column('resolved_date_earliest', sa.Date(), nullable=True),
        sa.Column('raw_date_text', sa.Text(), nullable=False),
        sa.Column(
            'agreed_by', postgresql.JSONB(astext_type=sa.Text()),
            server_default='[]', nullable=False,
        ),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='cascade'),
        sa.ForeignKeyConstraint(['run_id'], ['processing_runs.id'], ondelete='cascade'),
        sa.PrimaryKeyConstraint('id'),
        # Duplicate detection: one identical agreed event per user.
        sa.UniqueConstraint(
            'user_id', 'description', 'resolved_date',
            name='uq_events_user_description_resolved_date',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('events')
    op.drop_table('processing_steps')
    op.drop_table('processing_runs')
    # Native enum types aren't dropped with their table - drop them so a re-upgrade is clean.
    sa.Enum(name='processing_step_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='processing_run_status').drop(op.get_bind(), checkfirst=True)
