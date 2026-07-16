"""Template Method base class for per-brokerage authentication strategies.

`authenticate()` is the fixed skeleton (validate -> call broker -> parse ->
log); concrete subclasses (one per brokerage, e.g. `AngelOneAuthStrategy`)
fill in the three broker-specific steps. `_dispatch_request` is a shared,
non-abstract helper for the HTTP mechanics every broker call has in common
(build the request from `BrokerageEndpoint`, send it, raise on failure) —
only the request body/headers and response field names vary by broker.

Deliberately does NOT persist to Redis — see `brokerage.services.session_cache
.BrokerSessionCache`, called by the orchestrator after `authenticate()`
returns, so a strategy's tests never need a Redis client just to exercise
credential validation or response parsing.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import httpx

from brokerage.exceptions import BrokerAPIError, InvalidBrokerCredentialsError

if TYPE_CHECKING:
    from accounts.models import User
    from brokerage.models import BrokerageEndpoint

logger = logging.getLogger(__name__)

DEFAULT_REQUEST_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class BrokerSession:
    """A brokerage's authenticated session, normalized to this app's own field names.

    `_parse_response` is the seam that translates a broker's raw response
    field names (e.g. Angel One's `jwtToken`/`feedToken`) into this shape —
    every broker needs its own `_parse_response` since none of them share a
    response schema. Deliberately excludes the broker's own refresh token
    (per this app's Redis contract — see `BrokerSessionCache` — the cached
    session is re-obtained via a fresh login, not refreshed).
    """

    jwt_token: str
    feed_token: str
    client_id: str


class BaseBrokerAuthStrategy(ABC):
    """Template Method skeleton for authenticating against one brokerage's API."""

    def __init__(
        self, endpoint: BrokerageEndpoint, http_client: httpx.Client | None = None
    ) -> None:
        """Initialize the strategy, optionally injecting an `httpx.Client`.

        Constructor injection (matching this codebase's established DI
        convention — see `TokenDenylist`/`PriceCacheService`) lets tests
        supply a fake client without making a real network call.
        """
        self.endpoint = endpoint
        self._http_client = http_client or httpx.Client(
            timeout=DEFAULT_REQUEST_TIMEOUT_SECONDS
        )

    def authenticate(
        self,
        user: User,
        link_data: dict[str, Any],
        login_secrets: dict[str, Any],
    ) -> BrokerSession:
        """Validate, call the broker, parse the response, and log the outcome.

        `link_data` is the user's stored `UserBrokerageLink.user_brokerage_data`
        (client_id, api_key — semi-stable identifiers set up once). `login_secrets`
        is the request body's one-time credentials (password, totp) — never
        persisted, live only for this call. Does NOT persist the resulting
        `BrokerSession` to Redis; that's the caller's responsibility.
        """
        brokerage_name = self.endpoint.brokerage.name
        try:
            self._validate_credentials(link_data, login_secrets)
            logger.info(f"{link_data=}, {login_secrets=} validated for broker auth.")
            raw_response = self._call_broker_api(link_data, login_secrets)
        except (InvalidBrokerCredentialsError, BrokerAPIError):
            logger.warning(
                "Broker auth call failed.",
                extra={"brokerage_name": brokerage_name, "user_id": user.id},
                exc_info=True,
            )
            raise
        session = self._parse_response(raw_response, link_data)
        logger.info(
            "Broker auth succeeded.",
            extra={"brokerage_name": brokerage_name, "user_id": user.id},
        )
        return session

    def logout(
        self,
        user: User,
        link_data: dict[str, Any],
        cached_session: dict[str, str],
    ) -> None:
        """Call the broker's logout endpoint using the cached session's jwt_token.

        A second template method alongside `authenticate()`, sharing the
        same `endpoint`/`_dispatch_request` machinery but with a different
        shape: no `login_secrets` (there's nothing fresh to submit — this
        call authenticates itself via the already-cached `jwt_token`) and no
        response-to-`BrokerSession` parsing (a logout response carries no
        session data to extract, only a success/failure status).

        `cached_session` is the dict `BrokerSessionCache.get()` returned —
        this method is only ever called once a cached session is confirmed
        to exist; the orchestrator handles the "nothing cached" short-circuit
        before reaching here. Raises `BrokerAPIError` if the broker's logout
        call fails; the orchestrator still clears the local Redis session
        either way (Django's cache, not the broker's own session state, is
        this app's source of truth for "is this user connected").
        """
        self._validate_logout_credentials(link_data, cached_session)
        self._call_broker_logout(link_data, cached_session)
        logger.info(
            "Broker logout succeeded.",
            extra={"brokerage_name": self.endpoint.brokerage.name, "user_id": user.id},
        )

    def _dispatch_request(
        self, *, headers: dict[str, str], body: dict[str, Any]
    ) -> dict[str, Any]:
        """Send the built request to `self.endpoint` and return the parsed JSON body.

        Shared across every broker: only the body/headers construction
        (broker-specific) and the response field extraction (in
        `_parse_response`) differ. Concrete strategies call this from
        `_call_broker_api` rather than opening their own `httpx` call, so
        timeout/connection-error handling and status checking live in
        exactly one place.
        """
        try:
            response = self._http_client.request(
                self.endpoint.http_method,
                self.endpoint.url,
                headers=headers,
                json=body if self.endpoint.payload_type == "JSON" else None,
                data=body if self.endpoint.payload_type == "FORM" else None,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise BrokerAPIError(f"Broker request failed: {exc}") from exc
        return cast(dict[str, Any], response.json())

    @abstractmethod
    def _validate_credentials(
        self, link_data: dict[str, Any], login_secrets: dict[str, Any]
    ) -> None:
        """Raise if `link_data`/`login_secrets` are missing fields this broker needs."""

    @abstractmethod
    def _call_broker_api(
        self, link_data: dict[str, Any], login_secrets: dict[str, Any]
    ) -> dict[str, Any]:
        """Build this broker's request shape and dispatch it via `_dispatch_request`."""

    @abstractmethod
    def _parse_response(
        self, raw_response: dict[str, Any], link_data: dict[str, Any]
    ) -> BrokerSession:
        """Extract this broker's token fields into a normalized `BrokerSession`.

        `link_data` is passed through (not just `raw_response`) because some
        brokers' login responses don't echo back an identifier like
        `client_id` — the caller already knows it from the stored link, so
        it doesn't need to be re-derived from a response field that may not
        exist.
        """

    @abstractmethod
    def _validate_logout_credentials(
        self, link_data: dict[str, Any], cached_session: dict[str, str]
    ) -> None:
        """Raise if `link_data`/`cached_session` lack fields needed to log out."""

    @abstractmethod
    def _call_broker_logout(
        self, link_data: dict[str, Any], cached_session: dict[str, str]
    ) -> None:
        """Build this broker's logout request and dispatch it via `_dispatch_request`.

        Raises `BrokerAPIError` if the broker reports the logout failed —
        unlike `_call_broker_api`, there's no successful return value to
        parse (a logout response carries no session data), so this returns
        `None` on success and only ever communicates failure via exception.
        """
