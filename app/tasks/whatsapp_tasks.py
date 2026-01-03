# app/tasks/whatsapp_tasks.py
import logging
from app.core.celery_app import celery_app
from app.database import SessionLocal
from app.services.bulk_service import BulkService

logger = logging.getLogger(__name__)

@celery_app.task(name="process_bulk_whatsapp_job")
def process_bulk_whatsapp_job(job_id: int):
    """
    Celery task to execute a Bulk Job.
    Delegates the actual sending logic to BulkService.
    """
    db = SessionLocal()
    try:
        logger.info(f"Task: Starting Bulk Job {job_id}")
        
        # Initialize Service with the task's DB session
        svc = BulkService(db)
        
        # Execute the job (Iterates through messages and sends them)
        svc.run_job(job_id)
        
        logger.info(f"Task: Bulk Job {job_id} processing complete.")
        
    except Exception as e:
        logger.error(f"Task: Bulk Job {job_id} encountered critical error: {e}")
        # Note: BulkService is expected to handle individual message errors
        # and update the Job status to 'failed' if necessary.
        
    finally:
        db.close()