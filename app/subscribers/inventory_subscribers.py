# app/subscribers/inventory_subscribers.py
"""
Module: Inventory Subscribers
Context: Pod B - Module 7 (Async Workflows)

Contains the event handlers for Inventory-related events.
These functions run asynchronously in the background.
"""

import logging
import asyncio
from app.core.event_bus import EventBus
from app.events.inventory_events import LowStockEvent, StockAdjustedEvent

# Setup Logging
logger = logging.getLogger("InventorySubscribers")

async def handle_low_stock(event: LowStockEvent):
    """
    Handler for LowStockEvent.
    Simulates sending an alert to the procurement team.
    """
    # 1. Simulate Processing Delay (e.g., connecting to Email Server)
    # This proves that the main API response is not blocked by this delay.
    await asyncio.sleep(0.1) 
    
    # 2. Perform Action (Log for now, EmailService in future)
    logger.warning(
        f"⚠️  [ALERT] LOW STOCK: '{event.product_name}' (SKU: {event.sku}) "
        f"has dropped to {event.current_stock}. "
        f"Reorder Point: {event.reorder_point}."
    )
    
    # In a real app, you would do:
    # await email_service.send_alert(template="low_stock", to="admin@company.com", context=event.dict())

async def handle_stock_adjusted(event: StockAdjustedEvent):
    """
    Handler for StockAdjustedEvent.
    Useful for real-time dashboards or external syncs.
    """
    logger.info(
        f"📦 [TRACE] Stock Update: {event.sku} changed by {event.qty_change:+d}. "
        f"New Level: {event.new_stock}. Reason: {event.reason}"
    )

def setup_inventory_subscribers(bus: EventBus):
    """
    Registration function to wire events to handlers.
    Called during application startup.
    """
    bus.subscribe(LowStockEvent, handle_low_stock)
    bus.subscribe(StockAdjustedEvent, handle_stock_adjusted)