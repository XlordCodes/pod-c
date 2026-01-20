# tests/integration/test_auth.py
import pytest
import uuid
from httpx import AsyncClient

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

async def test_auth_flow(client: AsyncClient):
    """
    Test the full authentication lifecycle:
    Register -> Login (Get Token) -> Access Protected Route
    """
    # Unique email to avoid collision
    random_id = uuid.uuid4().hex[:8]
    email = f"tester_{random_id}@ryze.com"
    password = "secure_password_123"

    # 1. Register
    # FIX: Updated path to match router.py (/v1/api/auth/register)
    reg_payload = {
        "email": email, 
        "password": password, 
        "name": "Integration Tester",
        "tenant_id": 1  # Often required for tenant isolation logic
    }
    
    res = await client.post("/v1/api/auth/register", json=reg_payload)
    
    # Assert
    assert res.status_code in [200, 201], f"Registration failed: {res.text}"
    data = res.json()
    assert data["email"] == email

    # 2. Login
    # FIX: Updated path to match router.py (/v1/api/auth/token)
    login_data = {
        "username": email, 
        "password": password
    }
    
    res = await client.post("/v1/api/auth/token", data=login_data)
    assert res.status_code == 200, f"Login failed: {res.text}"
    
    token_data = res.json()
    token = token_data["access_token"]
    assert token is not None

    # 3. Access Protected Route
    # Endpoint: /v1/api/auth/users/me
    headers = {"Authorization": f"Bearer {token}"}
    
    res = await client.get("/v1/api/auth/users/me", headers=headers)
    assert res.status_code == 200, f"Protected route access failed: {res.text}"
    
    user_data = res.json()
    assert user_data["email"] == email