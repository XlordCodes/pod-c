# app/models/__init__.py
"""
Module: Model Registry
Context: Core Architecture

Exports all models so Alembic can detect them for migrations.
This file is the Single Source of Truth for the DB schema.
"""

# 1. Base
from app.database import Base

# 2. Auth & Core
from .auth import User, Role

# 3. Audit & Activity (Pod B Module 3)
# FIX: Added ActivityFeed here
from .audit import AuditLog, ActivityFeed

# 4. CRM & Communication (Pod A & Pod B Module 1)
# FIX: Added Lead and Deal here
from .crm import Contact, Lead, Deal
from .chat import Message, Conversation, ChatMessage
from .communication import BulkJob, BulkMessage, EmailQueue

# 5. Extensions
from .extensions import MessageStatus, MessageEmbedding, ReplySuggestion

# 6. Finance (Pod B Module 2)
from .finance import Invoice, InvoiceItem, Payment, LedgerEntry

# 7. Inventory (Pod B Module 5)
from .inventory import Product, StockTransaction

# Export for Alembic
__all__ = [
    "Base",
    "User", "Role", 
    "AuditLog", "ActivityFeed",
    "Contact", "Lead", "Deal",
    "Message", "Conversation", "ChatMessage",
    "BulkJob", "BulkMessage", "EmailQueue",
    "MessageStatus", "MessageEmbedding", "ReplySuggestion",
    "Invoice", "InvoiceItem", "Payment", "LedgerEntry",
    "Product", "StockTransaction"
]