"""Dependency health checks used by the liveness/readiness endpoints.

Kept separate from the API controller (`django_app.urls`) so the actual
check logic — "is Postgres/Redis reachable" — is plain, testable functions
with no HTTP/Ninja concerns mixed in.
"""

import logging

import redis
from django.db import connections
from django.db.utils import OperationalError

from extensions.redis_client import redis_manager

logger = logging.getLogger(__name__)


def check_database(alias: str) -> bool:
    """Return True if the database connection named `alias` is reachable.

    Opens (or reuses) a connection and runs a trivial query — the cheapest
    possible proof the connection actually works, not just that config
    parsed. Never raises: connection failures are the expected "unhealthy"
    case for a readiness check, not a bug to propagate.
    """
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except OperationalError:
        logger.warning("Readiness check: database '%s' is unreachable.", alias)
        return False


def check_redis() -> bool:
    """Return True if the shared Redis client can reach the server.

    Never raises: a Redis outage is the expected "unhealthy" case for a
    readiness check, not a bug to propagate.
    """
    try:
        return bool(redis_manager.get_client().ping())
    except redis.RedisError:
        logger.warning("Readiness check: Redis is unreachable.")
        return False
