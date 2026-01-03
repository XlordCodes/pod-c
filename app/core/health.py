# app/core/health.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db

router = APIRouter(prefix="/ops", tags=["Ops/Health"])

@router.get("/health")
def liveness():
    """
    Simple probe to check if the API process is running.
    Used by Docker/K8s to restart the container if it hangs.
    """
    return {"status": "alive"}

@router.get("/ready")
def readiness(db: Session = Depends(get_db)):
    """
    Readiness probe: "Can I serve traffic?"
    Verifies Database connectivity. 
    Returns 503 if DB is down, causing Load Balancers to stop routing traffic here.
    """
    try:
        # Simple SQL execution to verify DB connection
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        # CRITICAL: Return 503 Service Unavailable so LBs stop sending traffic
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connectivity failed: {str(e)}"
        )