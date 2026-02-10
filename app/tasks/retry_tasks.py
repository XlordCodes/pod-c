# app/tasks/retry_tasks.py
"""
Module: Retry Worker
Context: Pod C - Async Infrastructure

A dedicated periodic task that acts as a 'Dead Letter Queue' processor.
It scans for messages stuck in 'failed' state and retries them automatically.
"""

import logging
from sqlalchemy.orm import joinedload
from app.core.celery_app import celery_app
from app.database import SessionLocal
from app.models.bulk import BulkMessage
from app.integrations.whatsapp_client import whatsapp_client

logger = logging.getLogger(__name__)

# Constants
MAX_RETRIES = 3

@celery_app.task(name="retry_failed_bulk_messages")
def retry_failed_bulk_messages():
    """
    Periodic Task: Scans for failed bulk messages and retries them.
    """
    db = SessionLocal()
    try:
        # 1. Fetch candidates (Status=failed, Attempts < Max)
        # We use joinedload(BulkMessage.job) to fetch the template details in the SAME query.
        failed_msgs = (
            db.query(BulkMessage)
            .options(joinedload(BulkMessage.job))
            .filter(
                BulkMessage.status == "failed",
                BulkMessage.attempts < MAX_RETRIES
            )
            .limit(50) # Batch size to prevent memory spikes
            .all()
        )

        if not failed_msgs:
            return

        logger.info(f"Retry Worker: Found {len(failed_msgs)} messages to retry.")

        success_count = 0
        
        for msg in failed_msgs:
            job = msg.job
            if not job:
                logger.error(f"Data Integrity Error: Message {msg.id} has no parent Job.")
                continue

            try:
                # 2. Attempt Resend
                # We interpret the existing error as transient and try again.
                logger.info(f"Retrying Message {msg.id} to {msg.to_number} (Attempt {msg.attempts + 1})")
                
                # Using the Sync client (safe for Celery)
                response = whatsapp_client.send_template_sync(
                    to_number=msg.to_number,
                    template_name=job.template_name,
                    language=job.language_code,
                    components=job.components
                )
                
                # 3. Success Path
                msg.status = "sent"
                
                # Extract the new WAMID from the response if available
                # Response format: {'messages': [{'id': 'wamid.HBg...'}]}
                if response and "messages" in response:
                     msg.whatsapp_message_id = response["messages"][0].get("id")

                msg.last_error = None # Clear error
                msg.attempts += 1
                success_count += 1
                
            except Exception as e:
                # 4. Failure Path
                msg.attempts += 1
                msg.last_error = f"Retry Error: {str(e)}"
                
                # If max reached, it stays 'failed' permanently (Dead Letter)
                if msg.attempts >= MAX_RETRIES:
                    logger.error(f"Message {msg.id} permanently failed after {MAX_RETRIES} attempts.")
                
            # Commit per message (or small batches) to avoid one failure rolling back all retries
            try:
                db.commit()
            except Exception as commit_err:
                logger.error(f"DB Commit failed for retry {msg.id}: {commit_err}")
                db.rollback()

        if success_count > 0:
            logger.info(f"Retry Worker: Successfully recovered {success_count} messages.")

    except Exception as e:
        logger.error(f"Critical Retry Worker Error: {e}")
    finally:
        db.close()