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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- CORE IMPORTS ---
from app.core.logging import configure_logging
from app.metrics.prometheus import init_metrics
from app.core.config import settings
from app.core.middleware import RequestContextMiddleware

# --- EVENT BUS IMPORTS (Module 7) ---
from app.core.event_bus import event_bus, set_main_loop
from app.subscribers.inventory_subscribers import setup_inventory_subscribers

# --- ROUTER IMPORTS ---
from app.api.router import api_router  # The central router
from app.api.ops import router as ops_router  # Operations (Health/Metrics)

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
    
    # 1. Capture the Main Loop (CRITICAL FIX)
    # This allows sync worker threads (like InventoryService) to talk to async EventBus
    try:
        loop = asyncio.get_running_loop()
        set_main_loop(loop)
        logger.debug(f"✅ Main Event Loop captured: {id(loop)}")
    except RuntimeError as e:
        logger.error(f"❌ Failed to capture main loop: {e}")

    # 2. Initialize Event Bus Subscribers
    # This wires the 'InventoryService' events to their background handlers.
    setup_inventory_subscribers(event_bus)
    logger.info("📡 Event Bus: Subscribers registered.")

    yield
    
    logger.info("🛑 Application shutdown: Cleaning up resources.")
    # (Optional) If we had a Redis/Kafka connection, we would close it here.

# --- APP INIT ---
app = FastAPI(
    title="AI-Native Business OS/CRM",
    description="Unified Backend (Pods A, B, C)",
    version="1.0.0",
    lifespan=lifespan
)

# --- MIDDLEWARE ---
origins = settings.BACKEND_CORS_ORIGINS if hasattr(settings, "BACKEND_CORS_ORIGINS") else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)
init_metrics(app)

# --- ROUTES ---

# 1. Main API Group (/v1/api/...)
app.include_router(api_router, prefix="/v1/api")

# 2. Operations (/ops/...)
app.include_router(ops_router)

@app.get("/", tags=["Root"])
def root():
    return {
        "status": "AI-Native CRM Backend is running!",
        "module_7_events": "Active"
    }