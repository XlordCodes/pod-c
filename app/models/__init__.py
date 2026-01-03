from app.database import Base

# 1. Auth & Core
from .auth import User, Role
from .audit import AuditLog

# 2. CRM & Communication
from .crm import Contact
from .chat import Message, Conversation, ChatMessage
from .communication import BulkJob, BulkMessage, EmailQueue

# 3. Extensions (Consolidated from separate files)
from .extensions import MessageStatus, MessageEmbedding, ReplySuggestion

# 4. New Pod B Domains (Finance & Inventory)
from .finance import Invoice, InvoiceItem, Payment, LedgerEntry
from .inventory import Product, StockTransaction

# Export for Alembic
__all__ = [
    "Base",
    "User", "Role", "AuditLog",
    "Contact",
    "Message", "Conversation", "ChatMessage",
    "BulkJob", "BulkMessage", "EmailQueue",
    "MessageStatus", "MessageEmbedding", "ReplySuggestion",
    "Invoice", "InvoiceItem", "Payment", "LedgerEntry",
    "Product", "StockTransaction"
]