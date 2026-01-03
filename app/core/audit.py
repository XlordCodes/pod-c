# app/core/audit.py
import json
import logging
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session 
from app.database import SessionLocal
from app.models import AuditLog, User, Contact, BulkJob
from app.core.context import get_request_id, get_user_id

logger = logging.getLogger(__name__)

# List of models we want to track
AUDIT_MODELS = [User, Contact, BulkJob]

def object_as_dict(obj):
    """Convert SQLAlchemy model to dictionary, handling dates."""
    return {c.key: str(getattr(obj, c.key)) for c in inspect(obj).mapper.column_attrs}

def capture_audit_logs(session, flush_context, instances):
    """
    SQLAlchemy Event Hook: before_flush.
    Detects changes in session and queues AuditLog entries.
    """
    # Prevent infinite recursion: Don't audit the AuditLog table itself
    
    request_id = get_request_id() or "system"
    user_id = get_user_id() # Might be None if system task or unauth

    # 1. Handle New Records (INSERT)
    for obj in session.new:
        if type(obj) in AUDIT_MODELS:
            state_after = object_as_dict(obj)
            audit_entry = AuditLog(
                user_id=user_id,
                target_type=obj.__class__.__name__,
                target_id=None, 
                action="INSERT",
                state_before=None,
                state_after=state_after,
                request_id=request_id
            )
            session.add(audit_entry)

    # 2. Handle Updates
    for obj in session.dirty:
        if type(obj) in AUDIT_MODELS and session.is_modified(obj):
            state_before = {}
            state_after = {}
            
            # inspect history to see what changed
            ins = inspect(obj)
            for attr in ins.attrs:
                if attr.history.has_changes():
                    old_val = attr.history.deleted[0] if attr.history.deleted else None
                    new_val = attr.history.added[0] if attr.history.added else None
                    
                    state_before[attr.key] = str(old_val)
                    state_after[attr.key] = str(new_val)

            audit_entry = AuditLog(
                user_id=user_id,
                target_type=obj.__class__.__name__,
                target_id=obj.id,
                action="UPDATE",
                state_before=state_before,
                state_after=state_after,
                request_id=request_id
            )
            session.add(audit_entry)

    # 3. Handle Deletes
    for obj in session.deleted:
        if type(obj) in AUDIT_MODELS:
            state_before = object_as_dict(obj)
            audit_entry = AuditLog(
                user_id=user_id,
                target_type=obj.__class__.__name__,
                target_id=obj.id,
                action="DELETE",
                state_before=state_before,
                state_after=None,
                request_id=request_id
            )
            session.add(audit_entry)

event.listen(Session, "before_flush", capture_audit_logs)