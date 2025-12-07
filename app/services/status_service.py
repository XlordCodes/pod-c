# app/services/status_service.py
"""
Module: Status Service
Context: Pod C - Module 6 (Reliability).

This service encapsulates all business logic regarding message delivery tracking.
It is responsible for processing webhook status updates (Sent/Delivered/Read)
and ensuring the database reflects the most current, accurate state.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models_status import MessageStatus
from app.models import ChatMessage

# Configure module-level logger
logger = logging.getLogger(__name__)

class StatusService:
    """
    Service class for managing MessageStatus records.
    Designed to be instantiated per-request with a database session.
    """

    def __init__(self, db: Session):
        """
        Args:
            db (Session): The SQLAlchemy database session for this request.
        """
        self.db = db

    def update_status(self, wamid: str, new_status: str, error: str = None) -> MessageStatus | None:
        """
        Process an incoming status update from a WhatsApp Webhook.

        This method implements 'Upsert' logic and handles out-of-order delivery events.

        Args:
            wamid (str): The unique WhatsApp Message ID (e.g., 'wamid.HBgL...').
            new_status (str): The new status reported by the webhook.
            error (str, optional): Error message if the status is 'failed'.

        Returns:
            MessageStatus: The updated or created status record.
            None: If the original message could not be found.
        """
        # 1. REAL LOOKUP: Find the original message using the WAMID
        # FIX APPLIED: Querying 'message_id' instead of 'from_number'
        chat_msg = self.db.query(ChatMessage).filter(ChatMessage.message_id == wamid).first()

        if not chat_msg:
            logger.warning(f"Status Update Ignored: Could not find ChatMessage for WAMID: {wamid}")
            return None

        # 2. Check for an existing status row for this specific message
        status_row = self.db.query(MessageStatus).filter(MessageStatus.message_id == chat_msg.id).first()

        if not status_row:
            # Case A: First time we are seeing a status for this message. Create the record.
            status_row = MessageStatus(
                message_id=chat_msg.id,
                wa_status=new_status,
                last_error=error
            )
            self.db.add(status_row)
            logger.info(f"Created new status record for Msg ID {chat_msg.id}: {new_status}")
        else:
            # Case B: Update existing status.
            # LOGIC CHECK: Prevent regression. If the message is already 'read',
            # do not overwrite it with 'delivered' (which might arrive late due to network lag).
            if status_row.wa_status == "read" and new_status == "delivered":
                logger.info(f"Ignoring out-of-order status '{new_status}' for Msg ID {chat_msg.id} (Current: 'read')")
                return status_row

            status_row.wa_status = new_status
            if error:
                status_row.last_error = error
            logger.info(f"Updated status for Msg ID {chat_msg.id} to {new_status}")

        # 3. Commit the transaction
        try:
            self.db.commit()
            self.db.refresh(status_row)
            return status_row
        except Exception as e:
            logger.error(f"Database commit failed during status update: {e}")
            self.db.rollback()
            raise

    def get_metrics(self) -> dict:
        """
        Aggregates delivery statistics for the dashboard.

        Returns:
            dict: A dictionary mapping status strings to counts.
                  Example: {'sent': 120, 'delivered': 115, 'read': 90, 'failed': 2}
        """
        # Efficient SQL Group By query to offload counting to the DB
        rows = self.db.query(
            MessageStatus.wa_status, func.count(MessageStatus.id)
        ).group_by(MessageStatus.wa_status).all()

        # Convert list of tuples [(status, count), ...] to a dictionary
        return {status: count for status, count in rows}