import time
import logging
from sqlalchemy.orm import Session
from app.models import BulkJob, BulkMessage
from app.integrations.whatsappclient import send_template
from tenacity import retry, wait_exponential, stop_after_attempt

# Note: We are reverting the custom tenacity logger in favor of the clean structural fix.

class BulkService:
    def __init__(self, db: Session):
        self.db = db

    def create_job(self, template_name: str, language_code: str, components: list[dict] | None, numbers: list[str]) -> BulkJob:
        """
        Create a bulk job, storing the full template configuration.
        """
        job = BulkJob(
            template_name=template_name,
            language_code=language_code,
            components=components,
            status="queued"
        )
        self.db.add(job)
        self.db.flush()

        for num in numbers:
            self.db.add(BulkMessage(job_id=job.id, to_number=num))

        self.db.commit()
        self.db.refresh(job)
        return job

    @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3)) # Faster retries for testing
    def _send_one(self, to_number: str, template_name: str, language_code: str, components: list[dict] | None):
        """
        Wrapper around send_template with retries. Uses all template parameters.
        The standalone client function uses 'language' as parameter name.
        """
        return send_template(to_number, template_name, language=language_code, components=components)

    def run_job(self, job_id: int) -> BulkJob | None:
        """
        Runs the bulk job, processing messages in batches.
        """
        job = self.db.get(BulkJob, job_id)
        if not job:
            return None

        job.status = "running"
        self.db.commit()

        # Unpack configuration from job object
        template_name = job.template_name
        language_code = job.language_code
        components = job.components

        while True:
            msgs = (
                self.db.query(BulkMessage)
                .filter(BulkMessage.job_id == job_id, BulkMessage.status == "pending")
                .limit(10) # Fixed batch size
                .all()
            )
            if not msgs:
                break

            for m in msgs:
                try:
                    self._send_one(m.to_number, template_name, language_code, components)
                    m.status = "sent"
                except Exception as e:
                    error_message = repr(e) 
                    logging.error(f"Job {job_id}: Failed to send to {m.to_number}. Error: {error_message}")
                    
                    m.attempts += 1
                    m.status = "failed"
                    m.last_error = error_message
                
                try:
                    self.db.commit() # Commit after each message
                except Exception as db_err:
                    logging.error(f"Job {job_id}: DB Commit failed for message {m.id}: {db_err}")
                    self.db.rollback()
            
            time.sleep(2)

        job.status = "done"
        self.db.commit()
        self.db.refresh(job)
        return job