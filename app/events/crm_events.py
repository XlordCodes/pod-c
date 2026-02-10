# app/events/crm_events.py
"""
Module: CRM Events
Context: Pod B - Module 7 (Domain Events)

Defines the structure of events emitted by the CRM Service.
These are Pydantic models used by the Event Bus for decoupling.
"""

from typing import Optional
from app.core.event_bus import BaseEvent

class DealCreated(BaseEvent):
    """
    Triggered when a Lead is successfully promoted to a Deal.
    """
    tenant_id: int
    deal_id: int
    lead_id: int
    value_cents: int
    seller_id: Optional[int] = None
    currency: str = "USD"