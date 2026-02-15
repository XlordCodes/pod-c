# tests/integration/test_leads_logic.py
"""
Module: Leads Business Logic Integration Tests
Context: Pod B - CRM Domain.

Tests the Leads module's business rules and security controls:
- Duplicate email prevention
- Converted lead immutability (state lock)
- Invalid owner assignment prevention

These tests verify the security controls implemented in the LeadService.

DATABASE LOCKING FIX:
- All setup data is created via API calls (not direct DB manipulation)
- This ensures the same session/transaction is used throughout
- Service-level tests use the shared db_session fixture with proper rollback
"""

import pytest
from httpx import AsyncClient

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio


# =============================================================================
# TEST 1: Duplicate Email Prevention
# =============================================================================

async def test_duplicate_email_prevention(client: AsyncClient, auth_headers, test_user):
    """
    Verify that creating a lead with a duplicate email is rejected.
    
    Steps:
    1. Create a lead with email "dup@test.com" via API
    2. Attempt to create another lead with the same email (same tenant)
    3. Assert status code is 400 (Bad Request)
    4. Verify error message mentions duplicate
    """
    # 1. Create first lead with the email via API
    first_lead_payload = {
        "name": "First Lead",
        "email": "dup@test.com"
    }
    
    first_response = await client.post(
        "/v1/api/leads/",
        json=first_lead_payload,
        headers=auth_headers
    )
    
    assert first_response.status_code == 201, (
        f"Failed to create first lead: {first_response.text}"
    )
    
    first_lead_data = first_response.json()
    assert first_lead_data["email"] == "dup@test.com"
    
    # 2. Attempt to create second lead with the same email
    second_lead_payload = {
        "name": "Second Lead",
        "email": "dup@test.com"  # Duplicate email
    }
    
    second_response = await client.post(
        "/v1/api/leads/",
        json=second_lead_payload,
        headers=auth_headers
    )
    
    # 3. Assert rejection (400 Bad Request)
    assert second_response.status_code == 400, (
        f"Expected 400 for duplicate email, got {second_response.status_code}. "
        f"Response: {second_response.text}"
    )
    
    # 4. Verify error message mentions duplicate
    error_detail = second_response.json().get("detail", "")
    assert "already exists" in error_detail.lower(), (
        f"Error message should mention duplicate. Got: {error_detail}"
    )


# =============================================================================
# TEST 2: Converted Lead Immutability (State Lock)
# =============================================================================

async def test_converted_lead_immutable(client: AsyncClient, auth_headers, test_user):
    """
    Verify that a converted lead cannot be edited (state lock).
    
    Steps:
    1. Create a lead via API
    2. Convert the lead to a deal via API (sets status to "converted")
    3. Attempt to update the lead's name/email via API
    4. Assert status code is 400 (Bad Request)
    5. Verify error message mentions immutability
    
    NOTE: All operations use API to avoid database locking issues.
    """
    # 1. Create a lead via API
    lead_payload = {
        "name": "Convertible Lead",
        "email": "convert@test.com"
    }
    
    create_response = await client.post(
        "/v1/api/leads/",
        json=lead_payload,
        headers=auth_headers
    )
    
    assert create_response.status_code == 201, (
        f"Failed to create lead: {create_response.text}"
    )
    lead_id = create_response.json()["id"]
    
    # 2. Convert the lead to a deal via API
    # This will set the lead status to "converted"
    convert_response = await client.post(
        f"/v1/api/leads/{lead_id}/convert",
        params={"value_cents": 10000},  # $100.00 in cents
        headers=auth_headers
    )
    
    assert convert_response.status_code == 200, (
        f"Failed to convert lead: {convert_response.text}"
    )
    
    # Verify the conversion was successful
    deal_data = convert_response.json()
    assert deal_data["lead_id"] == lead_id
    
    # 3. Attempt to update the converted lead's name via API
    update_payload = {
        "name": "Updated Name"
    }
    
    update_response = await client.patch(
        f"/v1/api/leads/{lead_id}",
        json=update_payload,
        headers=auth_headers
    )
    
    # 4. Assert rejection (400 Bad Request)
    assert update_response.status_code == 400, (
        f"Expected 400 for editing converted lead, got {update_response.status_code}. "
        f"Response: {update_response.text}"
    )
    
    # 5. Verify error message mentions immutability
    error_detail = update_response.json().get("detail", "")
    assert "immutable" in error_detail.lower() or "converted" in error_detail.lower(), (
        f"Error message should mention immutability. Got: {error_detail}"
    )


# =============================================================================
# TEST 3: Invalid Owner Assignment (Service-Level Test)
# =============================================================================

async def test_invalid_owner_assignment(client: AsyncClient, auth_headers, test_user, db_session):
    """
    Verify that creating a lead with a non-existent owner_id is rejected.
    
    NOTE: The API uses current_user.id as owner_id, so we test this at the
    service level using the shared db_session fixture.
    
    Steps:
    1. Call LeadService.create_lead with invalid owner_id
    2. Assert HTTPException with 400 status
    3. Verify error message mentions invalid owner
    4. Rollback the failed transaction to clean up
    """
    from app.services.lead_service import LeadService
    from app.schemas.crm import LeadCreate
    from fastapi import HTTPException
    
    try:
        service = LeadService(db_session)
        
        # Create lead data
        lead_data = LeadCreate(
            name="Test Lead",
            email="test_nonexistent@test.com"
        )
        
        # Try to create a lead with non-existent owner_id
        with pytest.raises(HTTPException) as exc_info:
            service.create_lead(
                tenant_id=test_user.tenant_id,
                owner_id=99999,  # Non-existent user
                data=lead_data
            )
        
        # Verify the exception details
        assert exc_info.value.status_code == 400
        assert "does not exist" in exc_info.value.detail.lower()
        
    finally:
        # Rollback to ensure the failed transaction doesn't break subsequent tests
        db_session.rollback()


async def test_cross_tenant_owner_assignment(client: AsyncClient, auth_headers, test_user, db_session):
    """
    Verify that a lead cannot be assigned to a user from a different tenant.
    
    NOTE: Uses the shared db_session fixture to avoid locking issues.
    
    Steps:
    1. Create a user in a different tenant using db_session
    2. Try to create a lead assigned to that user (cross-tenant)
    3. Assert HTTPException with 400 status
    4. Rollback to clean up the test data
    """
    from app.models.auth import User
    from app.authentication.hashing import hash_password
    from app.services.lead_service import LeadService
    from app.schemas.crm import LeadCreate
    from fastapi import HTTPException
    
    try:
        # 1. Create a user in a different tenant using db_session
        other_tenant_user = User(
            email="other_tenant_user@test.com",
            hashed_password=hash_password("password123"),
            name="Other Tenant User",
            tenant_id=999  # Different tenant than test_user (tenant_id=1)
        )
        db_session.add(other_tenant_user)
        db_session.commit()
        db_session.refresh(other_tenant_user)
        
        # 2. Try to create a lead assigned to the other tenant's user
        service = LeadService(db_session)
        lead_data = LeadCreate(
            name="Cross Tenant Lead",
            email="cross_tenant@test.com"
        )
        
        # 3. This should raise HTTPException with 400
        with pytest.raises(HTTPException) as exc_info:
            service.create_lead(
                tenant_id=test_user.tenant_id,  # Tenant 1
                owner_id=other_tenant_user.id,   # User from Tenant 999
                data=lead_data
            )
        
        # 4. Verify the exception details
        assert exc_info.value.status_code == 400
        error_detail = exc_info.value.detail.lower()
        assert "another tenant" in error_detail or "invalid owner" in error_detail
        
    finally:
        # Rollback to ensure the test data is cleaned up
        db_session.rollback()


# =============================================================================
# TEST 4: Valid Lead Creation (Positive Test)
# =============================================================================

async def test_valid_lead_creation(client: AsyncClient, auth_headers, test_user):
    """
    Verify that a valid lead can be created successfully.
    
    This is a positive test to ensure the validation doesn't block
    legitimate operations.
    """
    lead_payload = {
        "name": "Valid Lead",
        "email": "valid@test.com"
    }
    
    response = await client.post(
        "/v1/api/leads/",
        json=lead_payload,
        headers=auth_headers
    )
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["name"] == "Valid Lead"
    assert data["email"] == "valid@test.com"
    assert data["status"] == "new"
    assert data["tenant_id"] == test_user.tenant_id
    assert data["owner_id"] == test_user.id


# =============================================================================
# TEST 5: Valid Lead Update (Before Conversion)
# =============================================================================

async def test_valid_lead_update_before_conversion(client: AsyncClient, auth_headers, test_user):
    """
    Verify that a lead CAN be updated before conversion.
    
    This ensures the state lock only applies to converted leads.
    """
    # 1. Create a lead via API
    lead_payload = {
        "name": "Updatable Lead",
        "email": "updatable@test.com"
    }
    
    create_response = await client.post(
        "/v1/api/leads/",
        json=lead_payload,
        headers=auth_headers
    )
    
    assert create_response.status_code == 201
    lead_id = create_response.json()["id"]
    
    # 2. Update the lead (should succeed because status is "new")
    update_payload = {
        "name": "Updated Lead Name",
        "email": "updated@test.com"
    }
    
    update_response = await client.patch(
        f"/v1/api/leads/{lead_id}",
        json=update_payload,
        headers=auth_headers
    )
    
    # 3. Assert success
    assert update_response.status_code == 200, (
        f"Update should succeed for non-converted lead. "
        f"Got {update_response.status_code}: {update_response.text}"
    )
    
    data = update_response.json()
    assert data["name"] == "Updated Lead Name"
    assert data["email"] == "updated@test.com"
    assert data["status"] == "new"  # Status unchanged


# =============================================================================
# TEST 6: Verify Converted Status in Database
# =============================================================================

async def test_lead_status_after_conversion(client: AsyncClient, auth_headers, test_user, db_session):
    """
    Verify that a lead's status is correctly set to 'converted' after conversion.
    
    This test uses db_session only for READ operations after API calls complete.
    """
    from app.models.crm import Lead
    
    # 1. Create a lead via API
    lead_payload = {
        "name": "Status Check Lead",
        "email": "status_check@test.com"
    }
    
    create_response = await client.post(
        "/v1/api/leads/",
        json=lead_payload,
        headers=auth_headers
    )
    
    assert create_response.status_code == 201
    lead_id = create_response.json()["id"]
    
    # 2. Convert the lead via API
    convert_response = await client.post(
        f"/v1/api/leads/{lead_id}/convert",
        params={"value_cents": 5000},
        headers=auth_headers
    )
    
    assert convert_response.status_code == 200
    
    # 3. Verify status in database (READ-ONLY operation)
    # Expire all objects to force fresh read from database
    db_session.expire_all()
    
    lead = db_session.query(Lead).filter(Lead.id == lead_id).first()
    assert lead is not None, "Lead should exist in database"
    assert lead.status == "converted", (
        f"Lead status should be 'converted', got: {lead.status}"
    )