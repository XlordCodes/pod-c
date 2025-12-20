# app/services/bulk_service.py
import time
import logging
from sqlalchemy.orm import Session
from app.models import BulkJob, BulkMessage
from app.integrations.whatsappclient import send_template
from tenacity import retry, wait_exponential, stop_after_attempt

logger = logging.getLogger(__name__)

class BulkService:
    def __init__(self, db: Session):
        self.db = db

    def create_job(self, template_name: str, language_code: str, components: list[dict] | None, numbers: list[str]) -> BulkJob:
        """
        Creates a new bulk job and creates pending messages using BATCH INSERT.
        """
        # 1. Create the Job Parent
        job = BulkJob(
            template_name=template_name,
            language_code=language_code,
            components=components,
            status="queued"
        )
        self.db.add(job)
        self.db.flush() # Flush to get the job.id

        # 2. Performance Optimization: Bulk Insert Messages
        # Instead of adding one by one, we map them and save in one go.
        bulk_messages = [
            BulkMessage(job_id=job.id, to_number=num, status="pending") 
            for num in numbers
        ]
        
        # This is ~100x faster than a loop for large lists
        self.db.bulk_save_objects(bulk_messages)

        self.db.commit()
        self.db.refresh(job)
        return job

    @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
    def _send_one(self, to_number: str, template_name: str, language_code: str, components: list[dict] | None):
        return send_template(to_number, template_name, language=language_code, components=components)

    def run_job(self, job_id: int) -> BulkJob | None:
        # (Existing logic remains valid for processing)
        job = self.db.get(BulkJob, job_id)
        if not job:
            return None

        job.status = "running"
        self.db.commit()

        template_name = job.template_name
        language_code = job.language_code
        components = job.components

        while True:
            # Process in batches
            msgs = (
                self.db.query(BulkMessage)
                .filter(BulkMessage.job_id == job_id, BulkMessage.status == "pending")
                .limit(10)
                .all()
            )
            if not msgs:
                break

            for m in msgs:
                try:
                    self._send_one(m.to_number, template_name, language_code, components)
                    m.status = "sent"
                except Exception as e:
                    error_message = str(e)
                    logger.error(f"Job {job_id}: Failed to send to {m.to_number}. Error: {error_message}")
                    m.attempts += 1
                    m.status = "failed"
                    m.last_error = error_message
                
                try:
                    self.db.commit() 
                except Exception as db_err:
                    logger.error(f"Job {job_id}: DB Commit failed for message {m.id}: {db_err}")
                    self.db.rollback()
            
            time.sleep(2) # Throttle

        job.status = "done"
        self.db.commit()
        self.db.refresh(job)
        return job