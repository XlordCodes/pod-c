from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db 
from app.schemas.bulk import BulkJobCreate, BulkJobStatus, BulkJobResponse
from app.services.bulk_service import BulkService
from app.models import BulkJob

router = APIRouter(prefix="/bulk", tags=["Bulk Messaging"])

# ----------------------------
# Create a new bulk job
# ----------------------------
@router.post("/jobs", response_model=BulkJobResponse)
def create_job(job_in: BulkJobCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Create a new bulk messaging job, including full template configuration.
    """
    service = BulkService(db)
    job = service.create_job(
        template_name=job_in.template_name,
        language_code=job_in.language_code,
        components=job_in.components,
        numbers=job_in.numbers
    )
    
    background_tasks.add_task(service.run_job, job.id)
    
    # We return the new fields in the response
    return {
        "id": job.id,
        "template_name": job.template_name,
        "language_code": job.language_code,
        "components": job.components,
        "status": job.status,
        "created_at": job.created_at,
        "numbers": job_in.numbers,
    }

# ----------------------------
# Get job status (remains simple)
# ----------------------------
@router.get("/jobs/{job_id}", response_model=BulkJobStatus)
def job_status(job_id: int, db: Session = Depends(get_db)):
    """
    Get the status of a specific bulk job and all its messages.
    """
    job = db.get(BulkJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job