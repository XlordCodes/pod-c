# app/main.py
"""
Module: Main Application Entry Point
Context: Root

Initializes the FastAPI application, middleware, and core systems.
Wires up the Event Bus for asynchronous workflows (Module 7).
"""

import logging
import asyncio
from contextlib import asynccontextmanager
import sentry_sdk
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

# --- CORE IMPORTS ---
from app.core.logging import configure_logging
from app.metrics.prometheus import init_metrics
from app.core.config import settings
from app.core.middleware import RequestContextMiddleware

# --- DATABASE IMPORTS (CRITICAL FIX) ---
from app.database import Base, engine

# --- EVENT BUS IMPORTS (Module 7) ---
from app.core.event_bus import event_bus, set_main_loop
from app.subscribers.inventory_subscribers import setup_inventory_subscribers

# --- ROUTER IMPORTS ---
# Importing this ensures all Models are loaded into Base.metadata via side-effects
from app.api.router import api_router

# --- CONFIGURATION ---
configure_logging()
logger = logging.getLogger(__name__)

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        environment=settings.ENVIRONMENT or "development"
    )

# --- LIFESPAN (Startup/Shutdown Logic) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    """
    logger.info("🚀 Application startup: Initializing resources.")
    
    # 1. Create Database Tables (The Missing Link)
    # This creates 'users', 'contacts', 'bulk_jobs', etc. if they don't exist
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables verified/created.")
    except Exception as e:
        logger.error(f"❌ Database setup failed: {e}")

    # 2. Capture the Main Loop
    try:
        loop = asyncio.get_running_loop()
        set_main_loop(loop)
        logger.debug(f"✅ Main Event Loop captured: {id(loop)}")
    except RuntimeError as e:
        logger.error(f"❌ Failed to capture main loop: {e}")

    # 3. Initialize Event Bus Subscribers
    setup_inventory_subscribers(event_bus)
    logger.info("📡 Event Bus: Subscribers registered.")

    yield
    
    logger.info("🛑 Application shutdown: Cleaning up resources.")

# --- APP INIT ---
app = FastAPI(
    title="AI-Native Business OS/CRM",
    description="Unified Backend (Pods A, B, C)",
    version="1.0.0",
    lifespan=lifespan
)

# --- MIDDLEWARE ---
# SECURITY FIX: Strict CORS configuration - no wildcard origins allowed
origins = settings.BACKEND_CORS_ORIGINS

# Validate CORS configuration
if not origins:
    logger.warning(
        "⚠️ SECURITY WARNING: BACKEND_CORS_ORIGINS is empty. "
        "No cross-origin requests will be allowed. "
        "Set BACKEND_CORS_ORIGINS in .env to whitelist specific domains."
    )
    # Fail-closed: Empty list means no origins are allowed
    origins = []
elif "*" in origins:
    logger.error(
        "❌ SECURITY ERROR: Wildcard '*' detected in BACKEND_CORS_ORIGINS. "
        "This is a critical security risk in production."
    )
    raise RuntimeError(
        "CORS misconfiguration: Wildcard origins are not allowed. "
        "Please specify explicit domain names."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.add_middleware(RequestContextMiddleware)
init_metrics(app)

# --- ROUTES ---

# 1. Main API Group (/v1/api/...)
app.include_router(api_router, prefix="/v1/api")

# 2. Health Checks
ops_router = APIRouter(tags=["Operations"])

@ops_router.get("/health")
def health_check():
    """Kubernetes Liveness Probe"""
    return {"status": "ok", "version": "1.0.0"}

@ops_router.get("/ready")
def readiness_check():
    """Kubernetes Readiness Probe"""
    return {"status": "ready"}

app.include_router(ops_router, prefix="/ops")

@app.get("/", tags=["Root"])
def root():
    return {
        "status": "AI-Native CRM Backend is running!",
        "docs": "/docs"
    }