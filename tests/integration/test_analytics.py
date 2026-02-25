# tests/integration/test_analytics.py
"""
Module: Analytics API Integration Tests
Context: Pod C - Analytics Endpoints

Tests the Analytics API endpoints to ensure they return properly structured
responses and enforce authentication requirements.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def setup_analytics_views(db_session):
    """
    Fixture to create the required database views for analytics tests.
    
    Creates the v_avg_response materialized view that the avg-response
    endpoint depends on. This ensures tests run against a properly
    configured database schema.
    
    Args:
        db_session: The SQLAlchemy session fixture from conftest.py
    """
    # Create the v_avg_response view for avg response time analytics
    db_session.execute(text("""
        CREATE OR REPLACE VIEW v_avg_response AS 
        SELECT 
            conversation_id, 
            EXTRACT(EPOCH FROM MAX(created_at) - MIN(created_at)) / GREATEST(COUNT(*) - 1, 1) AS avg_response_seconds 
        FROM chat_messages 
        GROUP BY conversation_id
    """))
    db_session.commit()
    
    yield
    
    # Cleanup: Drop the view after tests
    db_session.execute(text("DROP VIEW IF EXISTS v_avg_response"))
    db_session.commit()


class TestAnalyticsKPIs:
    """
    Test suite for the KPIs analytics endpoint.
    """

    async def test_get_kpis_returns_200_with_auth(
        self, 
        client: AsyncClient, 
        auth_headers: dict
    ):
        """
        Test that GET /v1/api/analytics/kpis returns 200 OK when authenticated.
        
        Verifies:
        - Response status code is 200
        - Response contains expected KPI keys (sent, delivered, read, failed)
        """
        response = await client.get("/v1/api/analytics/kpis", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify the response contains the expected KPI keys
        assert "sent" in data, "Response missing 'sent' key"
        assert "delivered" in data, "Response missing 'delivered' key"
        assert "read" in data, "Response missing 'read' key"
        assert "failed" in data, "Response missing 'failed' key"

    async def test_get_kpis_returns_401_without_auth(self, client: AsyncClient):
        """
        Test that GET /v1/api/analytics/kpis returns 401 Unauthorized without authentication.
        
        Verifies:
        - Response status code is 401 when no auth headers are provided
        """
        response = await client.get("/v1/api/analytics/kpis")
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestAnalyticsSentiment:
    """
    Test suite for the Sentiment analytics endpoint.
    """

    async def test_get_sentiment_returns_200_with_auth(
        self, 
        client: AsyncClient, 
        auth_headers: dict
    ):
        """
        Test that GET /v1/api/analytics/sentiment returns 200 OK when authenticated.
        
        Verifies:
        - Response status code is 200
        - Response is a list (array of sentiment data)
        
        Note: The service queries the 'chat_messages' table. If the table doesn't exist
        or there's a database error, the error will bubble up (no silent swallowing).
        """
        response = await client.get("/v1/api/analytics/sentiment", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify the response is a list
        assert isinstance(data, list), f"Expected list, got {type(data).__name__}"

    async def test_get_sentiment_returns_401_without_auth(self, client: AsyncClient):
        """
        Test that GET /v1/api/analytics/sentiment returns 401 Unauthorized without authentication.
        
        Verifies:
        - Response status code is 401 when no auth headers are provided
        """
        response = await client.get("/v1/api/analytics/sentiment")
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestAnalyticsAvgResponse:
    """
    Test suite for the Average Response Time analytics endpoint.
    """

    async def test_get_avg_response_returns_200_with_auth(
        self, 
        client: AsyncClient, 
        auth_headers: dict
    ):
        """
        Test that GET /v1/api/analytics/avg-response returns 200 OK when authenticated.
        
        Verifies:
        - Response status code is 200
        - Response is a list (array of response time data)
        
        Note: The v_avg_response view is created by the setup_analytics_views fixture.
        """
        response = await client.get("/v1/api/analytics/avg-response", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify the response is a list
        assert isinstance(data, list), f"Expected list, got {type(data).__name__}"

    async def test_get_avg_response_returns_401_without_auth(self, client: AsyncClient):
        """
        Test that GET /v1/api/analytics/avg-response returns 401 Unauthorized without authentication.
        
        Verifies:
        - Response status code is 401 when no auth headers are provided
        """
        response = await client.get("/v1/api/analytics/avg-response")
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
