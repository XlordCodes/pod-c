# tests/unit/test_cache_mock.py
import pytest
import json
from unittest.mock import AsyncMock, patch
from app.core.cache import get_cache, set_cache

# Mark all tests as asyncio since the cache functions are async
pytestmark = pytest.mark.asyncio

async def test_get_cache_hit():
    """
    Test that get_cache correctly parses JSON data from Redis.
    We MOCK Redis so we don't need a real connection.
    """
    # 1. Create a fake Redis client
    mock_redis = AsyncMock()
    
    # 2. Configure behavior: "When .get() is called, return this JSON string"
    mock_redis.get.return_value = json.dumps({"status": "cached_success"})
    
    # 3. Patch the real redis_client used inside app.core.cache
    # Note: We must patch the object WHERE IT IS IMPORTED/USED, not where it is defined.
    with patch("app.core.cache.redis_client", mock_redis):
        result = await get_cache("test_key")
    
    # 4. Verify results
    assert result == {"status": "cached_success"}
    
    # 5. Verify interaction
    mock_redis.get.assert_called_once_with("test_key")

async def test_get_cache_miss():
    """
    Test behavior when Redis returns None (cache miss).
    """
    mock_redis = AsyncMock()
    # Simulate Redis returning None (key not found)
    mock_redis.get.return_value = None
    
    with patch("app.core.cache.redis_client", mock_redis):
        result = await get_cache("missing_key")
        
    assert result is None
    mock_redis.get.assert_called_once_with("missing_key")

async def test_set_cache_failure():
    """
    Test that our code gracefully handles Redis downtime during a SET operation.
    It should log the error but NOT crash the application.
    """
    mock_redis = AsyncMock()
    # Simulate a crash/exception when .set() is called
    mock_redis.set.side_effect = Exception("Redis Connection Refused")
    
    with patch("app.core.cache.redis_client", mock_redis):
        # This should log an error internally but NOT raise an exception to the caller
        try:
            await set_cache("key", "data")
        except Exception as e:
            pytest.fail(f"set_cache raised an exception unexpectedly: {e}")
        
    # If we reached here without crashing, the test passed.
    mock_redis.set.assert_called_once()