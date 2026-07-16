"""Broker authentication orchestration entry point.

The API layer should only ever import `BrokerAuthOrchestrator` — never
`BrokerSessionCache` or a strategy class directly. Coordinates: resolving
the brokerage/endpoint/link, enforcing a per-user login cooldown, calling the
strategy, and persisting the resulting session — the same
orchestration-then-persistence shape `ledger.services.main_service
.LedgerOrchestratorService` already has for trades.
"""

import logging
from typing import Any

import redis

from accounts.models import User
from brokerage.exceptions import (
    BrokerAPIError,
    BrokerRateLimitedError,
    NoBrokerageLinkError,
    UnknownBrokerError,
)
from brokerage.models import Brokerage, BrokerageEndpoint, UserBrokerageLink
from brokerage.services.session_cache import BrokerSessionCache
from brokerage.strategies.base import BrokerSession
from brokerage.strategies.registry import get_strategy_class
from extensions.redis_client import redis_manager

logger = logging.getLogger(__name__)

LOGIN_ENDPOINT_PURPOSE = "login"
LOGOUT_ENDPOINT_PURPOSE = "logout"

# Angel One's own throttle table caps loginByPassword at 1 request/second
# with no per-minute/hour ceiling (unlike order-placement endpoints, which
# do have minute/hour caps). This cooldown is sized comfortably above that
# ceiling — not a generic rate-limiting framework, a narrow guard against a
# retry loop or double-click getting a user's own broker account throttled
# or blocked by the broker itself. Each broker's own throttle number may
# differ; this default applies until a broker-specific value is needed.
LOGIN_COOLDOWN_SECONDS = 2
COOLDOWN_KEY_TEMPLATE = "login_cooldown_user_{user_id}_brokerage_{brokerage_name}"


class BrokerAuthOrchestrator:
    """Coordinates a broker login end-to-end: cooldown, auth, and caching.

    Constructor-injectable dependencies, matching this codebase's DI
    convention (`ledger.services.main_service.LedgerOrchestratorService`) —
    tests can supply fakes without touching Redis or the database.
    """

    def __init__(
        self,
        session_cache: BrokerSessionCache | None = None,
        redis_client: redis.Redis | None = None,
    ) -> None:
        """Initialize the orchestrator, optionally injecting its dependencies."""
        self._session_cache = session_cache or BrokerSessionCache()
        self._redis = redis_client or redis_manager.get_client()

    def authenticate_and_cache(
        self,
        *,
        user: User,
        brokerage_name: str,
        login_secrets: dict[str, Any],
    ) -> tuple[BrokerSession, int]:
        """Authenticate `user` against `brokerage_name` and cache the resulting session.

        Raises `UnknownBrokerError` if no strategy or active `Brokerage`/
        `BrokerageEndpoint` row exists, `NoBrokerageLinkError` if the user
        hasn't linked this brokerage yet (see `UserBrokerageLink`), and
        `BrokerRateLimitedError` if called again within the login cooldown
        window. Returns the `BrokerSession` and the TTL (seconds) actually
        applied to its Redis cache entry.
        """
        strategy_class = get_strategy_class(brokerage_name)
        brokerage, link = self._get_brokerage_and_link(user, brokerage_name)

        try:
            endpoint = BrokerageEndpoint.objects.get(
                brokerage=brokerage, purpose=LOGIN_ENDPOINT_PURPOSE
            )
        except BrokerageEndpoint.DoesNotExist as exc:
            raise UnknownBrokerError(
                f"No login endpoint configured for: {brokerage_name!r}"
            ) from exc

        self._enforce_login_cooldown(user.id, brokerage_name)

        strategy = strategy_class(endpoint)
        session = strategy.authenticate(user, link.user_brokerage_data, login_secrets)
        ttl_seconds = self._session_cache.store(user.id, brokerage_name, session)
        return session, ttl_seconds

    def logout_and_clear(self, *, user: User, brokerage_name: str) -> bool:
        """Log `user` out of `brokerage_name` and clear their cached session.

        Returns True if a broker logout call was actually made (a session
        was cached), False if there was nothing to do — idempotent, matching
        the confirmed "already logged out" behavior for a repeat call.
        Raises `UnknownBrokerError`/`NoBrokerageLinkError` under the same
        conditions as `authenticate_and_cache`. Does NOT raise on a
        broker-side logout failure (network error, broker rejects the
        call, or no logout `BrokerageEndpoint` configured) — the local
        Redis session is cleared regardless, since Django's cache (not the
        broker's own session state) is this app's source of truth for
        "is this user connected"; the failure is only logged.
        """
        strategy_class = get_strategy_class(brokerage_name)
        brokerage, link = self._get_brokerage_and_link(user, brokerage_name)

        cached_session = self._session_cache.get(user.id, brokerage_name)
        if cached_session is None:
            return False

        try:
            endpoint = BrokerageEndpoint.objects.get(
                brokerage=brokerage, purpose=LOGOUT_ENDPOINT_PURPOSE
            )
            strategy = strategy_class(endpoint)
            strategy.logout(user, link.user_brokerage_data, cached_session)
        except (BrokerageEndpoint.DoesNotExist, BrokerAPIError) as exc:
            logger.warning(
                "Broker-side logout failed; clearing local session anyway.",
                extra={
                    "brokerage_name": brokerage_name,
                    "user_id": user.id,
                    "reason": str(exc),
                },
            )
        finally:
            self._session_cache.delete(user.id, brokerage_name)
        return True

    @staticmethod
    def _get_brokerage_and_link(
        user: User, brokerage_name: str
    ) -> tuple[Brokerage, UserBrokerageLink]:
        """Resolve the active `Brokerage` and the caller's `UserBrokerageLink`.

        Shared by `authenticate_and_cache`/`logout_and_clear` so the two
        lookups (and their error mapping) can't drift between login and
        logout.
        """
        try:
            brokerage = Brokerage.objects.get(name=brokerage_name, is_active=True)
        except Brokerage.DoesNotExist as exc:
            raise UnknownBrokerError(
                f"No active brokerage configured for: {brokerage_name!r}"
            ) from exc

        link = (
            UserBrokerageLink.objects.for_user(user).filter(brokerage=brokerage).first()
        )
        if link is None:
            raise NoBrokerageLinkError(
                f"{user} has not linked brokerage {brokerage_name!r}."
            )
        return brokerage, link

    def _enforce_login_cooldown(self, user_id: int, brokerage_name: str) -> None:
        """Reject a login attempt if one for the same user/broker just ran.

        Uses `SET ... NX EX` — an atomic check-and-set in one round trip —
        so concurrent requests can't both pass the check before either sets
        the key.
        """
        key = COOLDOWN_KEY_TEMPLATE.format(
            user_id=user_id, brokerage_name=brokerage_name
        )
        acquired = self._redis.set(key, "1", nx=True, ex=LOGIN_COOLDOWN_SECONDS)
        if not acquired:
            logger.warning(
                "Broker login rejected: cooldown still active.",
                extra={"user_id": user_id, "brokerage_name": brokerage_name},
            )
            raise BrokerRateLimitedError(
                f"Login to {brokerage_name!r} was attempted too recently; "
                f"wait {LOGIN_COOLDOWN_SECONDS}s and try again."
            )
