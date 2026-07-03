"""create llm_prompts table

Revision ID: d3e4f5a6b7c8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

import fastapi_users_db_sqlalchemy
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'llm_prompts',
        sa.Column('id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column('user_id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column('prompt_text', sa.Text(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='cascade'),
        sa.PrimaryKeyConstraint('id'),
        # One prompt per user.
        sa.UniqueConstraint('user_id', name='uq_llm_prompts_user_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('llm_prompts')
