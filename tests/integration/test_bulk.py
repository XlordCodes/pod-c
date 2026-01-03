# tests/integration/test_bulk.py
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

async def test_create_bulk_job(client: AsyncClient):
    """
    Test the creation of a bulk messaging job.
    This assumes the user has valid permissions or the endpoint is open for testing.
    """
    # Construct a sample payload for a bulk WhatsApp blast
    payload = {
        "template_name": "welcome_offer_2024",
        "language_code": "en_US",
        "numbers": ["919999999999", "918888888888"]
    }
    
    # Endpoint: /v1/api/bulk/jobs
    # Derived from main.py: prefix="/v1/api/bulk" + router path="/jobs"
    res = await client.post("/v1/api/bulk/jobs", json=payload)
    
    assert res.status_code in [200, 201], f"Bulk job creation failed: {res.text}"
    
    data = res.json()
    
    # Verify response structure
    # Adjust assertions based on your actual Pydantic response model
    assert data.get("status") in ["queued", "processing", "created"]
    
    # Check if the number of recipients matches (if your API echoes this back)
    if "numbers" in data:
        assert len(data["numbers"]) == 2