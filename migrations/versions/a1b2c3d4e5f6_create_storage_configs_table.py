"""create storage_configs table

Revision ID: a1b2c3d4e5f6
Revises: c9e4b9bec690
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

import fastapi_users_db_sqlalchemy
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c9e4b9bec690'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'storage_configs',
        sa.Column('id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column('user_id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column(
            'provider',
            sa.Enum('google_drive', 'dropbox', 's3', name='storage_provider'),
            nullable=False,
        ),
        sa.Column('folder_path', sa.String(), nullable=False),
        sa.Column('oauth_access_token', sa.String(), nullable=True),
        sa.Column('oauth_refresh_token', sa.String(), nullable=True),
        sa.Column('s3_access_key', sa.String(), nullable=True),
        sa.Column('s3_secret_key', sa.String(), nullable=True),
        sa.Column('s3_bucket_name', sa.String(), nullable=True),
        sa.Column('s3_region', sa.String(), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='cascade'),
        sa.PrimaryKeyConstraint('id'),
        # One active storage config per user.
        sa.UniqueConstraint('user_id', name='uq_storage_configs_user_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('storage_configs')
    # create_table auto-created the native PG enum type; drop_table leaves it behind, so drop it
    # explicitly to keep downgrade a clean inverse of upgrade.
    sa.Enum(name='storage_provider').drop(op.get_bind())
