import time
from sqlalchemy.orm import Session
from app.models import BulkJob, BulkMessage
from app.integrations.whatsapp_client import send_template
from tenacity import retry, wait_exponential, stop_after_attempt


class BulkService:
    def __init__(self, db: Session):
        self.db = db

    def create_job(self, template: str, numbers: list[str]) -> BulkJob:
        """
        Create a bulk job and associated messages.
        Returns the ORM BulkJob object.
        """
        # Create Job
        job = BulkJob(template=template, status="queued")
        self.db.add(job)
        self.db.flush()  # Assign job.id

        # Add Messages
        for num in numbers:
            self.db.add(BulkMessage(job_id=job.id, to_number=num))

        self.db.commit()
        self.db.refresh(job)

        return job  # return the ORM object

    @retry(wait=wait_exponential(min=1, max=60), stop=stop_after_attempt(5))
    def _send_one(self, to_number: str, template: str):
        """
        Wrapper around send_template with retries.
        """
        # CRITICAL: This assumes your WhatsApp client function is:
        # from app.integrations.whatsapp_client import send_template
        # If your function is named differently, update the import and call.
        return send_template(to_number, template)

    def run_job(self, job_id: int, batch_size: int = 10) -> BulkJob | None:
        """
        Run the bulk job:
        - Marks job as running
        - Sends messages in batches
        - Updates message status
        - Marks job as done
        Returns the ORM BulkJob object.
        """
        job = self.db.get(BulkJob, job_id)
        if not job:
            return None

        job.status = "running"
        self.db.commit()

        while True:
            msgs = (
                self.db.query(BulkMessage)
                .filter(BulkMessage.job_id == job_id, BulkMessage.status == "pending")
                .limit(batch_size)
                .all()
            )
            if not msgs:
                break

            for m in msgs:
                try:
                    self._send_one(m.to_number, job.template)
                    m.status = "sent"
                except Exception as e:
                    m.attempts += 1
                    m.status = "failed"
                    m.last_error = str(e)

            self.db.commit()
            time.sleep(2)  # pacing between batches

        job.status = "done"
        self.db.commit()
        self.db.refresh(job)

        return job  # return ORM object