# tests/integration/test_bulk.py
import pytest
from httpx import AsyncClient

# Mark all tests as asyncio
pytestmark = pytest.mark.asyncio

async def test_create_bulk_job(client: AsyncClient, auth_headers):
    """
    Test the creation of a bulk messaging job.
    Requires Authentication headers as per the updated API.
    """
    # Construct a sample payload for a bulk WhatsApp blast
    payload = {
        "template_name": "welcome_offer_2024",
        "language_code": "en_US",
        "numbers": ["919999999999", "918888888888"],
        # Optional: Add scheduled_at if you want to test scheduling
        # "scheduled_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()
    }
    
    # Endpoint: /v1/api/bulk/jobs
    # Fix: Added headers=auth_headers because the API now requires login
    res = await client.post("/v1/api/bulk/jobs", json=payload, headers=auth_headers)
    
    assert res.status_code in [200, 201], f"Bulk job creation failed: {res.text}"
    
    data = res.json()
    
    # Verify response structure
    assert data.get("status") in ["queued", "scheduled", "created"]
    
    # Check if the number of recipients matches
    if "numbers" in data:
        assert len(data["numbers"]) == 2