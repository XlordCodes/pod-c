# tests/integration/test_ai_pipeline.py
"""
Module: AI Pipeline Integration Test
Context: Pod C - End-to-End verification of the "Brain".

Verifies that:
1. Messages are saved correctly by ChatService.
2. The AI Worker Task (process_message_ai) runs without error.
3. Sentiment and Embeddings are updated in the Database.
"""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from app.models import ChatMessage, MessageEmbedding
from app.services.chat_service import ChatService
from app.tasks.ai_tasks import process_message_ai

# Mark test as sync because we are calling the task function directly
def test_ai_task_flow(db_session: Session):
    """
    Test the full AI pipeline (Save -> NLP -> Sentiment -> Embedding)
    Mocking external AI APIs to avoid costs/latency.
    """
    # --- 1. SETUP: Create a Message via ChatService ---
    chat_svc = ChatService(db_session)
    msg = chat_svc.save_incoming(
        from_number="+919999999999",
        text="I am very unhappy with the delay in my order."
    )
    
    # Commit to ensure ID is stable and row exists for the new session created by the task
    db_session.commit()

    # --- 2. SETUP MOCKS (Bypass Real AI & Patch DB) ---
    
    # Mock Sentiment Analysis Result (HuggingFace Pipeline)
    mock_sentiment_result = [{"label": "NEGATIVE", "score": 0.99}]
    
    mock_vector = [0.1] * 1536
    
    mock_embedding_response = {
        "data": [
            {
                "embedding": mock_vector,
                "index": 0,
                "object": "embedding"
            }
        ],
        "usage": {"prompt_tokens": 5, "total_tokens": 5}
    }
    
    # Create a callable mock for the sentiment pipeline
    mock_analyzer = MagicMock(return_value=mock_sentiment_result)
    
    # Patch 'get_pipeline' instead of the internal variable
    with patch("app.tasks.ai_tasks.SessionLocal", return_value=db_session), \
         patch("app.services.sentiment_service.get_pipeline", return_value=mock_analyzer), \
         patch("app.services.embedding_service.requests.post") as mock_post:
        
        # Configure the Embedding Mock
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_embedding_response

        # --- 3. EXECUTE: Run the Celery Task Synchronously ---
        process_message_ai(msg.id)

    # --- 4. VERIFICATION ---
    
    msg = db_session.query(ChatMessage).filter(ChatMessage.id == msg.id).first()
    assert msg is not None, "Message should exist in DB"
    
    print(f"DEBUG: Message Sentiment is: {msg.sentiment}")
    
    # Verify Sentiment (Updated by SentimentService)
    assert msg.sentiment.lower() == "negative", "Sentiment should be updated to 'negative'"

    # Verify Embedding (Created by EmbeddingService)
    embedding = db_session.query(MessageEmbedding).filter_by(message_id=msg.id).first()
    assert embedding is not None, "Embedding row should be created"
    
    # Verify vector dimensions
    assert len(embedding.embedding) == 1536, "Vector dimension should be 1536"
    
    # Verify vector content
    assert embedding.embedding[0] == pytest.approx(0.1, abs=1e-5)