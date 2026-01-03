# app/services/status_service.py
"""
Module: Message Status Management
Context: Pod C - Module 6 (Reliability & Delivery Receipts).

This service processes WhatsApp delivery receipts (webhooks).
It ensures we track the lifecycle (Sent -> Delivered -> Read) accurately
and handles idempotent updates (ignoring duplicates).
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import MessageStatus
from app.models import ChatMessage

logger = logging.getLogger(__name__)

class StatusService:
    def __init__(self, db: Session):
        self.db = db

    def update_status(self, wamid: str, new_status: str, error: str = None) -> MessageStatus | None:
        """
        Updates the delivery status of a message based on a webhook event.
        
        Args:
            wamid (str): WhatsApp Message ID (from the webhook).
            new_status (str): The new status (sent, delivered, read, failed).
            error (str, optional): Raw error message if failed.
        """
        # 1. Locate the original message
        # We link statuses to our internal ChatMessage via the WAMID
        chat_msg = self.db.query(ChatMessage).filter(ChatMessage.message_id == wamid).first()

        if not chat_msg:
            logger.warning(f"Status Update Ignored: Unknown WAMID {wamid}")
            return None

        # 2. Find or Create the Status Record (Upsert)
        status_row = self.db.query(MessageStatus).filter(MessageStatus.message_id == chat_msg.id).first()

        if not status_row:
            # Create new tracking record
            status_row = MessageStatus(
                message_id=chat_msg.id,
                wa_status=new_status,
                last_error=error
            )
            self.db.add(status_row)
            logger.info(f"Tracking started for Msg {chat_msg.id}: {new_status}")
        else:
            # Update existing record (Idempotency Check)
            # If current is 'read', ignore 'delivered' updates that arrive late
            if status_row.wa_status == "read" and new_status == "delivered":
                logger.debug(f"Ignoring stale status '{new_status}' for Msg {chat_msg.id}")
                return status_row

            status_row.wa_status = new_status
            if error:
                status_row.last_error = error
            
            logger.info(f"Status updated for Msg {chat_msg.id} -> {new_status}")

        # 3. Persist Changes
        try:
            self.db.commit()
            self.db.refresh(status_row)
            return status_row
        except Exception as e:
            logger.error(f"DB Commit failed for status update: {e}")
            self.db.rollback()
            raise

    def get_metrics(self) -> dict:
        """
        Aggregates current status counts for the dashboard.
        Used by the operational dashboard API.
        """
        # Perform aggregation in SQL for performance
        rows = self.db.query(
            MessageStatus.wa_status, func.count(MessageStatus.id)
        ).group_by(MessageStatus.wa_status).all()

        return {status: count for status, count in rows}