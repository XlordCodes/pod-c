# tests/integration/test_finance.py
"""
Module: Finance Integration Tests
Context: Pod B - Finance Domain.

Tests the Finance module's security controls and business logic:
- Invoice creation with Decimal validation
- Payment processing with row-level locking
- Overpayment prevention
- Tenant isolation (authorization)

CRITICAL: JSON doesn't support Decimal objects natively.
All monetary values must be cast to str or float in request payloads.

DATABASE REQUIREMENTS:
- Contact.owner_id is NOT NULL (requires a valid User ID)
- Contact.tenant_id can be NULL but should match the user's tenant
"""

import pytest
from decimal import Decimal
from httpx import AsyncClient
from unittest.mock import MagicMock

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

# =============================================================================
# HELPER FUNCTION
# =============================================================================

def create_test_contact(db_session, name: str, phone: str, tenant_id: int, owner_id: int, email: str = None):
    """
    Helper to create a Contact with all required fields.
    
    Required fields (from app/models/crm.py):
    - name: NOT NULL
    - owner_id: NOT NULL (ForeignKey to users.id)
    
    Optional fields:
    - tenant_id: NULL allowed (but should match user's tenant for isolation)
    - email: NULL allowed
    - phone: NULL allowed
    """
    from app.models.crm import Contact
    
    contact = Contact(
        tenant_id=tenant_id,
        name=name,
        phone=phone,
        email=email or f"{name.lower().replace(' ', '')}@test.com",
        owner_id=owner_id  # CRITICAL: Required field!
    )
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)
    return contact


# =============================================================================
# TEST 1: Invoice Creation Success
# =============================================================================

async def test_create_invoice_success(client: AsyncClient, auth_headers, db_session, test_user):
    """
    Verify an invoice is created with the correct Decimal total.
    
    Steps:
    1. Create a Contact (required for invoice.contact_id)
    2. Create an Invoice with multiple line items
    3. Verify the total_amount is calculated correctly using Decimal arithmetic
    """
    # 1. Create a Contact with all required fields
    contact = create_test_contact(
        db_session=db_session,
        name="Test Customer",
        phone="+1234567890",
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id,
        email="test@example.com"
    )
    
    # 2. Create Invoice Payload
    # CRITICAL: Cast Decimal to str for JSON serialization
    payload = {
        "contact_id": contact.id,
        "currency": "USD",
        "items": [
            {
                "description": "Service A",
                "quantity": 2,
                "unit_price": "50.00"  # str for JSON
            },
            {
                "description": "Service B",
                "quantity": 1,
                "unit_price": "25.50"  # str for JSON
            }
        ]
    }
    
    # 3. Send Request
    response = await client.post(
        "/v1/api/finance/invoices",
        json=payload,
        headers=auth_headers
    )
    
    # 4. Assertions
    assert response.status_code == 201, f"Failed to create invoice: {response.text}"
    
    data = response.json()
    
    # Verify total: (2 * 50.00) + (1 * 25.50) = 125.50
    expected_total = Decimal("125.50")
    actual_total = Decimal(str(data["total_amount"]))
    
    assert actual_total == expected_total, (
        f"Invoice total mismatch. Expected: {expected_total}, Got: {actual_total}"
    )
    
    # Verify other fields
    assert data["status"] == "draft"
    assert data["currency"] == "USD"
    assert len(data["items"]) == 2
    
    # Verify items have correct prices
    for item in data["items"]:
        if item["description"] == "Service A":
            assert Decimal(str(item["unit_price"])) == Decimal("50.00")
            assert item["quantity"] == 2
        elif item["description"] == "Service B":
            assert Decimal(str(item["unit_price"])) == Decimal("25.50")
            assert item["quantity"] == 1


# =============================================================================
# TEST 2: Invoice Creation - Negative Amount Rejection
# =============================================================================

async def test_create_invoice_negative_amount(client: AsyncClient, auth_headers, db_session, test_user):
    """
    Verify the API rejects negative numbers (Schema validation).
    
    The Pydantic schema enforces gt=0 for unit_price and quantity.
    This test verifies that validation is working correctly.
    """
    # Create a Contact with all required fields
    contact = create_test_contact(
        db_session=db_session,
        name="Test Customer Negative",
        phone="+1234567891",
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id
    )
    
    # Test Case 1: Negative unit_price
    payload_negative_price = {
        "contact_id": contact.id,
        "items": [
            {
                "description": "Invalid Item",
                "quantity": 1,
                "unit_price": "-10.00"  # Negative price
            }
        ]
    }
    
    response = await client.post(
        "/v1/api/finance/invoices",
        json=payload_negative_price,
        headers=auth_headers
    )
    
    # Should return 422 (Validation Error)
    assert response.status_code == 422, (
        f"Expected 422 for negative price, got {response.status_code}"
    )
    
    # Test Case 2: Zero quantity
    payload_zero_quantity = {
        "contact_id": contact.id,
        "items": [
            {
                "description": "Zero Quantity Item",
                "quantity": 0,  # Zero quantity (gt=0 means strictly positive)
                "unit_price": "10.00"
            }
        ]
    }
    
    response = await client.post(
        "/v1/api/finance/invoices",
        json=payload_zero_quantity,
        headers=auth_headers
    )
    
    # Should return 422 (Validation Error)
    assert response.status_code == 422, (
        f"Expected 422 for zero quantity, got {response.status_code}"
    )
    
    # Test Case 3: Negative quantity
    payload_negative_quantity = {
        "contact_id": contact.id,
        "items": [
            {
                "description": "Negative Quantity Item",
                "quantity": -5,  # Negative quantity
                "unit_price": "10.00"
            }
        ]
    }
    
    response = await client.post(
        "/v1/api/finance/invoices",
        json=payload_negative_quantity,
        headers=auth_headers
    )
    
    # Should return 422 (Validation Error)
    assert response.status_code == 422, (
        f"Expected 422 for negative quantity, got {response.status_code}"
    )


# =============================================================================
# TEST 3: Payment Success
# =============================================================================

async def test_record_payment_success(client: AsyncClient, auth_headers, db_session, test_user):
    """
    Verify a payment reduces the amount_due correctly.
    
    Steps:
    1. Create an Invoice with a known total
    2. Record a partial payment
    3. Verify the invoice status changes to 'partial'
    4. Record the remaining payment
    5. Verify the invoice status changes to 'paid'
    """
    # 1. Create Contact with all required fields
    contact = create_test_contact(
        db_session=db_session,
        name="Payment Test Customer",
        phone="+1234567892",
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id
    )
    
    # 2. Create Invoice (Total: 100.00)
    invoice_payload = {
        "contact_id": contact.id,
        "items": [
            {
                "description": "Test Service",
                "quantity": 1,
                "unit_price": "100.00"
            }
        ]
    }
    
    invoice_response = await client.post(
        "/v1/api/finance/invoices",
        json=invoice_payload,
        headers=auth_headers
    )
    
    assert invoice_response.status_code == 201
    invoice_id = invoice_response.json()["id"]
    
    # 3. Record Partial Payment (50.00)
    payment_payload = {
        "invoice_id": invoice_id,
        "amount": "50.00",  # str for JSON
        "method": "bank_transfer"
    }
    
    payment_response = await client.post(
        "/v1/api/finance/payments",
        json=payment_payload,
        headers=auth_headers
    )
    
    assert payment_response.status_code == 200, (
        f"Payment failed: {payment_response.text}"
    )
    
    # 4. Verify Invoice Status is 'partial'
    invoice_data = payment_response.json()
    assert invoice_data["status"] == "partial", (
        f"Expected status 'partial', got '{invoice_data['status']}'"
    )
    
    # Verify payment is recorded
    assert len(invoice_data["payments"]) == 1
    assert Decimal(str(invoice_data["payments"][0]["amount"])) == Decimal("50.00")
    
    # 5. Record Remaining Payment (50.00)
    final_payment_payload = {
        "invoice_id": invoice_id,
        "amount": "50.00",
        "method": "stripe"
    }
    
    final_response = await client.post(
        "/v1/api/finance/payments",
        json=final_payment_payload,
        headers=auth_headers
    )
    
    assert final_response.status_code == 200
    
    # 6. Verify Invoice Status is 'paid'
    final_data = final_response.json()
    assert final_data["status"] == "paid", (
        f"Expected status 'paid', got '{final_data['status']}'"
    )
    
    # Verify total payments
    assert len(final_data["payments"]) == 2
    
    total_paid = sum(
        Decimal(str(p["amount"])) for p in final_data["payments"]
    )
    assert total_paid == Decimal("100.00")


# =============================================================================
# TEST 4: Overpayment Prevention
# =============================================================================

async def test_record_payment_overpayment(client: AsyncClient, auth_headers, db_session, test_user):
    """
    Verify the system rejects a payment that is larger than the amount_due.
    
    This tests the overpayment validation added during the security audit.
    The service layer should return 400 Bad Request if payment exceeds balance.
    """
    # 1. Create Contact with all required fields
    contact = create_test_contact(
        db_session=db_session,
        name="Overpayment Test Customer",
        phone="+1234567893",
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id
    )
    
    # 2. Create Invoice (Total: 100.00)
    invoice_payload = {
        "contact_id": contact.id,
        "items": [
            {
                "description": "Test Product",
                "quantity": 1,
                "unit_price": "100.00"
            }
        ]
    }
    
    invoice_response = await client.post(
        "/v1/api/finance/invoices",
        json=invoice_payload,
        headers=auth_headers
    )
    
    assert invoice_response.status_code == 201
    invoice_id = invoice_response.json()["id"]
    
    # 3. Attempt Overpayment (150.00 on a 100.00 invoice)
    overpayment_payload = {
        "invoice_id": invoice_id,
        "amount": "150.00",  # Exceeds invoice total
        "method": "bank_transfer"
    }
    
    response = await client.post(
        "/v1/api/finance/payments",
        json=overpayment_payload,
        headers=auth_headers
    )
    
    # 4. Verify Rejection (400 Bad Request)
    assert response.status_code == 400, (
        f"Expected 400 for overpayment, got {response.status_code}. "
        f"Response: {response.text}"
    )
    
    # Verify error message mentions overpayment
    error_detail = response.json().get("detail", "")
    assert "exceeds remaining balance" in error_detail.lower() or "overpayment" in error_detail.lower(), (
        f"Error message should mention overpayment. Got: {error_detail}"
    )
    
    # 5. Verify Partial Payment Still Works
    partial_payload = {
        "invoice_id": invoice_id,
        "amount": "60.00",  # Valid partial payment
        "method": "bank_transfer"
    }
    
    partial_response = await client.post(
        "/v1/api/finance/payments",
        json=partial_payload,
        headers=auth_headers
    )
    
    assert partial_response.status_code == 200
    
    # 6. Attempt Overpayment on Remaining Balance
    # Remaining: 100.00 - 60.00 = 40.00
    # Try to pay 50.00
    second_overpayment = {
        "invoice_id": invoice_id,
        "amount": "50.00",  # Exceeds remaining 40.00
        "method": "cash"
    }
    
    response = await client.post(
        "/v1/api/finance/payments",
        json=second_overpayment,
        headers=auth_headers
    )
    
    assert response.status_code == 400, (
        f"Expected 400 for second overpayment, got {response.status_code}"
    )


# =============================================================================
# TEST 5: Unauthorized Access (Tenant Isolation)
# =============================================================================

async def test_unauthorized_access(client: AsyncClient, db_session):
    """
    Verify User A cannot view User B's invoices.
    
    This tests the tenant isolation security control.
    Each user should only see invoices from their own tenant.
    """
    from app.models.crm import Contact
    from app.models.auth import User
    from app.authentication.hashing import hash_password
    from app.authentication.router import create_access_token
    from datetime import timedelta
    
    # 1. Create User A (Tenant 1)
    user_a = User(
        email="user_a@test.com",
        hashed_password=hash_password("password_a"),
        name="User A",
        tenant_id=1
    )
    db_session.add(user_a)
    
    # 2. Create User B (Tenant 2)
    user_b = User(
        email="user_b@test.com",
        hashed_password=hash_password("password_b"),
        name="User B",
        tenant_id=2
    )
    db_session.add(user_b)
    
    db_session.commit()
    db_session.refresh(user_a)
    db_session.refresh(user_b)
    
    # 3. Create Auth Headers for Both Users
    token_a = create_access_token(
        data={"sub": user_a.email},
        expires_delta=timedelta(minutes=30)
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}
    
    token_b = create_access_token(
        data={"sub": user_b.email},
        expires_delta=timedelta(minutes=30)
    )
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    # 4. Create Contact for Tenant 1 (with owner_id = user_a.id)
    contact_a = Contact(
        tenant_id=1,
        name="Tenant 1 Customer",
        phone="+1111111111",
        owner_id=user_a.id  # CRITICAL: Required field!
    )
    db_session.add(contact_a)
    
    # 5. Create Contact for Tenant 2 (with owner_id = user_b.id)
    contact_b = Contact(
        tenant_id=2,
        name="Tenant 2 Customer",
        phone="+2222222222",
        owner_id=user_b.id  # CRITICAL: Required field!
    )
    db_session.add(contact_b)
    
    db_session.commit()
    db_session.refresh(contact_a)
    db_session.refresh(contact_b)
    
    # 6. User A Creates Invoice (Tenant 1)
    invoice_a_payload = {
        "contact_id": contact_a.id,
        "items": [
            {
                "description": "Tenant 1 Service",
                "quantity": 1,
                "unit_price": "200.00"
            }
        ]
    }
    
    response_a = await client.post(
        "/v1/api/finance/invoices",
        json=invoice_a_payload,
        headers=headers_a
    )
    
    assert response_a.status_code == 201
    invoice_a_id = response_a.json()["id"]
    
    # 7. User B Creates Invoice (Tenant 2)
    invoice_b_payload = {
        "contact_id": contact_b.id,
        "items": [
            {
                "description": "Tenant 2 Service",
                "quantity": 1,
                "unit_price": "300.00"
            }
        ]
    }
    
    response_b = await client.post(
        "/v1/api/finance/invoices",
        json=invoice_b_payload,
        headers=headers_b
    )
    
    assert response_b.status_code == 201
    invoice_b_id = response_b.json()["id"]
    
    # 8. TEST: User B Tries to Access User A's Invoice
    # This should return 404 (not found) because of tenant isolation
    unauthorized_response = await client.get(
        f"/v1/api/finance/invoices/{invoice_a_id}",
        headers=headers_b  # User B trying to access User A's invoice
    )
    
    assert unauthorized_response.status_code == 404, (
        f"SECURITY VIOLATION: User B accessed User A's invoice! "
        f"Status: {unauthorized_response.status_code}"
    )
    
    # 9. TEST: User A Tries to Access User B's Invoice
    unauthorized_response = await client.get(
        f"/v1/api/finance/invoices/{invoice_b_id}",
        headers=headers_a  # User A trying to access User B's invoice
    )
    
    assert unauthorized_response.status_code == 404, (
        f"SECURITY VIOLATION: User A accessed User B's invoice! "
        f"Status: {unauthorized_response.status_code}"
    )
    
    # 10. TEST: User A Can Access Their Own Invoice
    authorized_response = await client.get(
        f"/v1/api/finance/invoices/{invoice_a_id}",
        headers=headers_a
    )
    
    assert authorized_response.status_code == 200, (
        f"User A should be able to access their own invoice"
    )
    
    # 11. TEST: User B Can Access Their Own Invoice
    authorized_response = await client.get(
        f"/v1/api/finance/invoices/{invoice_b_id}",
        headers=headers_b
    )
    
    assert authorized_response.status_code == 200, (
        f"User B should be able to access their own invoice"
    )
    
    # 12. TEST: List Invoices - User A Only Sees Tenant 1 Invoices
    list_a = await client.get(
        "/v1/api/finance/invoices",
        headers=headers_a
    )
    
    assert list_a.status_code == 200
    invoices_a = list_a.json()
    
    # All invoices should belong to tenant 1
    for inv in invoices_a:
        assert inv["tenant_id"] == 1, (
            f"User A sees invoice from wrong tenant: {inv['tenant_id']}"
        )
    
    # 13. TEST: List Invoices - User B Only Sees Tenant 2 Invoices
    list_b = await client.get(
        "/v1/api/finance/invoices",
        headers=headers_b
    )
    
    assert list_b.status_code == 200
    invoices_b = list_b.json()
    
    # All invoices should belong to tenant 2
    for inv in invoices_b:
        assert inv["tenant_id"] == 2, (
            f"User B sees invoice from wrong tenant: {inv['tenant_id']}"
        )
    
    # 14. TEST: User B Cannot Pay User A's Invoice
    payment_attempt = await client.post(
        "/v1/api/finance/payments",
        json={
            "invoice_id": invoice_a_id,  # User A's invoice
            "amount": "50.00",
            "method": "cash"
        },
        headers=headers_b  # User B trying to pay
    )
    
    assert payment_attempt.status_code == 404, (
        f"SECURITY VIOLATION: User B paid User A's invoice! "
        f"Status: {payment_attempt.status_code}"
    )