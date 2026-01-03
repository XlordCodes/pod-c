# app/api/emailer.py
import logging
from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, EmailQueue
from app.authentication.router import get_current_user

# Import the task for async processing
from app.tasks.email_tasks import send_email_task

logger = logging.getLogger(__name__)

class EmailPayload(BaseModel):
    to_email: str
    subject: str
    template_name: str
    context: Optional[Dict] = {}

router = APIRouter()

@router.post("/send-email")
def send_email_handler(
    data: EmailPayload, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user) # Security Check
):
    """
    Queues an email for reliable background delivery via Celery.
    Persists request to DB so it survives server restarts.
    """
    try:
        # 1. Persist Request (Reliability)
        email_job = EmailQueue(
            to_email=data.to_email,
            subject=data.subject,
            template_name=data.template_name,
            context=data.context,
            status="pending"
        )
        db.add(email_job)
        db.commit()
        db.refresh(email_job)
        
        # 2. Dispatch Task (Async)
        # We pass the ID, not the object, because Celery uses a separate DB session
        send_email_task.delay(email_job.id)
        
        return {"status": "queued", "job_id": email_job.id}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to queue email: {str(e)}")