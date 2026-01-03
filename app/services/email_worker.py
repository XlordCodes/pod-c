# app/services/email_worker.py
import time
import logging
from sqlalchemy import text
from app.database import SessionLocal
from app.models import EmailQueue
from app.api.emailer import Emailer 

# Configure logging
logger = logging.getLogger("email_worker")
logging.basicConfig(level=logging.INFO)

def process_email_queue():
    """
    Polls DB for pending emails and sends them via SendGrid.
    """
    emailer = Emailer()
    logger.info("📧 Email Worker Started...")
    
    while True:
        db = SessionLocal()
        try:
            # Fetch pending jobs
            jobs = db.query(EmailQueue)\
                     .filter(EmailQueue.status == "pending")\
                     .limit(10)\
                     .with_for_update(skip_locked=True)\
                     .all()
            
            if not jobs:
                db.commit()
                db.close()
                time.sleep(5) 
                continue

            for job in jobs:
                try:
                    logger.info(f"Processing Email Job {job.id} to {job.to_email}")
                    
                    emailer.send_mail(
                        to_email=job.to_email,
                        subject=job.subject,
                        template_name=job.template_name,
                        context=job.context
                    )
                    job.status = "sent"
                    
                except Exception as e:
                    logger.error(f"Failed Job {job.id}: {e}")
                    job.attempts += 1
                    job.last_error = str(e)
                    if job.attempts >= 3:
                        job.status = "failed"
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Worker Loop Error: {e}")
            db.rollback()
        finally:
            db.close()

if __name__ == "__main__":
    process_email_queue()