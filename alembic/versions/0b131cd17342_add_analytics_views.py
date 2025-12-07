"""add_analytics_views

Revision ID: 0b131cd17342
Revises: 8ef9d8f35b89
Create Date: 2025-12-07 08:12:14.400713

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b131cd17342'
down_revision: Union[str, Sequence[str], None] = '8ef9d8f35b89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
