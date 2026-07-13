"""Live price lookups against the Redis cache populated by the FastAPI
Market Data Firehose service.

Django never talks to FastAPI directly — both services integrate purely
through the shared Redis keyspace, matching the system architecture diagram.
"""

import json
from decimal import Decimal, InvalidOperation

import redis
from django.conf import settings

from ledger.exceptions import PriceUnavailableError

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
        touching a real Redis instance.
        """
        self._redis = redis_client or redis.Redis.from_url(
            settings.REDIS_URL, decode_responses=True
        )

    def get_live_price(self, ticker: str) -> Decimal:
        """Return the current live price for `ticker`.

        Raises `PriceUnavailableError` if the price key is missing (never
        written or expired past its 10-second TTL), malformed, or
        non-positive — a trade must never execute against stale or invalid
        market data.
        """
        key = PRICE_KEY_TEMPLATE.format(ticker=ticker.upper())
        raw = self._redis.get(key)
        if raw is None:
            raise PriceUnavailableError(
                f"No live price available for '{ticker}' (missing or expired cache entry)."
            )

        try:
            payload = json.loads(raw)
            price = Decimal(str(payload["price"]))
        except (json.JSONDecodeError, KeyError, InvalidOperation, TypeError) as exc:
            raise PriceUnavailableError(
                f"Malformed price payload for '{ticker}' in cache."
            ) from exc

        if price <= 0:
            raise PriceUnavailableError(f"Invalid non-positive price cached for '{ticker}'.")

        return price
