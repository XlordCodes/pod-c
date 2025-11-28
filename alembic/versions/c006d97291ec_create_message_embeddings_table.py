"""create message_embeddings table

Revision ID: c006d97291ec
Revises: 025185cb33cc
Create Date: 2025-11-19 20:17:34.711461

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR # Critical import

# revision identifiers, used by Alembic.
# KEEP THESE VALUES AS THEY ARE IN YOUR FILE
revision: str = 'c006d97291ec' 
down_revision: Union[str, Sequence[str], None] = 'f65604e27b22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the message_embeddings table manually."""
    op.create_table('message_embeddings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        # using 1024 dimensions for Cohere
        sa.Column('vector', VECTOR(1024), nullable=True), 
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['message_id'], ['chat_messages.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Drop the table."""
    op.drop_table('message_embeddings')