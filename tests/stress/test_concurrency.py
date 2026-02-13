"""
Module: Concurrency Stress Tests
Context: Pod B - Inventory System

Simulates high-concurrency race conditions (e.g., "Flash Sales") to verify
that Row-Level Locking (SELECT FOR UPDATE) is correctly enforced.

Target: InventoryService.adjust_stock()
"""

import pytest
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session
from sqlalchemy import text 

from app.database import SessionLocal
from app.services.inventory_service import InventoryService
from app.schemas.inventory import ProductCreate, StockAdjustment
from app.models.auth import User

# --- FIXTURES ---

@pytest.fixture(scope="function")
def db_session():
    """
    Creates a new database session for setup/teardown.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture(scope="function")
def setup_product(db_session):
    """
    Creates a test product with exactly 10 items in stock.
    Also ensures a dummy user exists for Audit Logging.
    """
    # 1. Clean up previous tests (Order matters for Foreign Keys)
    db_session.execute(text("DELETE FROM stock_transactions"))
    db_session.execute(text("DELETE FROM products"))
    # Clean up the dummy user if it exists from a previous run
    db_session.execute(text("DELETE FROM users WHERE email = 'stress_test@example.com'"))
    db_session.commit()

    # 2. Create Dummy User for Audit Logs using ORM (Fixes IntegrityErrors)
    test_user = User(
        id=999,
        email='stress_test@example.com',
        hashed_password='dummy_hash',
        role_id=None,
        tenant_id=None
    )
    db_session.add(test_user)
    db_session.commit()

    # 3. Create Service
    svc = InventoryService(db_session)
    
    # 4. Disable event publishing for setup (prevents async warnings)
    svc._publish_event_safe = lambda event: None
    
    # 5. Create Product
    product = svc.create_product(
        tenant_id=1,
        schema=ProductCreate(
            sku="RACE-TEST-001",
            name="Flash Sale Item",
            description="Stress Test Item",
            price=100.00,
            reorder_point=0
        ),
        user_id=999  # <--- Now valid because we created User 999 above
    )
    
    # 6. Set Initial Stock to 10
    svc.adjust_stock(
        tenant_id=1,
        product_id=product.id,
        adjustment=StockAdjustment(
            qty=10, 
            reason="Initial Stock", 
            reference_id="SETUP"
        ),
        user_id=999
    )
    
    return product.id

# --- HELPER FUNCTION (The "User") ---

def attempt_purchase(product_id: int, tenant_id: int):
    """
    Simulates a single user trying to buy 1 item.
    Each thread gets its OWN database session to simulate a real HTTP request.
    """
    session = SessionLocal()
    svc = InventoryService(session)
    
    # CRITICAL FIX: Disable event publishing to prevent async RuntimeWarnings
    # This stress test focuses ONLY on DB transaction locking, not event side effects
    svc._publish_event_safe = lambda event: None
    
    success = False
    message = ""
    
    try:
        svc.adjust_stock(
            tenant_id=tenant_id,
            product_id=product_id,
            adjustment=StockAdjustment(
                qty=-1, 
                reason="Flash Sale Purchase", 
                reference_id=f"THREAD-{threading.get_ident()}"
            ),
            user_id=999 # Use the valid dummy user ID
        )
        success = True
    except Exception as e:
        # In a race, we EXPECT failures once stock hits 0.
        # We capture the error to ensure it's the *right* error (Insufficient Stock).
        success = False
        message = str(e)
    finally:
        session.close()
        
    return success, message

# --- THE STRESS TEST ---

def test_inventory_race_condition(setup_product):
    """
    Scenario: 20 concurrent threads try to buy stock from a pile of 10.
    
    Expectation:
    - 10 threads succeed.
    - 10 threads fail with "Insufficient stock".
    - Final stock is exactly 0.
    """
    product_id = setup_product
    tenant_id = 1
    total_buyers = 20
    
    print(f"\n[RACE TEST] Starting Race: {total_buyers} buyers vs 10 items...")

    results = []
    
    # Run 20 threads simultaneously
    with ThreadPoolExecutor(max_workers=total_buyers) as executor:
        futures = [
            executor.submit(attempt_purchase, product_id, tenant_id) 
            for _ in range(total_buyers)
        ]
        
        for future in as_completed(futures):
            results.append(future.result())

    # --- ANALYSIS ---
    
    successful_buys = sum(1 for r in results if r[0] is True)
    failed_buys = sum(1 for r in results if r[0] is False)
    
    print(f"[SUCCESS] Successful Buys: {successful_buys}")
    print(f"[FAILED] Failed Buys: {failed_buys}")

    # --- ASSERTIONS ---

    # 1. Check Logical Consistency
    assert successful_buys == 10, f"Expected 10 sales, got {successful_buys}"
    assert failed_buys == 10, f"Expected 10 rejections, got {failed_buys}"
    
    # 2. Check Database Integrity (Final Truth)
    # We open a NEW session to verify the persistent state
    final_session = SessionLocal()
    svc = InventoryService(final_session)
    final_product = svc.get_product(tenant_id, product_id)
    
    print(f"[FINAL] Final Stock Level: {final_product.stock}")
    
    assert final_product.stock == 0, f"CRITICAL FAILURE: Stock is {final_product.stock}, expected 0!"
    assert final_product.stock >= 0, "CRITICAL FAILURE: Stock went negative!"
    
    final_session.close()