import os
import json
import functools
import redis
from typing import Any, Callable, Optional


_redis_pool: Optional[redis.ConnectionPool] = None


def get_redis_pool() -> redis.ConnectionPool:
    global _redis_pool
    if _redis_pool is None:
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
        _redis_pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=50,
            decode_responses=True
        )
    return _redis_pool


class CacheManager:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.environ.get('REDIS_URL', 'redis://localhost:6379')
        self._client = None
        self._stats = {'hits': 0, 'misses': 0, 'errors': 0}
        self._connect()

    def _connect(self):
        try:
            self._client = redis.Redis(connection_pool=get_redis_pool())
            self._client.ping()
        except redis.RedisError:
            self._client = None

    def get(self, key: str) -> Optional[Any]:
        if self._client is None:
            self._connect()
        if self._client is None:
            self._stats['misses'] += 1
            return None
        try:
            result = self._client.get(key)
            if result is not None:
                self._stats['hits'] += 1
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    return result
            self._stats['misses'] += 1
            return None
        except redis.RedisError:
            self._stats['errors'] += 1
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        if self._client is None:
            self._connect()
        if self._client is None:
            return False
        try:
            serialized = json.dumps(value)
            return self._client.setex(key, ttl, serialized)
        except redis.RedisError:
            self._stats['errors'] += 1
            return False

    def delete(self, key: str) -> bool:
        if self._client is None:
            self._connect()
        if self._client is None:
            return False
        try:
            return self._client.delete(key) > 0
        except redis.RedisError:
            self._stats['errors'] += 1
            return False

    def invalidate_pattern(self, pattern: str) -> int:
        if self._client is None:
            self._connect()
        if self._client is None:
            return 0
        try:
            keys = self._client.keys(pattern)
            if keys:
                return self._client.delete(*keys)
            return 0
        except redis.RedisError:
            self._stats['errors'] += 1
            return 0

    def get_stats(self) -> dict:
        return {
            'cache_hits': self._stats['hits'],
            'cache_misses': self._stats['misses'],
            'cache_errors': self._stats['errors'],
            'hit_rate': (
                self._stats['hits'] / (self._stats['hits'] + self._stats['misses'])
                if (self._stats['hits'] + self._stats['misses']) > 0
                else 0.0
            )
        }


_cache_manager: Optional[CacheManager] = None


def _get_cache_manager() -> CacheManager:
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def cached(ttl: int = 300, key_prefix: str = 'api'):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            cache = _get_cache_manager()

            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ':'.join(key_parts)

            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)

            return result

        return wrapper
    return decorator
