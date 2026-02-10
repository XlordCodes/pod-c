# app/tasks/whatsapp_tasks.py
"""
Module: WhatsApp Background Tasks
Context: Pod C - Async Workers

Defines Celery tasks for executing long-running bulk messaging jobs.
Acts as the bridge between the Message Broker (Redis) and the Domain Service.
"""

import logging
from app.core.celery_app import celery_app
from app.database import SessionLocal
from app.services.bulk_service import BulkService
from app.models.bulk import BulkJob

logger = logging.getLogger(__name__)

@celery_app.task(name="process_bulk_whatsapp_job", bind=True, max_retries=1)
def process_bulk_whatsapp_job(self, job_id: int):
    """
    Celery task to execute a Bulk Job.
    
    Args:
        job_id (int): ID of the BulkJob to process.
    """
    # Create a new DB session for this specific task execution
    db = SessionLocal()
    
    try:
        logger.info(f"Worker: Starting Bulk Job {job_id}")
        
        # Initialize Service
        svc = BulkService(db)
        
        # Execute Logic
        # The service handles the iteration, sending, and per-message error logging.
        job = svc.run_job(job_id)
        
        if not job:
            logger.error(f"Worker: Job {job_id} not found in DB.")
            return "Job Not Found"
            
        logger.info(f"Worker: Bulk Job {job_id} finished with status: {job.status}")
        return f"Completed: {job.status}"
        
    except Exception as e:
        logger.critical(f"Worker: Bulk Job {job_id} CRASHED. Error: {e}")
        
        # Failsafe: Mark job as failed if the code crashes
        # otherwise it will look like it's "running" forever in the UI.
        try:
            job = db.get(BulkJob, job_id)
            if job:
                job.status = "failed"
                db.commit()
        except:
            # If DB is down, there's nothing we can do but log it.
            logger.error("Worker: Could not update job status to failed due to DB error.")
            pass 
            
        # Re-raise to ensure Celery marks the task as failed in Redis
        # Countdown=60 gives the system a minute to recover before (optionally) retrying
        raise self.retry(exc=e, countdown=60)
        
    finally:
        # Always close the session to return the connection to the pool
        db.close()