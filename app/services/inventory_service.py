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

CONCURRENCY HANDLING:
- Implements retry logic for database lock errors (SQLite/PostgreSQL)
- Uses tenacity for exponential backoff with jitter
- Critical for high-concurrency scenarios (Flash Sales, Bulk Operations)
"""

import asyncio
import logging
import random
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)

from app.repos.inventory_repo import InventoryRepo
from app.services.audit_service import AuditService
from app.schemas.inventory import ProductCreate, StockAdjustment
from app.models.inventory import Product

# Event Bus Imports
from app.core.event_bus import event_bus, get_main_loop
from app.events.inventory_events import LowStockEvent, StockAdjustedEvent

logger = logging.getLogger(__name__)


# ============================================================================
# RETRY CONFIGURATION FOR DATABASE LOCKS
# ============================================================================

# Retry decorator for handling database lock errors (SQLite "database is locked",
# PostgreSQL deadlock detection)
def _is_database_lock_error(exception: BaseException) -> bool:
    """
    Check if the exception is a database lock/deadlock error.
    
    SQLite: "database is locked" (OperationalError)
    PostgreSQL: "deadlock detected" (OperationalError with specific message)
    """
    if isinstance(exception, OperationalError):
        error_msg = str(exception).lower()
        # SQLite lock error
        if "database is locked" in error_msg:
            return True
        # PostgreSQL deadlock
        if "deadlock detected" in error_msg:
            return True
    return False


# Custom retry strategy for database operations
retry_on_db_lock = retry(
    # Only retry on database lock errors
    retry=retry_if_exception_type(OperationalError),
    # Retry up to 5 times
    stop=stop_after_attempt(5),
    # Exponential backoff with jitter: 0.01s -> 0.05s -> 0.1s -> 0.2s -> 0.4s
    # Plus random jitter to prevent thundering herd
    wait=wait_random_exponential(multiplier=0.01, min=0.01, max=0.5),
    # Log before each retry for debugging
    before_sleep=before_sleep_log(logger, logging.WARNING),
    # Log after successful retry
    after=after_log(logger, logging.DEBUG),
    # Re-raise the last exception if all retries fail
    reraise=True
)

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
                    logger.warning(f"Could not publish event {type(event).__name__}: No event loop found.")

        except Exception as e:
            # Event failure should NOT rollback the DB transaction
            logger.error(f"Failed to publish event {type(event).__name__}: {e}")

    def create_product(self, tenant_id: int, schema: ProductCreate, user_id: Optional[int] = None) -> Product:
        """
        Creates a new product in the catalog.
        Wraps creation and audit logging in a single atomic transaction.
        """
        try:
            # 1. Duplicate Check
            existing = self.repo.get_product_by_sku(tenant_id, schema.sku)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"Product with SKU '{schema.sku}' already exists."
                )
            
            # 2. Create Product (DB) - No commit here, just flush
            product = self.repo.create_product(tenant_id, schema)

            # 3. Audit Log
            self.audit.log_event(
                actor_id=user_id,
                entity="Product",
                entity_id=product.id,
                action="create",
                changes=schema.model_dump(mode='json') 
            )
            
            # 4. Commit Transaction
            self.db.commit()
            self.db.refresh(product)
            
            return product
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error creating product: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error")
        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error creating product: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected system error")

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

    def _adjust_stock_atomic(
        self, 
        tenant_id: int, 
        product_id: int, 
        adjustment: StockAdjustment,
        user_id: Optional[int] = None
    ) -> Product:
        """
        Internal atomic stock adjustment operation.
        
        This method is wrapped with retry logic to handle database lock errors.
        It contains ONLY the database operations that need to be retried.
        
        CRITICAL: Uses row locking (SELECT FOR UPDATE) to prevent race conditions
        during high-concurrency stock updates.
        
        Returns the updated Product on success.
        Raises OperationalError on database lock (will be retried by decorator).
        Raises HTTPException on business rule violations (NOT retried).
        """
        # 1. Fetch Product with Write Lock
        # This ensures no other transaction can modify this product until we commit.
        product = self.repo.get_product_for_update(tenant_id, product_id)
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
            }
        )
        
        # 5. Commit Atomic Transaction
        self.db.commit()
        self.db.refresh(product)
        
        return product

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
        
        CONCURRENCY HANDLING:
        - Wraps the atomic operation with retry logic for database lock errors
        - SQLite: Retries on "database is locked" errors
        - PostgreSQL: Retries on deadlock detection
        - Uses exponential backoff with jitter to prevent thundering herd
        
        Returns the updated Product on success.
        """
        try:
            # Execute the atomic operation with retry logic
            # The retry_on_db_lock decorator handles OperationalError retries
            product = retry_on_db_lock(self._adjust_stock_atomic)(
                tenant_id, product_id, adjustment, user_id
            )
            
            # Calculate new level for events (product is already updated)
            new_level = product.stock
            
            # 6. Publish Events (Fire-and-Forget AFTER successful commit)
            # These are NOT retried - they're best-effort notifications
            
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

        except OperationalError as e:
            # All retries exhausted - database still locked
            self.db.rollback()
            logger.error(f"Database lock error after retries: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                detail="Service temporarily unavailable. Please retry."
            )
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error adjusting stock: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database transaction failed")
        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error adjusting stock: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected system error")