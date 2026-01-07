"""
Redis client wrapper for caching natural language query results
"""
import json
import logging
from typing import Optional, Any
import redis.asyncio as redis
from app.config import REDIS_URL, NL_QUERY_CACHE_TTL

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Async Redis client for caching NL query results
    """

    def __init__(self, url: str = REDIS_URL):
        """
        Initialize Redis client

        Args:
            url: Redis connection URL
        """
        self.url = url
        self._client: Optional[redis.Redis] = None
        logger.info(f"[RedisClient] Initializing with URL: {url}")

    async def connect(self):
        """Establish Redis connection"""
        if self._client is None:
            logger.info("[RedisClient] Connecting to Redis...")
            self._client = await redis.from_url(
                self.url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
            )
            # Test connection
            await self._client.ping()
            logger.info("[RedisClient] Connected successfully")

    async def disconnect(self):
        """Close Redis connection"""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("[RedisClient] Disconnected")

    @property
    async def client(self) -> redis.Redis:
        """Get Redis client, connecting if needed"""
        if self._client is None:
            await self.connect()
        return self._client

    async def get(self, key: str) -> Optional[dict]:
        """
        Get cached value by key

        Args:
            key: Cache key

        Returns:
            Cached value as dict, or None if not found
        """
        try:
            client = await self.client
            value = await client.get(key)
            if value:
                logger.debug(f"[RedisClient] Cache HIT for key: {key}")
                return json.loads(value)
            logger.debug(f"[RedisClient] Cache MISS for key: {key}")
            return None
        except Exception as e:
            logger.error(f"[RedisClient] Error getting key {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = NL_QUERY_CACHE_TTL
    ) -> bool:
        """
        Set cache value with TTL

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds

        Returns:
            True if successful, False otherwise
        """
        try:
            client = await self.client
            await client.setex(
                key,
                ttl,
                json.dumps(value)
            )
            logger.debug(f"[RedisClient] Set key: {key} with TTL: {ttl}s")
            return True
        except Exception as e:
            logger.error(f"[RedisClient] Error setting key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete cache key

        Args:
            key: Cache key to delete

        Returns:
            True if deleted, False otherwise
        """
        try:
            client = await self.client
            result = await client.delete(key)
            logger.debug(f"[RedisClient] Deleted key: {key}")
            return result > 0
        except Exception as e:
            logger.error(f"[RedisClient] Error deleting key {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if key exists

        Args:
            key: Cache key

        Returns:
            True if exists, False otherwise
        """
        try:
            client = await self.client
            result = await client.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"[RedisClient] Error checking key {key}: {e}")
            return False

    async def increment(self, key: str) -> int:
        """
        Increment counter

        Args:
            key: Counter key

        Returns:
            New counter value
        """
        try:
            client = await self.client
            value = await client.incr(key)
            logger.debug(f"[RedisClient] Incremented {key} to {value}")
            return value
        except Exception as e:
            logger.error(f"[RedisClient] Error incrementing {key}: {e}")
            return 0


# Singleton instance
_redis_client: Optional[RedisClient] = None


async def get_redis_client() -> RedisClient:
    """
    Get singleton Redis client instance

    Returns:
        RedisClient instance
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
        await _redis_client.connect()
    return _redis_client


async def close_redis_client():
    """Close Redis client connection"""
    global _redis_client
    if _redis_client:
        await _redis_client.disconnect()
        _redis_client = None
