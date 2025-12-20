# app/main.py
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # <--- NEW IMPORT

# --- CORE IMPORTS ---
from app.core.logging import configure_logging
from app.metrics.prometheus import init_metrics
from app.core.config import settings

# Configure JSON logging for the entire app
configure_logging()

# --- IMPORT ALL ROUTERS ---
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

# --- INITIALIZE FASTAPI APP ---
app = FastAPI(
    title="AI-Native Business OS/CRM",
    description="The unified backend for Pods A (Auth) and C (Integrations).",
    version="1.0.0",
)

# --- MIDDLEWARE (CORS) ---
# This allows a frontend (e.g., localhost:3000) to communicate with this API.
origins = [
    "http://localhost",
    "http://localhost:3000", # React/Next.js default
    "http://localhost:5173", # Vite/Vue default
    "*" # WARNING: Allow all for development only. Change for production.
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Prometheus Metrics (Latency, Request Counts)
init_metrics(app)

# --- INCLUDE ROUTERS ---

# 1. Authentication
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])

# 2. Communication & Integrations
app.include_router(emailer_router, prefix="/api/email", tags=["Emailer"])
app.include_router(whatsapp_router, prefix="/api", tags=["WhatsApp"])
app.include_router(webhooks_router, prefix="/api", tags=["Webhooks"])
app.include_router(bulk_router, prefix="/api/bulk", tags=["Bulk Messaging"])

# 3. Core CRM Data
app.include_router(messages_router, prefix="/api", tags=["Messages"])
app.include_router(contacts_router, prefix="/api", tags=["Contacts"])

# 4. AI & Intelligence
app.include_router(llm_router, prefix="/api", tags=["AI Client"])
app.include_router(vector_router, prefix="/api", tags=["AI/Vector"])
app.include_router(chat_router, prefix="/api", tags=["Chat/NLP"])
app.include_router(replies_router, prefix="/api", tags=["AI/Replies"])

# 5. Ops & Analytics
app.include_router(status_router, prefix="/api", tags=["Reliability/Dashboard"])
app.include_router(analytics_router, prefix="/api", tags=["Analytics & BI"])
app.include_router(ops_router)

# --- ROOT ENDPOINT ---
@app.get("/", tags=["Root"])
def root():
    """Health check endpoint to confirm the API is running."""
    return {"status": "AI-Native CRM Backend is running!"}