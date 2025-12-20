# app/core/health.py
from fastapi import APIRouter
from sqlalchemy import text
from app.database import SessionLocal

router = APIRouter(prefix="/ops", tags=["Ops/Health"])

@router.get("/health")
def liveness():
    """
    Simple probe to check if the API process is running.
    Used by Docker/K8s to restart the container if it hangs.
    """
    return {"status": "alive"}

@router.get("/ready")
def readiness():
    """
    Checks if the application is ready to accept traffic.
    Verifies Database connectivity.
    """
    try:
        # Create a fresh session to test DB connection
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "ready"}
    except Exception as e:
        # Return 503 so Load Balancers stop sending traffic
        return {"status": "db_error", "detail": str(e)}