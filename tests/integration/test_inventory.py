# tests/integration/test_inventory.py
"""
Module: Inventory Integration Tests
Context: Pod B - Module 5 (Workflow & Inventory)

Tests the full lifecycle of inventory management:
1. Product Creation (RBAC protected)
2. Stock Adjustments (Atomic transactions)
3. Business Logic (Negative stock prevention)
4. Tenant Isolation (Implicit via Service)
"""

import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.models.auth import User, Role
from app.models.inventory import Product, StockTransaction

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

async def setup_admin_role(db: Session, user_email: str):
    """
    Helper: Promotes the test user to 'admin' to bypass RBAC checks.
    """
    # 1. Find or Create Admin Role
    admin_role = db.query(Role).filter(Role.name == "admin").first()
    if not admin_role:
        admin_role = Role(name="admin", description="Super User")
        db.add(admin_role)
        db.commit()
        db.refresh(admin_role)

    # 2. Assign to User
    user = db.query(User).filter(User.email == user_email).first()
    if user:
        user.role_id = admin_role.id
        db.add(user)
        db.commit()

async def test_inventory_lifecycle(client: AsyncClient, db_session: Session, auth_headers: dict):
    """
    Test the complete flow: Create Product -> Add Stock -> Remove Stock -> Fail on Negative.
    """
    # --- SETUP: Promote User to Admin ---
    # We need to extract email from the auth setup or just pick the user created by the fixture.
    # Assuming auth_headers comes from a user like "test@example.com" or we fetch the user id 1.
    # For robustness, we'll grab the user associated with the token or just the first user.
    user = db_session.query(User).first()
    assert user is not None, "Test user not found in DB"
    await setup_admin_role(db_session, user.email)

    # --- STEP 1: Create Product ---
    sku = f"TEST-SKU-{uuid.uuid4().hex[:6]}"
    payload = {
        "sku": sku,
        "name": "Integration Test Widget",
        "description": "A widget for testing",
        "price": 19.99,
        "reorder_point": 5
    }

    res = await client.post("/v1/api/inventory/products", json=payload, headers=auth_headers)
    assert res.status_code == 201, f"Create Product failed: {res.text}"
    product_data = res.json()
    product_id = product_data["id"]
    
    assert product_data["sku"] == sku
    assert product_data["stock"] == 0  # Initial stock must be 0

    # --- STEP 2: Restock (Add +10) ---
    adjust_payload = {
        "qty": 10,
        "reason": "Initial Restock",
        "reference_id": "PO-001"
    }
    
    res = await client.post(f"/v1/api/inventory/products/{product_id}/adjust", json=adjust_payload, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["stock"] == 10

    # Verify Transaction Log in DB
    txn = db_session.query(StockTransaction).filter(
        StockTransaction.product_id == product_id,
        StockTransaction.qty_change == 10
    ).first()
    assert txn is not None, "StockTransaction record was not created"

    # --- STEP 3: Sale (Remove -3) ---
    sale_payload = {
        "qty": -3,
        "reason": "Customer Order",
        "reference_id": "ORDER-999"
    }
    
    res = await client.post(f"/v1/api/inventory/products/{product_id}/adjust", json=sale_payload, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["stock"] == 7  # 10 - 3 = 7

    # --- STEP 4: Prevent Negative Stock (Try removing -100) ---
    fail_payload = {
        "qty": -100,
        "reason": "Overselling",
    }
    
    res = await client.post(f"/v1/api/inventory/products/{product_id}/adjust", json=fail_payload, headers=auth_headers)
    assert res.status_code == 400
    assert "Insufficient stock" in res.text

    # Verify stock didn't change
    db_session.refresh(txn) # Refresh session to be safe
    prod = db_session.query(Product).filter(Product.id == product_id).first()
    assert prod.stock == 7

async def test_unauthorized_access(client: AsyncClient, db_session: Session, auth_headers: dict):
    """
    Verify that non-admin users cannot create products.
    """
    # --- SETUP: Demote User (Ensure no role) ---
    user = db_session.query(User).first()
    if user:
        user.role_id = None # Remove role
        db_session.add(user)
        db_session.commit()

    payload = {
        "sku": "FAIL-SKU",
        "name": "Illegal Widget",
        "price": 100.00
    }

    # Attempt to create product
    res = await client.post("/v1/api/inventory/products", json=payload, headers=auth_headers)
    
    # Should be 403 Forbidden because of @require_role(["admin", "manager"])
    assert res.status_code == 403