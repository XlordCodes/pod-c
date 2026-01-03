# tests/integration/test_auth.py
import pytest
import uuid
from httpx import AsyncClient

# Mark all tests in this module as asyncio to avoid decorating every function
pytestmark = pytest.mark.asyncio

async def test_auth_flow(client: AsyncClient):
    """
    Test the full authentication lifecycle:
    Register -> Login (Get Token) -> Access Protected Route
    """
    # Generate a random email to ensure the test is repeatable without 
    # hitting unique constraint violations in the database.
    random_id = uuid.uuid4().hex[:8]
    email = f"tester_{random_id}@ryze.com"
    password = "secure_password_123"

    # 1. Register
    # Endpoint: /v1/auth/register (Prefix defined in main.py)
    reg_payload = {
        "email": email, 
        "password": password, 
        "name": "Integration Tester"
    }
    
    res = await client.post("/v1/auth/register", json=reg_payload)
    
    # Expect 201 Created or 200 OK depending on your specific implementation
    assert res.status_code in [200, 201], f"Registration failed: {res.text}"
    data = res.json()
    assert data["email"] == email

    # 2. Login
    # Endpoint: /v1/auth/token
    login_data = {
        "username": email, 
        "password": password
    }
    
    res = await client.post("/v1/auth/token", data=login_data)
    assert res.status_code == 200, f"Login failed: {res.text}"
    
    token_data = res.json()
    token = token_data["access_token"]
    assert token is not None

    # 3. Access Protected Route
    # Endpoint: /v1/auth/users/me (Assuming standard naming convention)
    headers = {"Authorization": f"Bearer {token}"}
    
    res = await client.get("/v1/auth/users/me", headers=headers)
    assert res.status_code == 200, f"Protected route access failed: {res.text}"
    
    user_data = res.json()
    assert user_data["email"] == email