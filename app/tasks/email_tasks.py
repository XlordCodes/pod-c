# app/tasks/email_tasks.py
import logging
from app.core.celery_app import celery_app
from app.database import SessionLocal
from app.models import EmailQueue

# FIX: Import from Service, not API, to break circular dependency
from app.services.email_service import Emailer

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, email_job_id: int):
    """
    Celery task to process a specific email job from the DB queue.
    """
    db = SessionLocal()
    try:
        # 1. Fetch Job
        email_job = db.query(EmailQueue).filter(EmailQueue.id == email_job_id).first()
        
        if not email_job:
            logger.error(f"Email Job {email_job_id} not found.")
            return

        # 2. Initialize Sender
        emailer = Emailer()
        
        # 3. Send
        try:
            emailer.send_mail(
                to_email=email_job.to_email,
                subject=email_job.subject,
                template_name=email_job.template_name,
                context=email_job.context
            )
            email_job.status = "sent"
            logger.info(f"Task: Email {email_job_id} sent successfully.")
            
        except Exception as e:
            email_job.status = "failed"
            email_job.last_error = str(e)
            email_job.attempts += 1
            logger.error(f"Task: Email {email_job_id} failed: {e}")
            
            # Retry logic via Celery
            raise self.retry(exc=e)

        db.commit()

    except Exception as e:
        logger.error(f"Critical Worker Error: {e}")
    finally:
        db.close()