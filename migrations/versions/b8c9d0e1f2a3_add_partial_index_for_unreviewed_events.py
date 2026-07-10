"""add partial index for the dashboard's default unreviewed-events query (#113)

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-09 00:10:00.000000

``show_reviewed=False`` is the default on every ``/dashboard``/``GET /api/v1/events`` call, so
``AND reviewed = false`` now runs on the dashboard's hot path on every page load. The existing
``ix_events_user_id_resolved_date_earliest_created_at`` index (added in f6a7b8c9d0e1 to cover this
same query's filter+sort) doesn't include ``reviewed``, so Postgres has to walk every one of a
user's events - including ones already marked reviewed - to apply that predicate as a Filter rather
than an Index Cond. As users mark more events reviewed over time, that wasted scan only grows.

A partial index scoped to ``WHERE reviewed = false`` covers the default query directly and stays
small regardless of how many reviewed events accumulate (unlike a plain composite index, which
would grow with the whole table). The ``show_reviewed=True`` path still uses the existing
non-partial index.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        'ix_events_user_id_unreviewed_sort',
        'events',
        ['user_id', 'resolved_date_earliest', 'created_at'],
        postgresql_where=sa.text('reviewed = false'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_events_user_id_unreviewed_sort', table_name='events')
