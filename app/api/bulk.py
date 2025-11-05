from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

# Correct dependency import for the database session
from app.database import get_db 

# Our new schemas
from app.schemas.bulk import (
    BulkJobCreate, 
    BulkJobStatus, 
    BulkJobResponse
)

# Our new service
from app.services.bulk_service import BulkService

# Models for DB querying
from app.models import BulkJob

router = APIRouter()

# ----------------------------
# Create a new bulk job
# ----------------------------
@router.post("/jobs", response_model=BulkJobResponse)
def create_job(job_in: BulkJobCreate, db: Session = Depends(get_db)):
    """
    Create a new bulk messaging job.
    
    - **template**: The name of the WhatsApp template to send.
    - **numbers**: A list of 'to' numbers in E.164 format.
    """
    service = BulkService(db)
    job = service.create_job(template=job_in.template, numbers=job_in.numbers)
    
    return {
        "job_id": job.id,
        "template": job.template,
        "status": job.status,
        "created_at": job.created_at,
        "numbers": job_in.numbers,
    }

# ----------------------------
# Get job status
# ----------------------------
@router.get("/jobs/{job_id}", response_model=BulkJobStatus)
def job_status(job_id: int, db: Session = Depends(get_db)):
    """
    Get the status of a specific bulk job and all its messages.
    """
    # Use .get() for efficient primary key lookup
    job = db.get(BulkJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Use the SQLAlchemy relationship 'job.messages'
    # This is more efficient than a separate query.
    return job