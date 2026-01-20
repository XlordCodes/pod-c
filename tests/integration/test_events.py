# tests/integration/test_events.py
"""
Module: Event Integration Tests
Context: Pod B - Module 7 (Async Workflows)

Verifies that the InventoryService correctly publishes events to the Event Bus.
Uses mocking on the Service Boundary to avoid threading/loop complexity.
"""

import pytest
from unittest.mock import patch
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.models.auth import User, Role
from app.events.inventory_events import LowStockEvent, StockAdjustedEvent

# Mark all tests as async
pytestmark = pytest.mark.asyncio

async def setup_admin_role(db: Session, user_email: str):
    """Helper: Promotes the test user to 'admin'."""
    admin_role = db.query(Role).filter(Role.name == "admin").first()
    if not admin_role:
        admin_role = Role(name="admin", description="Super User")
        db.add(admin_role)
        db.commit()
    
    user = db.query(User).filter(User.email == user_email).first()
    if user:
        user.role_id = admin_role.id
        db.add(user)
        db.commit()

async def test_low_stock_event_trigger(client: AsyncClient, db_session: Session, auth_headers: dict):
    """
    Scenario:
    1. Create a product with Stock=10, Reorder Point=5.
    2. Reduce stock by 6 (New Stock=4).
    3. EXPECTATION: A 'LowStockEvent' is published.
    """
    # 1. Setup Admin
    user = db_session.query(User).first()
    await setup_admin_role(db_session, user.email)

    # 2. Create Product
    product_payload = {
        "sku": "EVENT-TEST-SKU",
        "name": "Event Test Widget",
        "price": 50.00,
        "reorder_point": 5
    }
    res = await client.post("/v1/api/inventory/products", json=product_payload, headers=auth_headers)
    assert res.status_code == 201
    product_id = res.json()["id"]

    # 3. Add Initial Stock (10)
    await client.post(
        f"/v1/api/inventory/products/{product_id}/adjust", 
        json={"qty": 10, "reason": "Init"}, 
        headers=auth_headers
    )

    # 4. Trigger Low Stock (Reduce by 6 -> Result 4)
    # FIX: We patch the internal helper method. 
    # This avoids the "No event loop" error because the threading code is never executed.
    with patch("app.services.inventory_service.InventoryService._publish_event_safe") as mock_publish:
        res = await client.post(
            f"/v1/api/inventory/products/{product_id}/adjust", 
            json={"qty": -6, "reason": "Sale"}, 
            headers=auth_headers
        )
        assert res.status_code == 200
        assert res.json()["stock"] == 4

        # 5. VERIFICATION
        assert mock_publish.called, "Event Bus publish was not called!"
        
        # Verify LowStockEvent was sent
        low_stock_sent = False
        stock_adjusted_sent = False
        
        for call_args in mock_publish.call_args_list:
            event = call_args[0][0] # First arg of the call
            
            if isinstance(event, LowStockEvent):
                low_stock_sent = True
                assert event.current_stock == 4
                assert event.sku == "EVENT-TEST-SKU"
            elif isinstance(event, StockAdjustedEvent):
                stock_adjusted_sent = True
                assert event.qty_change == -6

        assert stock_adjusted_sent, "StockAdjustedEvent was not fired."
        assert low_stock_sent, "LowStockEvent was not fired (Critical Failure)."