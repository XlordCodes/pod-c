# app/api/audit.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import database, models
from app.authentication.router import RoleChecker

router = APIRouter(tags=["Audit & Ops"])

@router.get("/audit-logs")
def view_audit_logs(
    limit: int = 50, 
    db: Session = Depends(database.get_db),
    # Only Admins can view audit logs
    user: models.User = Depends(RoleChecker(["admin"]))
):
    """
    Fetch system audit logs. Only accessible by Admins.
    """
    return db.query(models.AuditLog)\
             .order_by(models.AuditLog.created_at.desc())\
             .limit(limit)\
             .all()