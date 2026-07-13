"""Live price lookups against the Redis cache populated by the FastAPI
Market Data Firehose service.

Django never talks to FastAPI directly — both services integrate purely
through the shared Redis keyspace, matching the system architecture diagram.
"""

import json
import logging
from decimal import Decimal, InvalidOperation

import redis

from extensions.redis_client import redis_manager
from ledger.exceptions import PriceUnavailableError

logger = logging.getLogger(__name__)

PRICE_KEY_TEMPLATE = "TICKER:{ticker}:PRICE"


class PriceCacheService:
    """Reads live ticker prices written by the market-data service.

    The upstream writer sets each key with a 10-second TTL, so a missing key
    is the correct signal to treat the price as stale/unavailable rather than
    falling back to any cached or default value — trades must never execute
    against data older than the TTL allows.
    """

    def __init__(self, redis_client: "redis.Redis | None" = None) -> None:
        """Initialize the service, optionally injecting a Redis client.

        Accepting a client via constructor injection (rather than always
        constructing one internally) lets tests supply a fake client without
        touching a real Redis instance. When no client is injected, reuses
        the shared, process-wide client from `extensions.redis_client`
        instead of building a new one — `PriceCacheService` (and the
        `TradeExecutionService`/`LedgerOrchestratorService`/`LedgerController`
        chain above it) is constructed fresh on every REST request, so
        defaulting to a fresh `redis.Redis.from_url(...)` here would rebuild
        a whole connection pool per request instead of reusing one for the
        life of the process.
        """
        self._redis = redis_client or redis_manager.get_client()

    def get_live_price(self, ticker: str) -> Decimal:
        """Return the current live price for `ticker`.

        Raises `PriceUnavailableError` if the price key is missing (never
        written or expired past its 10-second TTL), malformed, non-positive,
        or if Redis itself is unreachable — a trade must never execute
        against stale, invalid, or unconfirmed market data.
        """
        key = PRICE_KEY_TEMPLATE.format(ticker=ticker.upper())
        try:
            raw = self._redis.get(key)
        except redis.RedisError as exc:
            logger.warning(
                "Price cache unreachable; Redis connection failed.",
                extra={"ticker": ticker},
            )
            raise PriceUnavailableError(
                f"Price cache unreachable while looking up '{ticker}'."
            ) from exc

        if raw is None:
            logger.warning(
                "No live price available (missing or expired cache entry).",
                extra={"ticker": ticker},
            )
            raise PriceUnavailableError(
                f"No live price available for '{ticker}' (missing or expired cache entry)."
            )

        try:
            payload = json.loads(raw)
            price = Decimal(str(payload["price"]))
        except (json.JSONDecodeError, KeyError, InvalidOperation, TypeError) as exc:
            logger.warning(
                "Malformed price payload in cache.",
                extra={"ticker": ticker},
            )
            raise PriceUnavailableError(
                f"Malformed price payload for '{ticker}' in cache."
            ) from exc

        if price <= 0:
            logger.warning(
                "Invalid non-positive price cached.",
                extra={"ticker": ticker, "price": str(price)},
            )
            raise PriceUnavailableError(f"Invalid non-positive price cached for '{ticker}'.")

        return price
