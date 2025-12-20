"""add_message_id_to_chat

Revision ID: a0b9f85b42b6
Revises: 0b131cd17342
Create Date: 2025-12-20 11:33:12.785811

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0b9f85b42b6'
down_revision: Union[str, Sequence[str], None] = '0b131cd17342'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('chat_messages', sa.Column('message_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_chat_messages_message_id'), 'chat_messages', ['message_id'], unique=True)

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_chat_messages_message_id'), table_name='chat_messages')
    op.drop_column('chat_messages', 'message_id')