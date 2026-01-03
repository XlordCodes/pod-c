# app/core/cache.py
import json
import logging
from typing import Optional, Any
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Redis Client
# We use the service name "redis" from docker-compose
redis_client = redis.Redis(
    host=settings.REDIS_HOST, 
    port=settings.REDIS_PORT, 
    db=0, 
    decode_responses=True # Automatically decode bytes to strings
)

async def get_cache(key: str) -> Optional[Any]:
    """Retrieve data from Redis by key."""
    try:
        data = await redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        logger.error(f"Redis GET error: {e}")
        return None

async def set_cache(key: str, data: Any, expire: int = 60):
    """
    Store data in Redis.
    expire: Time in seconds (default 60s).
    """
    try:
        await redis_client.set(key, json.dumps(data), ex=expire)
    except Exception as e:
        logger.error(f"Redis SET error: {e}")

async def invalidate_cache(pattern: str):
    """Delete keys matching a pattern (e.g., 'contacts:*')."""
    try:
        keys = await redis_client.keys(pattern)
        if keys:
            await redis_client.delete(*keys)
    except Exception as e:
        logger.error(f"Redis DELETE error: {e}")