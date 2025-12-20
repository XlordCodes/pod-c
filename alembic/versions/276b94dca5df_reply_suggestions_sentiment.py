"""reply suggestions + sentiment

Revision ID: 276b94dca5df
Revises: c006d97291ec
Create Date: 2025-11-19 17:04:32.429138

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '276b94dca5df'
down_revision: Union[str, Sequence[str], None] = 'c006d97291ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('reply_suggestions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=True),
        sa.Column('suggestion', sa.Text(), nullable=True),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['message_id'], ['chat_messages.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.add_column('chat_messages', sa.Column('sentiment', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chat_messages', 'sentiment')
    op.drop_table('reply_suggestions')