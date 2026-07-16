"""Redis cache for authenticated broker sessions.

Key format is `auth_user_<user_id>_brokerage_<brokerage_name>` — underscore-
delimited, per the confirmed contract (a deliberate departure from
`extensions.token_denylist`'s colon-delimited `deny:{jti}` convention; not a
typo). Sessions expire at the next IST midnight, not a fixed duration —
reusing `extensions.redis_client.redis_manager`'s shared client, matching
`extensions.token_denylist.TokenDenylist`'s constructor-injection pattern.
"""

from datetime import datetime, timedelta
from typing import cast
from zoneinfo import ZoneInfo

import redis

from brokerage.strategies.base import BrokerSession
from extensions.redis_client import redis_manager

KEY_TEMPLATE = "auth_user_{user_id}_brokerage_{brokerage_name}"

IST = ZoneInfo("Asia/Kolkata")


def seconds_until_ist_midnight(now: datetime) -> timedelta:
    """Return the timedelta from `now` to the next midnight in IST (UTC+5:30).

    Mirrors `accounts.api._seconds_until_utc_midnight`'s "convert now to the
    target timezone, find next local midnight, diff" shape, but is
    deliberately a separate function: that one governs Django's own JWT
    access-token expiry and is intentionally UTC — reusing it here would
    silently repurpose a helper meant for a different concern. `now` is
    converted to IST before finding the next local midnight, so this is
    correct regardless of the server's own timezone (this project runs with
    `TIME_ZONE = "UTC"`, `USE_TZ = True`).
    """
    now_ist = now.astimezone(IST)
    next_midnight_ist = (now_ist + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return next_midnight_ist - now_ist


class BrokerSessionCache:
    """Caches a user's authenticated broker session in Redis, keyed per brokerage.

    Constructor-injectable Redis client, exactly matching
    `extensions.token_denylist.TokenDenylist.__init__` — tests can supply a
    fake client without touching real Redis, and the shared connection pool
    is reused instead of building a new one per instantiation.
    """

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        """Initialize the cache, optionally injecting a Redis client."""
        self._redis = redis_client or redis_manager.get_client()

    def store(self, user_id: int, brokerage_name: str, session: BrokerSession) -> int:
        """Cache `session`, expiring at the next IST midnight.

        Uses a Redis pipeline so the hash write and its expiry are set
        atomically in one round trip — a crash between two separate calls
        would otherwise leave a hash with no TTL (a token that never
        expires, contradicting the whole point of the midnight cutoff).
        Returns the TTL actually applied, in seconds.
        """
        key = KEY_TEMPLATE.format(user_id=user_id, brokerage_name=brokerage_name)
        ttl_seconds = int(seconds_until_ist_midnight(datetime.now(IST)).total_seconds())

        pipe = self._redis.pipeline()
        pipe.hset(
            key,
            mapping={
                "jwt_token": session.jwt_token,
                "feed_token": session.feed_token,
                "client_id": session.client_id,
            },
        )
        pipe.expire(key, ttl_seconds)
        pipe.execute()
        return ttl_seconds

    def get(self, user_id: int, brokerage_name: str) -> dict[str, str] | None:
        """Return the cached session hash, or None if nothing is cached.

        `None` covers both "never logged in" and "the IST-midnight TTL
        already expired" — callers (the logout orchestrator) treat both the
        same way: nothing to disconnect.
        """
        key = KEY_TEMPLATE.format(user_id=user_id, brokerage_name=brokerage_name)
        # redis-py's stubs type hgetall's return as dict[bytes | str, bytes |
        # str] since the client is generically typed regardless of the
        # decode_responses setting — this app's shared client
        # (extensions.redis_client.redis_manager) is always constructed with
        # decode_responses=True, so values are always str at runtime; same
        # kind of stub/runtime mismatch ledger.api.auth.DenylistCheckingJWTAuth
        # already casts around for a different upstream library.
        session = cast(dict[str, str], self._redis.hgetall(key))
        return session or None

    def delete(self, user_id: int, brokerage_name: str) -> None:
        """Remove the cached session, if any. A no-op if nothing was cached."""
        key = KEY_TEMPLATE.format(user_id=user_id, brokerage_name=brokerage_name)
        self._redis.delete(key)
