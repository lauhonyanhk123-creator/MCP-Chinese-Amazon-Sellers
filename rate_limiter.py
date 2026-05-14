#!/usr/bin/env python3
"""
Rate Limiter Module for Cross-Border Seller Web App
Provides rate limiting functionality based on user subscription tiers
"""

import os
import threading
import time
from functools import wraps
from typing import Any

from flask import Response, g, jsonify, request

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RateLimiter:
    TIER_LIMITS = {
        'FREE': {'requests': 100, 'period': 3600, 'description': 'Free Tier'},
        'BASIC': {'requests': 1000, 'period': 3600, 'description': 'Basic Tier'},
        'PRO': {'requests': 10000, 'period': 3600, 'description': 'Pro Tier'},
        'ENTERPRISE': {'requests': -1, 'period': 3600, 'description': 'Enterprise Tier (Unlimited)'}
    }

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._redis_client = None
        self._memory_store: dict[str, dict[str, Any]] = {}
        self._memory_lock = threading.Lock()

        if REDIS_AVAILABLE:
            try:
                redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
                self._redis_client = redis.from_url(redis_url, decode_responses=True)
                self._redis_client.ping()
            except Exception:
                self._redis_client = None

        self._initialized = True

    def _get_user_identifier(self) -> str:
        if hasattr(g, 'user_id') and g.user_id:
            return f"user:{g.user_id}"
        if hasattr(g, 'session_id') and g.session_id:
            return f"session:{g.session_id}"
        return f"ip:{request.remote_addr}"

    def _get_redis_key(self, user_id: str, tier: str) -> str:
        current_hour = int(time.time() // 3600)
        return f"ratelimit:{user_id}:{tier}:{current_hour}"

    def get_tier_limits(self, tier: str) -> dict[str, Any]:
        tier = tier.upper()
        if tier not in self.TIER_LIMITS:
            tier = 'FREE'
        return self.TIER_LIMITS[tier].copy()

    def check_rate_limit(self, user_id: str | None = None, tier: str = 'FREE') -> tuple[bool, dict[str, Any]]:
        tier = tier.upper()
        limits = self.get_tier_limits(tier)

        if limits['requests'] == -1:
            return True, {
                'limit': -1,
                'remaining': -1,
                'reset': int(time.time()) + limits['period'],
                'tier': tier
            }

        identifier = user_id or self._get_user_identifier()
        key = self._get_redis_key(identifier, tier)
        current_time = int(time.time())
        window_start = (current_time // limits['period']) * limits['period']
        reset_time = window_start + limits['period']

        if self._redis_client:
            try:
                current_count = self._redis_client.get(key)
                current_count = int(current_count) if current_count else 0
            except Exception:
                current_count = 0
        else:
            with self._memory_lock:
                if key not in self._memory_store:
                    self._memory_store[key] = {'count': 0, 'window_start': window_start}
                entry = self._memory_store[key]
                if current_time >= window_start + limits['period']:
                    entry = {'count': 0, 'window_start': window_start}
                    self._memory_store[key] = entry
                current_count = entry['count']

        remaining = max(0, limits['requests'] - current_count)
        is_allowed = current_count < limits['requests']

        return is_allowed, {
            'limit': limits['requests'],
            'remaining': remaining,
            'reset': reset_time,
            'tier': tier
        }

    def get_remaining_requests(self, user_id: str | None = None, tier: str = 'FREE') -> int:
        tier = tier.upper()
        identifier = user_id or self._get_user_identifier()
        _, info = self.check_rate_limit(identifier, tier)
        return info['remaining']

    def increment_counter(self, user_id: str | None = None, tier: str = 'FREE') -> int:
        tier = tier.upper()
        identifier = user_id or self._get_user_identifier()
        key = self._get_redis_key(identifier, tier)
        limits = self.get_tier_limits(tier)
        current_time = int(time.time())
        window_start = (current_time // limits['period']) * limits['period']

        if limits['requests'] == -1:
            return -1

        if self._redis_client:
            try:
                pipe = self._redis_client.pipeline()
                pipe.incr(key)
                pipe.expire(key, limits['period'] + 60)
                results = pipe.execute()
                return results[0]
            except Exception:
                pass

        with self._memory_lock:
            if key not in self._memory_store:
                self._memory_store[key] = {'count': 0, 'window_start': window_start}
            entry = self._memory_store[key]
            if current_time >= window_start + limits['period']:
                entry = {'count': 0, 'window_start': window_start}
            entry['count'] += 1
            self._memory_store[key] = entry
            return entry['count']

    def reset_counter(self, user_id: str | None = None, tier: str = 'FREE') -> bool:
        tier = tier.upper()
        identifier = user_id or self._get_user_identifier()
        key = self._get_redis_key(identifier, tier)

        if self._redis_client:
            try:
                self._redis_client.delete(key)
                return True
            except Exception:
                return False

        with self._memory_lock:
            if key in self._memory_store:
                del self._memory_store[key]
            return True

    def get_rate_limit_info(self, user_id: str | None = None, tier: str = 'FREE') -> dict[str, Any]:
        tier = tier.upper()
        identifier = user_id or self._get_user_identifier()
        is_allowed, info = self.check_rate_limit(identifier, tier)
        info['is_allowed'] = is_allowed
        return info


_rate_limiter_instance = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        _rate_limiter_instance = RateLimiter()
    return _rate_limiter_instance


def rate_limit(tier: str = 'FREE'):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            limiter = get_rate_limiter()

            user_tier = tier
            user_id = None
            if hasattr(g, 'user_id') and g.user_id:
                user_id = g.user_id
            if hasattr(g, 'user_tier') and g.user_tier:
                user_tier = g.user_tier

            is_allowed, rate_info = limiter.check_rate_limit(user_id, user_tier)

            g.rate_limit_info = rate_info

            if not is_allowed:
                return jsonify({
                    'error': 'rate_limit_exceeded',
                    'message': get_text(request.args.get('lang', 'en'), 'rate_limit_exceeded'),
                    'retry_after': rate_info['reset'],
                    'try_again_in': get_text(request.args.get('lang', 'en'), 'try_again_in'),
                    'current_limit': get_text(request.args.get('lang', 'en'), 'current_limit'),
                    'upgrade_plan': get_text(request.args.get('lang', 'en'), 'upgrade_plan'),
                    'limit': rate_info['limit'],
                    'tier': rate_info['tier']
                }), 429

            limiter.increment_counter(user_id, user_tier)

            result = f(*args, **kwargs)

            if isinstance(result, tuple):
                response, status_code = result if len(result) == 2 else (result, 200)
            else:
                response, status_code = result, 200

            if isinstance(response, Response) or hasattr(response, 'headers'):
                response.headers['X-RateLimit-Limit'] = str(rate_info['limit'])
                response.headers['X-RateLimit-Remaining'] = str(rate_info['remaining'])
                response.headers['X-RateLimit-Reset'] = str(rate_info['reset'])

            return response, status_code if isinstance(result, tuple) else 200

        return decorated_function
    return decorator


def get_text(lang: str, key: str) -> str:
    from flask import current_app
    if hasattr(current_app, 'config') and 'TEXT' in current_app.config:
        text_dict = current_app.config['TEXT']
        return text_dict.get(lang, {}).get(key, key)
    return key


def add_rate_limit_headers(response: Response, rate_info: dict[str, Any] | None = None) -> Response:
    if rate_info is None:
        if hasattr(g, 'rate_limit_info'):
            rate_info = g.rate_limit_info
        else:
            return response

    response.headers['X-RateLimit-Limit'] = str(rate_info.get('limit', 0))
    response.headers['X-RateLimit-Remaining'] = str(rate_info.get('remaining', 0))
    response.headers['X-RateLimit-Reset'] = str(rate_info.get('reset', 0))
    return response


def get_user_tier_from_license() -> str:
    try:
        from license_manager import LicenseTier, get_license_manager
        license_mgr = get_license_manager()
        license_info = license_mgr.get_license_info()
        tier_map = {
            LicenseTier.FREE: 'FREE',
            LicenseTier.BASIC: 'BASIC',
            LicenseTier.PRO: 'PRO',
            LicenseTier.ENTERPRISE: 'ENTERPRISE'
        }
        return tier_map.get(license_info.tier, 'FREE')
    except Exception:
        return 'FREE'
