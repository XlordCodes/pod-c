"""message status tracking

Revision ID: 8ef9d8f35b89
Revises: 025185cb33cc
Create Date: 2025-12-06 10:09:28.438535

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR

# revision identifiers, used by Alembic.
revision: str = '8ef9d8f35b89'
down_revision: Union[str, Sequence[str], None] = '025185cb33cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    
    op.create_table('message_status',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('wa_status', sa.String(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_error', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['message_id'], ['chat_messages.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_message_status_message_id'), 'message_status', ['message_id'], unique=False)
    op.create_index(op.f('ix_message_status_wa_status'), 'message_status', ['wa_status'], unique=False)

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_message_status_wa_status'), table_name='message_status')
    op.drop_index(op.f('ix_message_status_message_id'), table_name='message_status')
    op.drop_table('message_status')