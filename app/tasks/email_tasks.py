# app/tasks/email_tasks.py
"""
Module: Email Background Tasks
Context: Pod C - Async Notifications

Processes the Email Queue.
Decouples the API (fast response) from the SMTP/SendGrid layer (slow/flaky).
"""

import logging
from app.core.celery_app import celery_app
from app.database import SessionLocal
from app.models.bulk import EmailQueue
from app.services.email_service import Emailer

logger = logging.getLogger(__name__)

@celery_app.task(name="send_email_task", bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, email_job_id: int):
    """
    Celery task to process a specific email job from the DB queue.
    
    Args:
        email_job_id (int): Primary Key of the EmailQueue record.
    """
    db = SessionLocal()
    try:
        # 1. Fetch Job
        email_job = db.query(EmailQueue).filter(EmailQueue.id == email_job_id).first()
        
        if not email_job:
            logger.error(f"Email Task: Job {email_job_id} not found in DB.")
            return

        # 2. Initialize Service
        # The Emailer handles the SendGrid connection and template rendering
        emailer = Emailer()
        
        # 3. Attempt Delivery
        try:
            emailer.send_mail(
                to_email=email_job.to_email,
                subject=email_job.subject,
                template_name=email_job.template_name,
                context=email_job.context
            )
            
            # 4. Success Path
            email_job.status = "sent"
            # Reset error log if it succeeded after a retry
            email_job.last_error = None 
            logger.info(f"Email Task: Job {email_job_id} sent successfully.")
            
        except Exception as e:
            # 5. Failure Path
            logger.error(f"Email Task: Job {email_job_id} failed: {e}")
            
            email_job.last_error = str(e)
            email_job.attempts += 1
            
            # If we have retries left, the status remains 'pending' (or 'retrying')
            # If we are out of retries, we mark it 'failed'.
            if self.request.retries >= self.max_retries:
                email_job.status = "failed"
            
            # Commit the attempt count/error before retrying
            db.commit()
            
            # Trigger Celery Retry
            raise self.retry(exc=e)

        # Commit final success state
        db.commit()

    except Exception as e:
        # Catch-all for DB errors or other critical failures
        logger.critical(f"Email Task Critical Error: {e}")
        # We don't retry DB connection errors indefinitely to avoid hammering the DB
    finally:
        db.close()