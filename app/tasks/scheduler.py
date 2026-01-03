# app/tasks/scheduler.py
import logging
from datetime import datetime, timezone
from app.core.celery_app import celery_app
from app.database import SessionLocal
from app.models import BulkJob
from app.tasks.whatsapp_tasks import process_bulk_whatsapp_job

logger = logging.getLogger(__name__)

@celery_app.task(name="check_scheduled_jobs")
def check_scheduled_jobs():
    """
    Periodic Task: Runs every minute.
    Checks DB for jobs with status='scheduled' and scheduled_at <= NOW.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        
        # Find due jobs
        due_jobs = db.query(BulkJob).filter(
            BulkJob.status == "scheduled",
            BulkJob.scheduled_at <= now
        ).all()
        
        if not due_jobs:
            return 
            
        logger.info(f"Scheduler: Found {len(due_jobs)} due jobs.")
        
        for job in due_jobs:
            # 1. Update status to prevent double-processing
            job.status = "queued"
            db.commit()
            
            # 2. Dispatch to the actual Worker
            process_bulk_whatsapp_job.delay(job.id)
            logger.info(f"Scheduler: Dispatched Job {job.id}")
            
    except Exception as e:
        logger.error(f"Scheduler Error: {e}")
    finally:
        db.close()