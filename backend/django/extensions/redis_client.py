"""Shared Redis client for the ledger service.

Wraps `redis.Redis` in a thread-safe singleton (`RedisClientManager`),
mirroring `extensions.vault.InfisicalVaultManager`'s pattern, so callers
throughout the app (currently `ledger.services.price_service.PriceCacheService`)
reuse one client/connection pool for the lifetime of the process instead of
constructing a fresh one — and paying for a fresh connection pool — on
every call site instantiation (e.g. once per REST request, since Ninja
Extra controllers and the service objects they build are instantiated
per-request).
"""

import threading

import redis
from django.conf import settings


class RedisClientManager:
    """Thread-safe singleton wrapper around a shared `redis.Redis` client.

    Unlike Vault, Redis has no separate authentication handshake to defer —
    the client object itself is the lazily-connecting resource. `redis.Redis
    .from_url()` doesn't eagerly open a TCP connection (redis-py connects
    lazily on first command), so "lazy" here means the client/connection
    pool is built on first use rather than at import time, not that there's
    a distinct auth step to postpone.
    """

    _instance: RedisClientManager | None = None
    _instance_lock = threading.Lock()
    # Declared here so mypy can resolve the attribute's type — see
    # extensions.vault.InfisicalVaultManager's identical pattern/comment.
    _initialized: bool

    def __new__(cls) -> RedisClientManager:
        """Enforce thread-safe singleton instantiation."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Prepare the manager without yet building a client.

        No connection is opened here — only `get_client()` builds (and
        thereafter reuses) the underlying `redis.Redis` instance.
        """
        if self._initialized:
            return

        self._client: redis.Redis | None = None
        self._client_lock = threading.Lock()
        self._initialized = True

    def get_client(self) -> redis.Redis:
        """Return the shared `redis.Redis` client, building it on first call.

        Every subsequent call returns the same client (and thus the same
        underlying connection pool) rather than constructing a new one —
        this is the actual latency win: a fresh `ConnectionPool` (and the
        TCP handshakes it eventually opens) is expensive to keep rebuilding
        on every request, and unnecessary once one shared pool exists.
        """
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    self._client = redis.Redis.from_url(
                        settings.REDIS_URL, decode_responses=True
                    )
        return self._client


# Module-level singleton, imported directly by callers (e.g. PriceCacheService).
redis_manager = RedisClientManager()
