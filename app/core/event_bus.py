# app/core/event_bus.py
"""
Module: Event Bus
Context: Pod B - Module 7 (Async Workflows).

A lightweight, in-memory event bus for decoupling services.
Allows 'Fire-and-Forget' asynchronous event handling.

Architecture Note:
This module includes a 'Main Loop Bridge' to allow synchronous worker threads
(e.g., standard FastAPI endpoints) to dispatch events to the main asyncio loop.
"""

import asyncio
import logging
from typing import Callable, Dict, List, Type, TypeVar, Awaitable, Any, Optional
from pydantic import BaseModel

# Setup Logging
logger = logging.getLogger("EventBus")

# --- Global Loop Reference (The Bridge) ---
# This variable holds the reference to the main application event loop.
# It is set during application startup (see app/main.py).
_main_loop: Optional[asyncio.AbstractEventLoop] = None

def set_main_loop(loop: asyncio.AbstractEventLoop):
    """
    Registers the main application loop. 
    Called once during startup (lifespan).
    """
    global _main_loop
    _main_loop = loop
    logger.info("✅ Event Bus: Main event loop registered.")

def get_main_loop() -> Optional[asyncio.AbstractEventLoop]:
    """
    Retrieves the main application loop.
    Used by synchronous services to schedule async tasks safely.
    """
    return _main_loop

# --- 1. Base Event Definition ---

class BaseEvent(BaseModel):
    """
    Base class for all Domain Events.
    Events are immutable data structures (Pydantic models).
    """
    pass

# Generic TypeVar to enforce type safety in subscribers
EventType = TypeVar("EventType", bound=BaseEvent)


# --- 2. The Event Bus ---

class EventBus:
    """
    Asynchronous In-Memory Event Bus.
    Singleton-style usage recommended.
    """
    def __init__(self):
        # Maps Event Type -> List of Async Handler Functions
        self._subscribers: Dict[Type[BaseEvent], List[Callable[[Any], Awaitable[None]]]] = {}

    def subscribe(self, event_type: Type[EventType], handler: Callable[[EventType], Awaitable[None]]):
        """
        Registers a function to handle a specific event type.
        
        Args:
            event_type: The class of the event to listen for (e.g., OrderCreated).
            handler: An async function that accepts the event instance.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        
        self._subscribers[event_type].append(handler)
        logger.info(f"📡 Subscribed '{handler.__name__}' to '{event_type.__name__}'")

    async def publish(self, event: BaseEvent):
        """
        Dispatches an event to all registered subscribers.
        
        Mechanism: FIRE-AND-FORGET.
        This method creates background tasks for handlers and returns immediately.
        It does NOT wait for handlers to finish.
        """
        event_type = type(event)
        handlers = self._subscribers.get(event_type, [])

        if not handlers:
            # No subscribers is a valid state (just debug log it)
            logger.debug(f"Event '{event_type.__name__}' published but no subscribers found.")
            return

        logger.info(f"📢 Publishing Event: {event_type.__name__} ({len(handlers)} subscribers)")

        # Schedule each handler as an independent asyncio task.
        # Note: This uses the CURRENT running loop. If called from a sync thread via
        # run_coroutine_threadsafe, this correctly schedules on the main loop.
        for handler in handlers:
            asyncio.create_task(self._run_handler_safe(handler, event))

    async def _run_handler_safe(self, handler, event):
        """
        Wrapper to execute handlers safely.
        Captures exceptions so one failing handler doesn't crash others or the loop.
        """
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"❌ Error in handler '{handler.__name__}': {str(e)}")
            # In a real production system, you would report this to Sentry/Datadog here.


# --- 3. Global Instance ---
# We use a single global instance for the application lifecycle.
event_bus = EventBus()