# app/api/bulk.py
"""
Module: Bulk Messaging API
Context: Pod C - Marketing & Broadcasts

Exposes endpoints to create and monitor broadcast campaigns.
Delegates logic to BulkService for performance and Celery for async execution.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

# --- Imports ---
from app.database import get_db
from app.models.auth import User
from app.models.bulk import BulkJob # Type hinting
from app.schemas.bulk import BulkJobCreate, BulkJobResponse, BulkJobStatus
from app.authentication.router import get_current_user
from app.services.bulk_service import BulkService

# Import the Celery task
from app.tasks.whatsapp_tasks import process_bulk_whatsapp_job

router = APIRouter()

@router.post("/jobs", response_model=BulkJobResponse, status_code=status.HTTP_201_CREATED)
def create_bulk_job(
    job_request: BulkJobCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a bulk messaging job record.
    Enforces authentication and assigns the job to the user's tenant.
    
    If 'scheduled_at' is in the past or null, the job triggers immediately.
    If in the future, it is saved as 'scheduled' (to be picked up by Celery Beat).
    """
    # 1. Security: Enforce Tenant Context
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="User is not associated with a valid tenant."
        )

    # 2. Logic: Determine Schedule
    # If a date is provided and is in the future, we mark it as 'scheduled'.
    # Otherwise, it defaults to 'queued' for immediate processing.
    initial_status = "queued"
    target_time = job_request.scheduled_at

    if target_time:
        now = datetime.now(timezone.utc)
        # Ensure target is timezone-aware
        if target_time.tzinfo is None:
            target_time = target_time.replace(tzinfo=timezone.utc)

        if target_time > now:
            initial_status = "scheduled"
        else:
            # Past/Current time means run now
            # We explicitly clear target_time so the Service sees it as immediate
            target_time = None 

    # 3. Execution: Delegate to Service
    # The Service handles the high-performance bulk insert of messages
    svc = BulkService(db)
    
    new_job = svc.create_job(
        tenant_id=current_user.tenant_id,
        template_name=job_request.template_name,
        language_code=job_request.language_code,
        components=getattr(job_request, "components", []),
        numbers=job_request.numbers,
        scheduled_at=target_time,
        status=initial_status
    )

    # 4. Async Trigger: Fire Celery Task
    # Only fire if it's meant to run immediately. 
    # Scheduled jobs are picked up by a separate "Beat" task (cron).
    if new_job.status == "queued":
        process_bulk_whatsapp_job.delay(new_job.id)

    return new_job

@router.get("/jobs/{job_id}", response_model=BulkJobStatus)
def get_job_status(
    job_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the status and message details of a bulk job.
    Enforces tenant isolation (users can only see their own organization's jobs).
    """
    job = db.get(BulkJob, job_id)
    
    # Security Check: Ensure job exists AND belongs to the user's tenant
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job