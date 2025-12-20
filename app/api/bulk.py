# app/api/bulk.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

# --- Imports ---
from app.database import get_db
from app.models import BulkJob, BulkMessage, User 
from app.schemas.bulk import BulkJobCreate, BulkJobResponse, BulkJobStatus
from app.authentication.router import get_current_user

router = APIRouter(tags=["Bulk Messaging"])

@router.post("/jobs", response_model=BulkJobResponse, status_code=201)
def create_bulk_job(
    job_request: BulkJobCreate, 
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user) # Uncomment when auth is ready
):
    """
    Creates a bulk messaging job record.
    The separate Worker container (worker-1) will automatically pick this up,
    send the messages, and update the status.
    """
    # 1. Create the Parent Job Record
    new_job = BulkJob(
        template_name=job_request.template_name,
        language_code=job_request.language_code,
        status="queued",
        # We save components if they exist (supported by your schema)
        components=getattr(job_request, "components", []) 
    )
    db.add(new_job)
    db.flush() # Flush to generate new_job.id so we can use it below

    # 2. Create the Child Message Records
    # These are the actual rows the Worker will process.
    messages_objects = []
    for number in job_request.numbers:
        msg = BulkMessage(
            job_id=new_job.id,
            to_number=number,
            status="pending" # Worker will change this to 'sent'/'failed'
        )
        messages_objects.append(msg)
    
    db.add_all(messages_objects)
    
    # 3. Commit everything
    db.commit()
    db.refresh(new_job)

    # 4. Return Response
    return {
        "id": new_job.id,
        "template_name": new_job.template_name,
        "language_code": new_job.language_code,
        "status": new_job.status,
        "created_at": new_job.created_at,
        "numbers": job_request.numbers,
        "components": new_job.components
    }

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