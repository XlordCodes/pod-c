# tests/integration/test_contacts.py
import pytest
import pytest_asyncio
import uuid
from httpx import AsyncClient

# -----------------------------------------------------------------------------
# FIXTURES
# -----------------------------------------------------------------------------
# FIX: Use pytest_asyncio to ensure the async fixture is awaited properly
@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient):
    """
    Automatically logs in as admin and returns the Authorization headers.
    """
    unique_email = f"admin_{uuid.uuid4().hex[:6]}@ryze.com"
    reg_data = {"email": unique_email, "password": "securepass", "name": "Admin"}
    
    # Register
    await client.post("/v1/auth/register", json=reg_data)
    
    # Login
    res = await client.post("/v1/auth/token", data={"username": unique_email, "password": "securepass"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

# -----------------------------------------------------------------------------
# TESTS
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_contact_success(client: AsyncClient, auth_headers):
    """
    Happy Path: Create a standard contact.
    """
    payload = {
        "name": "Alice Wonderland",
        "email": f"alice_{uuid.uuid4().hex[:4]}@example.com",
        "phone": "+919876543210",
        "custom_fields": {"segment": "vip"}
    }
    res = await client.post("/v1/api/contacts", json=payload, headers=auth_headers)
    
    assert res.status_code == 200, f"Failed: {res.text}"
    data = res.json()
    assert data["name"] == payload["name"]
    assert data["id"] is not None
    # Verify custom fields were saved (requires DB model update)
    assert data["custom_fields"] == {"segment": "vip"}

@pytest.mark.asyncio
async def test_create_duplicate_phone_fails(client: AsyncClient, auth_headers):
    """
    Edge Case: The system must reject duplicate phone numbers.
    """
    phone = f"+91{uuid.uuid4().int}"[:13]
    
    payload_1 = {"name": "User One", "phone": phone}
    payload_2 = {"name": "User Two", "phone": phone}

    # First creation -> Success
    res1 = await client.post("/v1/api/contacts", json=payload_1, headers=auth_headers)
    assert res1.status_code == 200

    # Second creation -> Should Fail
    res2 = await client.post("/v1/api/contacts", json=payload_2, headers=auth_headers)
    assert res2.status_code in [400, 409]

@pytest.mark.asyncio
async def test_get_contacts_pagination(client: AsyncClient, auth_headers):
    """
    Performance: Ensure listing contacts supports pagination.
    """
    res = await client.get("/v1/api/contacts?skip=0&limit=5", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    
    assert isinstance(data, list)
    assert len(data) <= 5

@pytest.mark.asyncio
async def test_update_contact(client: AsyncClient, auth_headers):
    """
    CRUD: Verify update logic works.
    """
    # 1. Create
    phone = f"+91{uuid.uuid4().int}"[:13]
    create_res = await client.post("/v1/api/contacts", json={"name": "Old Name", "phone": phone}, headers=auth_headers)
    contact_id = create_res.json()["id"]

    # 2. Update
    patch_payload = {"name": "New Name"}
    update_res = await client.put(f"/v1/api/contacts/{contact_id}", json=patch_payload, headers=auth_headers)
    
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "New Name"
    assert update_res.json()["phone"] == phone

@pytest.mark.asyncio
async def test_delete_contact(client: AsyncClient, auth_headers):
    """
    CRUD: Verify deletion.
    """
    # 1. Create
    phone = f"+91{uuid.uuid4().int}"[:13]
    create_res = await client.post("/v1/api/contacts", json={"name": "To Delete", "phone": phone}, headers=auth_headers)
    contact_id = create_res.json()["id"]

    # 2. Delete
    del_res = await client.delete(f"/v1/api/contacts/{contact_id}", headers=auth_headers)
    assert del_res.status_code == 200

    # 3. Verify it's gone
    get_res = await client.get(f"/v1/api/contacts/{contact_id}", headers=auth_headers)
    assert get_res.status_code == 404