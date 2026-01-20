# tests/integration/test_contacts.py
import pytest
import uuid
from httpx import AsyncClient

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

# -----------------------------------------------------------------------------
# TESTS
# -----------------------------------------------------------------------------

async def test_create_contact_success(client: AsyncClient, auth_headers):
    """
    Happy Path: Create a standard contact.
    Uses global 'auth_headers' fixture for authentication.
    """
    payload = {
        "name": "Alice Wonderland",
        "email": f"alice_{uuid.uuid4().hex[:4]}@example.com",
        "phone": "+919876543210",
        "custom_fields": {"segment": "vip"}
    }
    
    # Path: /v1/api/contacts (Matches router.py structure)
    res = await client.post("/v1/api/contacts", json=payload, headers=auth_headers)
    
    assert res.status_code == 200, f"Failed: {res.text}"
    data = res.json()
    assert data["name"] == payload["name"]
    assert data["id"] is not None
    # Verify custom fields were saved
    assert data["custom_fields"] == {"segment": "vip"}

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

    # Second creation -> Should Fail (400 Bad Request or 409 Conflict)
    res2 = await client.post("/v1/api/contacts", json=payload_2, headers=auth_headers)
    assert res2.status_code in [400, 409]

async def test_get_contacts_pagination(client: AsyncClient, auth_headers):
    """
    Performance: Ensure listing contacts supports pagination.
    """
    # Create at least one contact to ensure list isn't empty (optional but good practice)
    await client.post("/v1/api/contacts", json={"name": "Pagination Test"}, headers=auth_headers)

    res = await client.get("/v1/api/contacts?skip=0&limit=5", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    
    assert isinstance(data, list)
    assert len(data) <= 5

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