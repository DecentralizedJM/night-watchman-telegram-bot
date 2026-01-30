import os
import logging
import json
import time
from typing import Optional, Any, List, Union, Dict
import redis.asyncio as redis
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class RedisManager:
    """
    Manages Redis connection and operations for the Night Watchman bot.
    Handles persistent storage for immunity, rate limits, and caching.
    """
    
    def __init__(self, url: str = None):
        """
        Initialize Redis manager.
        
        Args:
            url: Redis connection URL. If None, tries REDIS_URL from env.
        """
        self.url = url or os.getenv('REDIS_URL')
        self.redis: Optional[redis.Redis] = None
        self.enabled = False
        
        if self.url:
            try:
                self.redis = redis.from_url(self.url, decode_responses=True)
                self.enabled = True
                logger.info("✅ RedisManager initialized via URL")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Redis: {e}")
        else:
            logger.warning("⚠️ No REDIS_URL provided. Redis functionality disabled.")

    async def verify_connection(self) -> bool:
        """Verify Redis connection works"""
        if not self.redis:
            return False
        try:
            await self.redis.ping()
            logger.info("✅ Redis connection verified")
            return True
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self.enabled = False
            return False

    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()

    # === IMMUNITY / ENHANCED USERS ===

    async def add_immune_user(self, user_id: int) -> bool:
        """Add user to persistent immunity set"""
        if not self.enabled: return False
        try:
            await self.redis.sadd('nightwatchman:immune_users', str(user_id))
            return True
        except Exception as e:
            logger.error(f"Redis error adding immune user: {e}")
            return False

    async def is_user_immune(self, user_id: int) -> bool:
        """Check if user has immunity"""
        if not self.enabled: return False
        try:
            return await self.redis.sismember('nightwatchman:immune_users', str(user_id))
        except Exception as e:
            logger.error(f"Redis error checking immunity: {e}")
            return False

    async def remove_immune_user(self, user_id: int) -> bool:
        """Remove user from immunity set"""
        if not self.enabled: return False
        try:
            await self.redis.srem('nightwatchman:immune_users', str(user_id))
            return True
        except Exception as e:
            logger.error(f"Redis error removing immune user: {e}")
            return False

    async def get_immune_user_ids(self) -> List[int]:
        """Return all user IDs in the immune set (for startup cache)."""
        if not self.enabled:
            return []
        try:
            members = await self.redis.smembers('nightwatchman:immune_users')
            return [int(m) for m in members if str(m).isdigit()]
        except Exception as e:
            logger.error(f"Redis error getting immune users: {e}")
            return []

    # === SPAM DETECTION / RATE LIMITS ===

    async def check_rate_limit(self, key: str, limit: int, window_seconds: int) -> bool:
        """
        Check rate limit using sliding window or simple counter.
        Returns True if LIMIT EXCEEDED (blocked), False if allowed.
        """
        if not self.enabled: return False
        try:
            # key example: "rate:media:12345:chat6789"
            current = await self.redis.incr(key)
            if current == 1:
                await self.redis.expire(key, window_seconds)
            
            return current > limit
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            return False

    async def add_warning(self, user_id: int, chat_id: int, ttl: int = 86400) -> int:
        """Increment warning count and return new count"""
        if not self.enabled: return 0
        key = f"warnings:{chat_id}:{user_id}"
        try:
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, ttl)
            return count
        except Exception as e:
            logger.error(f"Redis warning error: {e}")
            return 0

    async def get_warnings(self, user_id: int, chat_id: int) -> int:
        """Get current warning count"""
        if not self.enabled: return 0
        key = f"warnings:{chat_id}:{user_id}"
        try:
            val = await self.redis.get(key)
            return int(val) if val else 0
        except Exception as e:
            logger.error(f"Redis get warnings error: {e}")
            return 0

    async def clear_warnings(self, user_id: int, chat_id: int):
        """Clear warnings for a user"""
        if not self.enabled: return
        key = f"warnings:{chat_id}:{user_id}"
        try:
            await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Redis clear warnings error: {e}")

    # === COOLDOWNS ===

    async def set_cooldown(self, key_prefix: str, user_id: int, ttl: int):
        """Set a cooldown flag"""
        if not self.enabled: return
        key = f"cooldown:{key_prefix}:{user_id}"
        try:
            await self.redis.setex(key, ttl, "1")
        except Exception as e:
            logger.error(f"Redis set cooldown error: {e}")

    async def check_cooldown(self, key_prefix: str, user_id: int) -> bool:
        """Check if cooldown is active"""
        if not self.enabled: return False
        key = f"cooldown:{key_prefix}:{user_id}"
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis check cooldown error: {e}")
            return False

    async def get_cooldown_ttl(self, key_prefix: str, user_id: int) -> int:
        """Get remaining cooldown time in seconds"""
        if not self.enabled: return 0
        key = f"cooldown:{key_prefix}:{user_id}"
        try:
            ttl = await self.redis.ttl(key)
            return max(0, ttl)
        except Exception as e:
            logger.error(f"Redis get TTL error: {e}")
            return 0

    # === REPUTATION / CAS ===

    async def cache_cas_result(self, user_id: int, result: Dict, ttl: int = 86400):
        """Cache CAS check result"""
        if not self.enabled: return
        key = f"cas_cache:{user_id}"
        try:
            await self.redis.setex(key, ttl, json.dumps(result))
        except Exception as e:
            logger.error(f"Redis cache CAS error: {e}")

    async def get_cas_cache(self, user_id: int) -> Optional[Dict]:
        """Get cached CAS result"""
        if not self.enabled: return None
        key = f"cas_cache:{user_id}"
        try:
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Redis get CAS cache error: {e}")
        return None
