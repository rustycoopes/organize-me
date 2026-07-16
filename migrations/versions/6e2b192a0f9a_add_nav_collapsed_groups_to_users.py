"""add nav_collapsed_groups to host.users (sidebar-nav-groups, organize-me#212)

Revision ID: 6e2b192a0f9a
Revises: e6f7a8b9c0d1
Create Date: 2026-07-16 00:00:00.000000

Per-user sidebar nav-group collapse state, keyed by app service_name
(organizeme_chrome.registry) -> collapsed bool. A missing key means expanded, so a JSON default of
`{}` correctly represents "every group expanded" for both existing and newly-created users.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6e2b192a0f9a'
down_revision: Union[str, Sequence[str], None] = 'e6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("nav_collapsed_groups", sa.JSON(), nullable=False, server_default="{}"),
        schema="host",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "nav_collapsed_groups", schema="host")
