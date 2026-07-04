"""add index on events for the dashboard's user-scoped sort (Slice 5.1, #54)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-03 00:00:00.000000

The dashboard query (app.api.v1.events.list_user_events) filters by ``user_id`` and orders by
``resolved_date_earliest DESC NULLS LAST, created_at DESC`` on every page load. The existing
``uq_events_user_description_resolved_date`` unique index starts with ``user_id`` but is otherwise
keyed on ``description``/``resolved_date`` (text columns), so it can't serve this sort. This index
covers the exact filter+sort the dashboard runs.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        'ix_events_user_id_resolved_date_earliest_created_at',
        'events',
        ['user_id', 'resolved_date_earliest', 'created_at'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_events_user_id_resolved_date_earliest_created_at', table_name='events')
