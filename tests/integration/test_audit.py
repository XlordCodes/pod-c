# tests/integration/test_audit.py
import pytest
import uuid
from app.models import AuditLog

@pytest.mark.asyncio
async def test_audit_log_creation(client, db_session):
    """
    Test that creating a row (Contact) automatically creates an AuditLog entry.
    """
    # 1. Setup User Credentials
    # Use random email to avoid conflicts if DB isn't perfectly wiped
    unique_id = uuid.uuid4().hex[:6]
    email = f"audit_admin_{unique_id}@ryze.com"
    password = "pass123"

    # 2. REGISTER the user first (Critical Step)
    # The DB is empty, so we must create the user before logging in.
    reg_payload = {
        "email": email, 
        "password": password, 
        "name": "Audit Admin"
    }
    reg_res = await client.post("/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201, f"Registration failed: {reg_res.text}"

    # 3. LOGIN to get a token
    login_data = {
        "username": email, # OAuth2 form expects 'username' field for email
        "password": password
    }
    login_res = await client.post("/v1/auth/token", data=login_data)
    
    # Fail fast if login fails
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 4. Create a new Contact via API
    random_contact_email = f"contact_{unique_id}@test.com"
    
    contact_payload = {
        "name": "Audit Test Contact",
        "email": random_contact_email,
        "phone": "+1234567890",
        "custom_fields": {"source": "test"} # Added to match new schema
    }
    
    # Send POST request
    res = await client.post("/v1/api/contacts", json=contact_payload, headers=headers)
    assert res.status_code == 200, f"Contact creation failed: {res.text}"
    
    # 5. Check Audit Logs in DB
    # We expect an entry with action="INSERT" for target_type="Contact"
    log_entry = db_session.query(AuditLog).filter(
        AuditLog.target_type == "Contact",
        AuditLog.action == "INSERT"
    ).order_by(AuditLog.created_at.desc()).first()

    assert log_entry is not None, "No AuditLog entry found for Contact insertion"
    assert log_entry.user_id is not None
    # Verify the unique email appears in the log payload (state_after)
    # state_after is stored as JSON, so we cast to string for simple inclusion check
    assert random_contact_email in str(log_entry.state_after)

@pytest.mark.asyncio
async def test_request_id_middleware(client):
    """
    Test that the RequestContextMiddleware adds the X-Request-ID header.
    """
    res = await client.get("/")
    assert res.status_code == 200
    assert "X-Request-ID" in res.headers
    assert len(res.headers["X-Request-ID"]) > 0