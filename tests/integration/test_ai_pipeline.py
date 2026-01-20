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
    
    # Commit to ensure ID is stable and row exists for the new session
    db_session.flush()

    # --- 2. SETUP MOCKS (Bypass Real AI & Patch DB) ---
    
    mock_sentiment_result = [{"label": "NEGATIVE", "score": 0.99}]
    
    # Fake vector with correct dimensions (1024)
    mock_embedding_response = {
        "embeddings": [[0.1] * 1024]
    }
    
    # Prevent the task from closing the test session
    real_close = db_session.close
    db_session.close = MagicMock() 

    try:
        # Patch SessionLocal to use our kept-alive session
        with patch("app.tasks.ai_tasks.SessionLocal", return_value=db_session), \
             patch("app.services.sentiment_service.sentiment_pipeline", side_effect=lambda x: mock_sentiment_result), \
             patch("app.services.embedding_service.requests.post") as mock_post:
            
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_embedding_response

            # --- 3. EXECUTE: Run the Celery Task Synchronously ---
            process_message_ai(msg.id)

        # --- 4. VERIFICATION ---
        
        db_session.refresh(msg)
        
        print(f"DEBUG: Message Sentiment is: {msg.sentiment}")
        assert msg.sentiment == "negative", "Sentiment should be updated to 'negative'"

        embedding = db_session.query(MessageEmbedding).filter_by(message_id=msg.id).first()
        assert embedding is not None, "Embedding row should be created"
        
        # Verify vector dimensions
        assert len(embedding.embedding) == 1024, "Vector dimension should be 1024"
        
        # FIX: Use approximate comparison for floating point numbers
        assert embedding.embedding[0] == pytest.approx(0.1, abs=1e-5)

    finally:
        # Restore the real close method 
        db_session.close = real_close