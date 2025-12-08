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
    # 1. View: Sentiment Mix
    # Calculates the count of each sentiment (positive, negative, neutral)
    op.execute("""
    CREATE OR REPLACE VIEW v_sentiment_mix AS
    SELECT 
        COALESCE(sentiment, 'unclassified') as sentiment, 
        COUNT(*) as count
    FROM chat_messages
    GROUP BY sentiment;
    """)

    # 2. View: Average Response Time
    # Uses Window Functions to calculate the time gap between messages in a thread
    op.execute("""
    CREATE OR REPLACE VIEW v_avg_response AS
    SELECT 
        c.id AS conversation_id,
        AVG(EXTRACT(EPOCH FROM (msg.created_at - prev_msg.created_at))) / 60 AS avg_gap_minutes
    FROM conversations c
    JOIN (
        SELECT 
            conversation_id, 
            created_at,
            LAG(created_at) OVER (PARTITION BY conversation_id ORDER BY created_at) as prev_created_at
        FROM chat_messages
    ) msg ON c.id = msg.conversation_id
    JOIN chat_messages prev_msg ON prev_msg.created_at = msg.prev_created_at
    GROUP BY c.id;
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_avg_response;")
    op.execute("DROP VIEW IF EXISTS v_sentiment_mix;")