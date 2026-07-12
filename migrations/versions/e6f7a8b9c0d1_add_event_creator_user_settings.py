"""add event_creator.user_settings, backfill, drop moved columns from host.users (Slice R2, #158)

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2026-07-12 00:00:00.000000

Moves the notification-preference and onboarding-progress columns off `host.users` into a new
`event_creator.user_settings` table (one row per user, FK cascade to `host.users.id`) - they're
conceptually Event-Creator settings, written and read entirely by Event-Creator flows, but sat on
the Host user table. Backfill-then-drop (not a bare column move) keeps rollback safe: downgrade()
re-adds the columns and backfills them back from `user_settings` before dropping the table.
"""
from typing import Sequence, Union

import fastapi_users_db_sqlalchemy
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MOVED_COLUMNS = [
    "notification_sms",
    "notification_email",
    "onboarding_storage_done",
    "onboarding_notifications_done",
    "onboarding_first_upload_done",
]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_settings",
        sa.Column("id", fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column("user_id", fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column("notification_sms", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("notification_email", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "onboarding_storage_done", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "onboarding_notifications_done", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "onboarding_first_upload_done", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["host.users.id"], ondelete="cascade"),
        sa.UniqueConstraint("user_id"),
        schema="event_creator",
    )

    # Backfill: one settings row per existing host.users row, carrying over their current values
    # (not the column defaults - a user who already disabled a channel must keep it disabled).
    op.execute(
        """
        INSERT INTO event_creator.user_settings (
            id, user_id, notification_sms, notification_email,
            onboarding_storage_done, onboarding_notifications_done, onboarding_first_upload_done
        )
        SELECT
            gen_random_uuid(), id, notification_sms, notification_email,
            onboarding_storage_done, onboarding_notifications_done, onboarding_first_upload_done
        FROM host.users
        """
    )

    for column in _MOVED_COLUMNS:
        op.drop_column("users", column, schema="host")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "notification_sms", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        schema="host",
    )
    op.add_column(
        "users",
        sa.Column(
            "notification_email", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        schema="host",
    )
    op.add_column(
        "users",
        sa.Column(
            "onboarding_storage_done",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema="host",
    )
    op.add_column(
        "users",
        sa.Column(
            "onboarding_notifications_done",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema="host",
    )
    op.add_column(
        "users",
        sa.Column(
            "onboarding_first_upload_done",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema="host",
    )

    op.execute(
        """
        UPDATE host.users u
        SET
            notification_sms = s.notification_sms,
            notification_email = s.notification_email,
            onboarding_storage_done = s.onboarding_storage_done,
            onboarding_notifications_done = s.onboarding_notifications_done,
            onboarding_first_upload_done = s.onboarding_first_upload_done
        FROM event_creator.user_settings s
        WHERE s.user_id = u.id
        """
    )

    op.drop_table("user_settings", schema="event_creator")
