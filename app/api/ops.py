# app/api/ops.py
from fastapi import APIRouter
from app.core.health import router as health_router

# Main Operations Router
# This mounts the health checks and potentially other ops tools (backup triggers, etc.)
router = APIRouter()

router.include_router(health_router)