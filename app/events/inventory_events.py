# app/events/inventory_events.py
"""
Module: Inventory Events
Context: Pod B - Module 7 (Domain Events)

Defines the structure of events emitted by the Inventory Service.
These are Pydantic models used by the Event Bus.
"""

from typing import Optional
from app.core.event_bus import BaseEvent

class LowStockEvent(BaseEvent):
    """
    Triggered when a product's stock drops below its reorder point.
    """
    tenant_id: int
    product_id: int
    sku: str
    product_name: str
    current_stock: int
    reorder_point: int

class StockAdjustedEvent(BaseEvent):
    """
    Triggered after any successful stock modification.
    Useful for analytics or syncing with external channels (e.g., Shopify).
    """
    tenant_id: int
    product_id: int
    sku: str
    qty_change: int
    new_stock: int
    reason: str
    actor_id: Optional[int] = None