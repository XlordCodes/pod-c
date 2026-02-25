"""add_v_avg_response_view

Revision ID: 367554740673
Revises: 6d7dbf50f1ab
Create Date: 2026-02-24 06:18:57.892281

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '367554740673'
down_revision: Union[str, Sequence[str], None] = '6d7dbf50f1ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE OR REPLACE VIEW v_avg_response AS 
        SELECT 
            conversation_id, 
            EXTRACT(EPOCH FROM MAX(created_at) - MIN(created_at)) / GREATEST(COUNT(*) - 1, 1) AS avg_response_seconds 
        FROM chat_messages 
        GROUP BY conversation_id
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP VIEW IF EXISTS v_avg_response")
