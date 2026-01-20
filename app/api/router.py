# app/api/router.py
"""
Module: Central API Router
Context: Core Architecture.

Aggregates all domain-specific routers into a single 'api_router'.
This keeps main.py clean and centralizes URL prefix management.
"""

from fastapi import APIRouter

# --- Import Domain Routers ---

# 1. Auth & Core
from app.authentication.router import router as auth_router

# 2. Integrations (Pod C)
from app.api.emailer import router as emailer_router
from app.api.whatsapp import router as whatsapp_router
from app.api.webhooks import router as webhooks_router
from app.api.bulk import router as bulk_router

# 3. CRM Data (Pod A/B)
from app.api.contacts import router as contacts_router
from app.api.messages import router as messages_router

# 4. Finance (Pod B - NEW)
from app.api.finance import router as finance_router
from app.api.leads import router as leads_router

# 5. AI & Intelligence (Pod C)
from app.api.aiclient import router as llm_router
from app.api.vector import router as vector_router
from app.api.chat import router as chat_router
from app.api.replies import router as replies_router

# 6. Operations & Analytics
from app.api.status import router as status_router
from app.api.analytics import router as analytics_router
from app.api.audit import router as audit_router

# 7. Inventory 
from app.api.inventory import router as inventory_router

# --- Initialize Central Router ---
api_router = APIRouter()

# --- Register Routes ---

# Authentication
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])

# Integrations
api_router.include_router(emailer_router, prefix="/email", tags=["Emailer"])
api_router.include_router(whatsapp_router, tags=["WhatsApp"]) 
api_router.include_router(webhooks_router, tags=["Webhooks"]) 
api_router.include_router(bulk_router, prefix="/bulk", tags=["Bulk Messaging"])

# CRM
api_router.include_router(contacts_router, tags=["Contacts"]) 
api_router.include_router(messages_router, tags=["Messages"]) 
api_router.include_router(leads_router, prefix="/leads", tags=["Leads"])

# Finance
api_router.include_router(finance_router, prefix="/finance", tags=["Finance"])

# Inventory
api_router.include_router(inventory_router, prefix="/inventory", tags=["Inventory"])

# AI
api_router.include_router(llm_router, tags=["AI Client"]) 
api_router.include_router(vector_router, prefix="/vector", tags=["AI/Vector"]) 

api_router.include_router(chat_router, prefix="/chat", tags=["Chat/NLP"]) 

api_router.include_router(replies_router, prefix="/ai", tags=["AI/Replies"]) 

# Ops & Analytics
api_router.include_router(status_router, prefix="/status", tags=["Reliability"]) 
api_router.include_router(analytics_router, prefix="/analytics", tags=["Analytics"]) 
api_router.include_router(audit_router, prefix="/audit", tags=["Audit"])