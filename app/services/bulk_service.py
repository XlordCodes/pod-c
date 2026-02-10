# app/services/bulk_service.py
"""
Module: Bulk Messaging Service
Context: Pod C - Marketing & Broadcasts

Manages the lifecycle of high-volume broadcast jobs.
Integrates with the WhatsApp Client for transmission and maintains
detailed audit logs of delivery status.
"""

import time
import logging
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.bulk import BulkJob, BulkMessage
# Import Unified Client
from app.integrations.whatsapp_client import whatsapp_client

logger = logging.getLogger(__name__)

class BulkService:
    """
    Service for handling high-volume messaging campaigns.
    Designed to be resilient to crashes and compliant with rate limits.
    """
    def __init__(self, db: Session):
        self.db = db

    def create_job(
        self, 
        tenant_id: int, 
        template_name: str, 
        language_code: str, 
        components: Optional[List[dict]], 
        numbers: List[str],
        scheduled_at: Optional[datetime] = None,
        status: str = "queued"
    ) -> BulkJob:
        """
        Creates a new bulk job and queues messages using high-performance Batch Insert.
        
        Args:
            tenant_id (int): Security context.
            template_name (str): WhatsApp template ID.
            language_code (str): e.g., 'en_US'.
            components (list): Dynamic parameters for the template.
            numbers (list): List of destination phone numbers.
            scheduled_at (datetime): Optional execution time.
            status (str): Initial status ('queued' or 'scheduled').
            
        Returns:
            BulkJob: The created job instance.
        """
        try:
            # 1. Create the Job Parent
            job = BulkJob(
                tenant_id=tenant_id,
                template_name=template_name,
                language_code=language_code,
                components=components,
                status=status,              
                scheduled_at=scheduled_at   
            )
            self.db.add(job)
            self.db.flush() # Flush to generate the job.id required for child messages

            # 2. Performance Optimization: Bulk Insert
            # Mapping objects in memory is fast; DB round-trips are slow.
            # We construct all Message objects and save them in a single SQL operation.
            bulk_messages = [
                BulkMessage(
                    job_id=job.id, 
                    to_number=num, 
                    status="pending"
                ) 
                for num in numbers
            ]
            
            # This is ~100x faster than a loop for large lists
            self.db.bulk_save_objects(bulk_messages)

            # 3. Commit Transaction
            # This makes the job visible to the Celery Worker.
            self.db.commit()
            self.db.refresh(job)
            
            logger.info(f"Created Bulk Job {job.id} with {len(numbers)} messages (Status: {status})")
            return job

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to create bulk job: {e}")
            raise e

    def run_job(self, job_id: int) -> Optional[BulkJob]:
        """
        Executes a queued job by iterating through pending messages and sending them.
        
        Design Note:
        - This is typically called by a background worker (Celery).
        - Uses 'Batch Processing' to manage memory.
        - Uses 'Incremental Commits' to save progress (Checkpointing).
        """
        # 1. Fetch Job
        job = self.db.get(BulkJob, job_id)
        if not job:
            logger.error(f"Job {job_id} not found.")
            return None

        # 2. Update Status to Running
        job.status = "running"
        self.db.commit()

        # Extract static job details to avoid re-fetching
        template_name = job.template_name
        language_code = job.language_code
        components = job.components

        logger.info(f"Starting execution of Bulk Job {job_id}")

        while True:
            # 3. Fetch Batch (Limit 50 to balance speed vs risk)
            # We select only 'pending' messages. This acts as a cursor.
            msgs = (
                self.db.query(BulkMessage)
                .filter(BulkMessage.job_id == job_id, BulkMessage.status == "pending")
                .limit(50)
                .all()
            )
            
            if not msgs:
                # No more pending messages, job is done.
                break

            for m in msgs:
                try:
                    # 4. Send Message (Sync Call)
                    # Relies on the client's internal retry logic for transient network errors.
                    whatsapp_client.send_template_sync(
                        to_number=m.to_number, 
                        template_name=template_name, 
                        language=language_code, 
                        components=components
                    )
                    m.status = "sent"
                    
                except Exception as e:
                    # Capture the failure but DO NOT stop the job.
                    # Individual failure should not block the campaign.
                    error_msg = str(e)
                    logger.warning(f"Job {job_id}: Failed to send to {m.to_number}. Error: {error_msg}")
                    
                    m.attempts += 1
                    m.status = "failed"
                    m.last_error = error_msg
            
            # 5. Checkpoint: Commit this batch
            # If the worker crashes here, we only lose the processing status of the last 50 messages,
            # not the whole job.
            try:
                self.db.commit()
                # Basic throttle to be a good API citizen (can be adjusted based on tier)
                time.sleep(1) 
            except SQLAlchemyError as db_err:
                logger.error(f"Job {job_id}: DB Commit failed for batch: {db_err}")
                self.db.rollback()
                # If DB is down, we must abort the loop to prevent infinite loops on the same batch
                break

        # 6. Finalize Job
        job.status = "completed"
        self.db.commit()
        self.db.refresh(job)
        
        logger.info(f"Bulk Job {job_id} execution completed.")
        return job