import logging

# --- Robust Logging Configuration ---
# Set the root logger level to WARNING. This will silence SQLAlchemy's INFO spam.
logging.basicConfig(level=logging.WARNING) 

# Set specific loggers back to INFO so we can see Uvicorn startup
# and our own application-level logs.
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.error").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

from fastapi import FastAPI
from dotenv import load_dotenv

# --- IMPORT ALL ROUTERS ---
# Routers from the original pod-c-project
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
from app.authentication.router import router as auth_router
from app.api.analytics import router as analytics_router


# Load environment variables from the .env file
load_dotenv()

# --- INITIALIZE FASTAPI APP ---
# Adding title and version for better API documentation
app = FastAPI(
    title="AI-Native Business OS/CRM",
    description="The unified backend for Pods A (Auth) and C (Integrations).",
    version="1.0.0",
)

# --- INCLUDE ALL ROUTERS IN THE APP ---

# 1. Authentication Router (from the integrated ns-crm project)
# --- FIX: Added prefix and tags for clarity ---
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])

# 2. Existing Integration Routers
# --- Added tags for better organization in API docs ---
app.include_router(emailer_router, prefix="/api/email", tags=["Emailer"])
app.include_router(llm_router, prefix="/api", tags=["AI Client"])
app.include_router(webhooks_router, prefix="/api", tags=["Webhooks"])
app.include_router(messages_router, prefix="/api", tags=["Messages"])
app.include_router(contacts_router, prefix="/api", tags=["Contacts"])
app.include_router(whatsapp_router, prefix="/api", tags=["WhatsApp"])
app.include_router(bulk_router, prefix="/api/bulk", tags=["Bulk Messaging"])
app.include_router(vector_router, prefix="/api", tags=["AI/Vector"])
app.include_router(chat_router, prefix="/api", tags=["Chat/NLP"])
app.include_router(replies_router, prefix="/api", tags=["AI/Replies"])
app.include_router(status_router, prefix="/api", tags=["Reliability/Dashboard"])
app.include_router(analytics_router, prefix="/api", tags=["Analytics & BI"])
# --- ROOT ENDPOINT ---
@app.get("/", tags=["Root"])
def root():
    """A simple root endpoint to confirm the API is running."""
    return {"status": "AI-Native CRM Backend is running!"}

