# app/api/bulk.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

# --- Imports ---
from app.database import get_db
from app.models import BulkJob, BulkMessage, User
from app.schemas.bulk import BulkJobCreate, BulkJobResponse, BulkJobStatus
from app.authentication.router import get_current_user

# Import the Celery task
from app.tasks.whatsapp_tasks import process_bulk_whatsapp_job

# Clean router (no tags/prefix here, handled in router.py)
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
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="User is not associated with a valid tenant."
        )

    # 1. Determine Initial Status
    initial_status = "queued"
    
    if job_request.scheduled_at:
        # Check if time is in the future
        now = datetime.now(timezone.utc)
        target = job_request.scheduled_at
        
        # Ensure timezone awareness for comparison
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)

        if target > now:
            initial_status = "scheduled"
        else:
            # If date is in the past, default to immediate execution
            initial_status = "queued"

    # 2. Create the Parent Job Record
    # We explicitly bind this job to the current user's tenant_id
    new_job = BulkJob(
        tenant_id=current_user.tenant_id,
        template_name=job_request.template_name,
        language_code=job_request.language_code,
        status=initial_status,
        scheduled_at=job_request.scheduled_at,
        components=getattr(job_request, "components", []) 
    )
    db.add(new_job)
    db.flush() # Generate ID for foreign keys

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
    
    # If scheduled, the periodic Celery Beat task will pick it up later.

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
        
    if hasattr(job, "tenant_id") and job.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job