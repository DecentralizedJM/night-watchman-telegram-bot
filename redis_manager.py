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

    # === JOINS, RAIDS, FORWARDS, REVIEWS ===

    async def record_join(self, chat_id: int, user_id: int, window_seconds: int) -> int:
        """Store a join and return how many joins fell inside the raid window."""
        if not self.enabled:
            return 0
        now = time.time()
        key = f"raid:{chat_id}"
        try:
            await self.redis.zadd(key, {str(user_id): now})
            await self.redis.zremrangebyscore(key, 0, now - window_seconds)
            await self.redis.expire(key, window_seconds)
            await self.redis.set(f"joined:{chat_id}:{user_id}", str(now), ex=14 * 86400)
            return int(await self.redis.zcard(key))
        except Exception as e:
            logger.error(f"Redis record join error: {e}")
            return 0

    async def get_join_time(self, chat_id: int, user_id: int) -> Optional[float]:
        if not self.enabled:
            return None
        try:
            value = await self.redis.get(f"joined:{chat_id}:{user_id}")
            return float(value) if value else None
        except Exception as e:
            logger.error(f"Redis get join time error: {e}")
            return None

    async def set_raid_mode(self, chat_id: int, ttl_seconds: int):
        if not self.enabled:
            return
        try:
            await self.redis.setex(f"raidmode:{chat_id}", ttl_seconds, "1")
        except Exception as e:
            logger.error(f"Redis set raid mode error: {e}")

    async def raid_mode_active(self, chat_id: int) -> bool:
        if not self.enabled:
            return False
        try:
            return await self.redis.exists(f"raidmode:{chat_id}") > 0
        except Exception as e:
            logger.error(f"Redis raid mode error: {e}")
            return False

    async def add_forward_strike(self, chat_id: int, user_id: int, ttl: int = 604800) -> int:
        if not self.enabled:
            return 0
        key = f"forwards:{chat_id}:{user_id}"
        try:
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, ttl)
            return int(count)
        except Exception as e:
            logger.error(f"Redis forward strike error: {e}")
            return 0

    async def remember_author(self, chat_id: int, message_id: int, user_id: int):
        if not self.enabled:
            return
        try:
            await self.redis.setex(f"author:{chat_id}:{message_id}", 86400, str(user_id))
        except Exception as e:
            logger.error(f"Redis remember author error: {e}")

    async def get_author(self, chat_id: int, message_id: int) -> Optional[int]:
        if not self.enabled:
            return None
        try:
            value = await self.redis.get(f"author:{chat_id}:{message_id}")
            return int(value) if value and str(value).isdigit() else None
        except Exception as e:
            logger.error(f"Redis get author error: {e}")
            return None

    async def store_review(self, token: str, payload: Dict, ttl: int = 86400):
        if not self.enabled:
            return
        try:
            await self.redis.setex(f"review:{token}", ttl, json.dumps(payload))
        except Exception as e:
            logger.error(f"Redis store review error: {e}")

    async def pop_review(self, token: str) -> Optional[Dict]:
        if not self.enabled:
            return None
        key = f"review:{token}"
        try:
            data = await self.redis.get(key)
            if not data:
                return None
            await self.redis.delete(key)
            return json.loads(data)
        except Exception as e:
            logger.error(f"Redis pop review error: {e}")
            return None

    async def add_scam_text(self, text: str):
        if not self.enabled or not text:
            return
        try:
            await self.redis.lpush("nightwatchman:scam_memory", text)
            await self.redis.ltrim("nightwatchman:scam_memory", 0, 199)
        except Exception as e:
            logger.error(f"Redis add scam text error: {e}")

    async def load_scam_texts(self) -> List[str]:
        if not self.enabled:
            return []
        try:
            values = await self.redis.lrange("nightwatchman:scam_memory", 0, 199)
            return list(values or [])
        except Exception as e:
            logger.error(f"Redis load scam texts error: {e}")
            return []
