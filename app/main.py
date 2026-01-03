# app/main.py
import logging
from contextlib import asynccontextmanager
import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- CORE IMPORTS ---
from app.core.logging import configure_logging
from app.metrics.prometheus import init_metrics
from app.core.config import settings
from app.core.middleware import RequestContextMiddleware

# --- AUDIT HOOKS ---
# Import this module to ensure event listeners for auditing are registered 
# before the application starts processing requests.
import app.core.audit

# --- ROUTER IMPORTS ---
from app.api.emailer import router as emailer_router
from app.api.aiclient import router as llm_router
from app.api.webhooks import router as webhooks_router
from app.api.messages import router as messages_router
from app.api.contacts import router as contacts_router
from app.api.whatsapp import router as whatsapp_router
from app.api.bulk import router as bulk_router
from app.api.vector import router as vector_router
from app.api.chat import router as chat_router
from app.api.replies import router as replies_router
from app.api.status import router as status_router
from app.api.analytics import router as analytics_router
from app.authentication.router import router as auth_router
from app.api.ops import router as ops_router
from app.api.audit import router as audit_router

# --- CONFIGURATION & SETUP ---

# Initialize the custom logging configuration for the application.
configure_logging()

# Initialize Sentry for error tracking and performance monitoring if a DSN is provided.
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        # Capture 100% of transactions for performance monitoring during development.
        # Ensure this is tuned via settings for production to manage quota usage.
        traces_sample_rate=1.0,
        # Profile 100% of sampled transactions.
        profiles_sample_rate=1.0,
        environment=settings.ENVIRONMENT or "development"
    )

# --- LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handle startup and shutdown events for the FastAPI application.
    Use this to initialize database connections, Redis pools, or HTTP clients.
    """
    # Logic to execute on startup
    logging.info("Application startup: Initializing resources.")
    
    yield
    
    # Logic to execute on shutdown
    logging.info("Application shutdown: Cleaning up resources.")

# --- INITIALIZE FASTAPI APP ---
app = FastAPI(
    title="AI-Native Business OS/CRM",
    description="The unified backend for Pods A (Auth) and C (Integrations).",
    version="1.0.0",
    lifespan=lifespan
)

# --- MIDDLEWARE CONFIGURATION ---

# Configure Cross-Origin Resource Sharing (CORS).
# In production, allow_origins should be restricted to specific domains defined in settings.
# Defaulting to ["*"] is acceptable for local development but insecure for production.
origins = settings.BACKEND_CORS_ORIGINS if hasattr(settings, "BACKEND_CORS_ORIGINS") else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register custom middleware for request context logging and auditing.
app.add_middleware(RequestContextMiddleware)

# Initialize Prometheus metrics instrumentation for the application.
init_metrics(app)

# --- ROUTER REGISTRATION ---

# 1. Authentication Module
# Handles user login, registration, and token management.
app.include_router(auth_router, prefix="/v1/auth", tags=["Authentication"])

# 2. Communication & Integrations Modules
# Handles external communication channels and third-party integrations.
app.include_router(emailer_router, prefix="/v1/api/email", tags=["Emailer"])
app.include_router(whatsapp_router, prefix="/v1/api", tags=["WhatsApp"])
app.include_router(webhooks_router, prefix="/v1/api", tags=["Webhooks"])
app.include_router(bulk_router, prefix="/v1/api/bulk", tags=["Bulk Messaging"])

# 3. Core CRM Data Modules
# Handles the primary business entities: Messages and Contacts.
app.include_router(messages_router, prefix="/v1/api", tags=["Messages"])
app.include_router(contacts_router, prefix="/v1/api", tags=["Contacts"])

# 4. AI & Intelligence Modules
# Handles LLM interactions, vector database operations, and NLP logic.
app.include_router(llm_router, prefix="/v1/api", tags=["AI Client"])
app.include_router(vector_router, prefix="/v1/api", tags=["AI/Vector"])
app.include_router(chat_router, prefix="/v1/api", tags=["Chat/NLP"])
app.include_router(replies_router, prefix="/v1/api", tags=["AI/Replies"])

# 5. Operations, Analytics & Auditing Modules
# Handles system reliability, business intelligence, and security auditing.
app.include_router(status_router, prefix="/v1/api", tags=["Reliability/Dashboard"])
app.include_router(analytics_router, prefix="/v1/api", tags=["Analytics & BI"])
app.include_router(audit_router, prefix="/v1/api", tags=["Audit"])

# Note: The Ops router is mounted with a specific prefix to avoid namespace pollution at the root.
app.include_router(ops_router, prefix="/ops", tags=["Operations"])

# --- ROOT ENDPOINT ---
@app.get("/", tags=["Root"])
def root():
    """
    Root endpoint to verify the service status.
    """
    return {"status": "AI-Native CRM Backend is running!"}