# app/services/inventory_service.py
"""
Module: Inventory Service
Context: Pod B - Module 5 (Business Logic) & Module 7 (Events)

Manages Product Catalog and Stock Levels.
Integrates:
1. Data Persistence (Repo)
2. Audit Logging (AuditService)
3. Async Event Publishing (EventBus) - Thread-Safe Implementation

Standards:
- Strict Typing
- Atomic Transactions
- "Fire-and-Forget" Event Dispatch (Sync -> Async Bridge)
"""

import asyncio
import logging
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repos.inventory_repo import InventoryRepo
from app.services.audit_service import AuditService
from app.schemas.inventory import ProductCreate, StockAdjustment
from app.models.inventory import Product

# Event Bus Imports
from app.core.event_bus import event_bus, get_main_loop # <--- Helper imported here
from app.events.inventory_events import LowStockEvent, StockAdjustedEvent

logger = logging.getLogger(__name__)

class InventoryService:
    """
    Service for managing Inventory.
    Enforces business rules and orchestrates side effects (Audit, Events).
    """
    def __init__(self, db: Session):
        self.db = db
        self.repo = InventoryRepo(db)
        self.audit = AuditService(db)

    def _publish_event_safe(self, event):
        """
        Helper: Schedules an async event from a synchronous context.
        Uses the global main loop to ensure thread safety across AnyIO worker threads.
        """
        try:
            # Strategy: Use the captured main loop (The Bridge)
            main_loop = get_main_loop()
            
            if main_loop and main_loop.is_running():
                # Correct way to fire-and-forget from a worker thread to the main loop
                asyncio.run_coroutine_threadsafe(event_bus.publish(event), main_loop)
            else:
                # Fallback: This path is usually taken during Unit Tests where 
                # the app lifecycle (and thus set_main_loop) hasn't run.
                # We try to find a loop in the current thread.
                try:
                    loop = asyncio.get_event_loop()
                    loop.create_task(event_bus.publish(event))
                except RuntimeError:
                    # No loop at all (common in some synchronous test runners)
                    logger.warning(f"⚠️ Could not publish event {type(event).__name__}: No event loop found.")

        except Exception as e:
            # Critical: Event failure should NOT rollback the DB transaction
            logger.error(f"❌ Failed to publish event {type(event).__name__}: {e}")

    def create_product(self, tenant_id: int, schema: ProductCreate, user_id: Optional[int] = None) -> Product:
        """
        Creates a new product in the catalog.
        """
        # 1. Duplicate Check
        existing = self.repo.get_product_by_sku(tenant_id, schema.sku)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Product with SKU '{schema.sku}' already exists."
            )
        
        # 2. Create Product (DB)
        product = self.repo.create_product(tenant_id, schema)

        # 3. Audit Log
        # FIX: Added mode='json' to prevent "Object of type Decimal is not JSON serializable"
        self.audit.log_event(
            actor_id=user_id,
            entity="Product",
            entity_id=product.id,
            action="create",
            changes=schema.model_dump(mode='json') 
        )
        
        return product

    def get_product(self, tenant_id: int, product_id: int) -> Product:
        product = self.repo.get_product(tenant_id, product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Product not found"
            )
        return product

    def list_products(self, tenant_id: int, skip: int = 0, limit: int = 100) -> List[Product]:
        return self.repo.list_products(tenant_id, skip, limit)

    def adjust_stock(
        self, 
        tenant_id: int, 
        product_id: int, 
        adjustment: StockAdjustment,
        user_id: Optional[int] = None
    ) -> Product:
        """
        Moves stock IN/OUT.
        Triggers: Audit Log, StockAdjustedEvent, LowStockEvent.
        """
        # 1. Fetch Product
        product = self.repo.get_product(tenant_id, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # 2. Business Rule: Prevent negative stock
        new_level = product.stock + adjustment.qty
        if new_level < 0:
            raise HTTPException(
                status_code=400, 
                detail=f"Insufficient stock. Current: {product.stock}, Requested: {abs(adjustment.qty)}"
            )

        # 3. Execute Transaction (Atomic Update)
        self.repo.create_transaction(
            product=product,
            change=adjustment.qty,
            reason=adjustment.reason,
            ref_id=adjustment.reference_id
        )
        
        # 4. Audit Log
        self.audit.log_event(
            actor_id=user_id,
            entity="Product",
            entity_id=product.id,
            action="adjust_stock",
            changes={
                "change": adjustment.qty,
                "reason": adjustment.reason,
                "new_stock": new_level
                # Note: If new_level was a Decimal, we would need to cast it here.
                # Integer arithmetic usually remains Integer in Python.
            }
        )
        
        # 5. Refresh to get final state
        self.db.refresh(product)

        # --- EVENT PUBLISHING (After successful DB commit) ---
        
        # Event A: General Stock Change
        self._publish_event_safe(StockAdjustedEvent(
            tenant_id=tenant_id,
            product_id=product.id,
            sku=product.sku,
            qty_change=adjustment.qty,
            new_stock=new_level,
            reason=adjustment.reason,
            actor_id=user_id
        ))

        # Event B: Low Stock Warning
        if new_level <= product.reorder_point:
            self._publish_event_safe(LowStockEvent(
                tenant_id=tenant_id,
                product_id=product.id,
                sku=product.sku,
                product_name=product.name,
                current_stock=new_level,
                reorder_point=product.reorder_point
            ))
        
        return product