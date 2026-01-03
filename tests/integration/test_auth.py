# tests/integration/test_auth.py
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

async def test_auth_flow(client: AsyncClient):
    """
    Test the full authentication lifecycle:
    Register -> Login (Get Token) -> Access Protected Route
    """
    # 1. Register
    reg_payload = {"email": "test@ryze.com", "password": "pass", "name": "Tester"}
    res = await client.post("/auth/register", json=reg_payload)
    
    # API returns 201 Created for successful registration
    assert res.status_code == 201
    assert res.json()["email"] == "test@ryze.com"

    # 2. Login
    login_data = {"username": "test@ryze.com", "password": "pass"}
    res = await client.post("/auth/token", data=login_data)
    assert res.status_code == 200
    token = res.json()["access_token"]
    assert token is not None

    # 3. Access Protected Route
    headers = {"Authorization": f"Bearer {token}"}
    res = await client.get("/auth/users/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["email"] == "test@ryze.com"