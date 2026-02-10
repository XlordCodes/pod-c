# app/tasks/scheduler.py
"""
Module: Periodic Scheduler
Context: Pod C - Async Infrastructure

This module is registered in the Celery Beat schedule (celery_app.py).
It acts as a 'Cron' trigger for time-sensitive events like scheduled broadcasts.
"""

import logging
from datetime import datetime, timezone
from app.core.celery_app import celery_app
from app.database import SessionLocal
from app.models.bulk import BulkJob
from app.tasks.whatsapp_tasks import process_bulk_whatsapp_job

logger = logging.getLogger(__name__)

@celery_app.task(name="check_scheduled_jobs")
def check_scheduled_jobs():
    """
    Periodic Task: Runs every minute (configured in celery_app).
    Checks DB for jobs with status='scheduled' and scheduled_at <= NOW.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        
        # 1. Find Due Jobs
        # We look for 'scheduled' jobs whose time has passed.
        due_jobs = db.query(BulkJob).filter(
            BulkJob.status == "scheduled",
            BulkJob.scheduled_at <= now
        ).all()
        
        if not due_jobs:
            return 
            
        logger.info(f"Scheduler: Found {len(due_jobs)} due jobs.")
        
        for job in due_jobs:
            try:
                # 2. State Change (Atomic)
                # We mark it as 'queued' immediately so the next scheduler run 
                # (in 1 min) doesn't pick it up again if the worker is slow.
                job.status = "queued"
                db.commit()
                
                # 3. Dispatch to Worker
                process_bulk_whatsapp_job.delay(job.id)
                logger.info(f"Scheduler: Dispatched Job {job.id} to Worker Queue")
                
            except Exception as inner_e:
                logger.error(f"Scheduler: Failed to dispatch Job {job.id}: {inner_e}")
                # Rollback only affects the current job loop
                db.rollback()

    except Exception as e:
        logger.error(f"Scheduler Critical Error: {e}")
    finally:
        db.close()