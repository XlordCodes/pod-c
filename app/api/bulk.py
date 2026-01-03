# app/api/bulk.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone

# --- Imports ---
from app.database import get_db
from app.models import BulkJob, BulkMessage, User 
from app.schemas.bulk import BulkJobCreate, BulkJobResponse, BulkJobStatus
from app.authentication.router import get_current_user

# Import the Celery task
from app.tasks.whatsapp_tasks import process_bulk_whatsapp_job

router = APIRouter(tags=["Bulk Messaging"])

@router.post("/jobs", response_model=BulkJobResponse, status_code=201)
def create_bulk_job(
    job_request: BulkJobCreate, 
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user) # Uncomment when auth is ready
):
    """
    Creates a bulk messaging job record.
    If 'scheduled_at' is provided and is in the future, the job is saved as 'scheduled'.
    Otherwise, it is 'queued' and processed immediately by the worker.
    """
    # 1. Determine Initial Status
    initial_status = "queued"
    
    if job_request.scheduled_at:
        # Check if time is in the future
        now = datetime.now(timezone.utc)
        target = job_request.scheduled_at
        
        # If input has no timezone, assume UTC to make it comparable
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)

        if target > now:
            initial_status = "scheduled"
        else:
            # If date is in the past, just send it now
            initial_status = "queued"

    # 2. Create the Parent Job Record
    new_job = BulkJob(
        template_name=job_request.template_name,
        language_code=job_request.language_code,
        status=initial_status,
        scheduled_at=job_request.scheduled_at, # Save the schedule time
        components=getattr(job_request, "components", []) 
    )
    db.add(new_job)
    db.flush() # Generate ID

    # 3. Create Child Message Records
    messages_objects = []
    for number in job_request.numbers:
        msg = BulkMessage(
            job_id=new_job.id,
            to_number=number,
            status="pending"
        )
        messages_objects.append(msg)
    
    db.add_all(messages_objects)
    
    # 4. Commit to DB
    db.commit()
    db.refresh(new_job)

    # 5. Trigger Celery Task (Conditional)
    if initial_status == "queued":
        # Run immediately if not scheduled for later
        process_bulk_whatsapp_job.delay(new_job.id)
    else:
        # If scheduled, do NOTHING here.
        # The Celery Beat scheduler will pick this up when the time comes.
        pass

    # 6. Return Response
    # Returning the ORM object; Pydantic response_model will handle serialization
    return new_job

@router.get("/jobs/{job_id}", response_model=BulkJobStatus)
def get_job_status(
    job_id: int, 
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user)
):
    """
    Get the status and message details of a bulk job.
    """
    job = db.get(BulkJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job