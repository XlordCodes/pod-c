import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

async def test_create_bulk_job(client: AsyncClient):
    payload = {
        "template_name": "welcome",
        "language_code": "en_US",
        "numbers": ["919999999999", "918888888888"]
    }
    res = await client.post("/api/bulk/jobs", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "queued"
    assert len(data["numbers"]) == 2