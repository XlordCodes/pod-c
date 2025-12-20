"""add_created_at_to_replies

Revision ID: 09544dc12606
Revises: a0b9f85b42b6
Create Date: 2025-12-20 12:08:51.014497

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '09544dc12606'
down_revision: Union[str, Sequence[str], None] = 'a0b9f85b42b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('reply_suggestions', 
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('reply_suggestions', 'created_at')
