"""Angel One authentication strategy.

Implements Angel One's `loginByPassword` contract: POST clientcode/password/
totp/state as JSON, with `X-PrivateKey` (the user's stored API key) as a
header; response nests tokens under `data.jwtToken`/`data.feedToken`.
"""

from typing import Any

from brokerage.exceptions import BrokerAPIError, InvalidBrokerCredentialsError
from brokerage.strategies.base import BaseBrokerAuthStrategy, BrokerSession


class AngelOneAuthStrategy(BaseBrokerAuthStrategy):
    """Authenticates against Angel One's `loginByPassword` endpoint."""

    def _validate_credentials(
        self, link_data: dict[str, Any], login_secrets: dict[str, Any]
    ) -> None:
        """Require a stored client_id/api_key and a submitted password/totp."""
        if not link_data.get("client_id"):
            raise InvalidBrokerCredentialsError(
                "Angel One link is missing a client_id."
            )
        if not link_data.get("api_key"):
            raise InvalidBrokerCredentialsError("Angel One link is missing an api_key.")
        if not login_secrets.get("password"):
            raise InvalidBrokerCredentialsError("Angel One login requires a password.")
        if not login_secrets.get("totp"):
            raise InvalidBrokerCredentialsError("Angel One login requires a totp.")

    def _call_broker_api(
        self, link_data: dict[str, Any], login_secrets: dict[str, Any]
    ) -> dict[str, Any]:
        """Build Angel One's clientcode/password/totp body and dispatch it."""
        headers = {
            **self.endpoint.default_headers,
            "X-PrivateKey": link_data["api_key"],
        }
        body = {
            "clientcode": link_data["client_id"],
            "password": login_secrets["password"],
            "totp": login_secrets["totp"],
            "state": "live",
        }
        return self._dispatch_request(headers=headers, body=body)

    def _parse_response(
        self, raw_response: dict[str, Any], link_data: dict[str, Any]
    ) -> BrokerSession:
        """Extract jwtToken/feedToken from Angel One's nested `data` object.

        Angel One's response body doesn't echo `clientcode` back, so
        `client_id` comes from `link_data` (the stored identifier used to
        build the request) rather than the response. Raises `BrokerAPIError`
        if the response doesn't report success or is missing an expected
        field — never returns a partially-populated `BrokerSession`.
        """
        if raw_response.get("status") is not True:
            message = raw_response.get("message", "Angel One login failed.")
            raise BrokerAPIError(f"Angel One rejected the login: {message}")

        data = raw_response.get("data") or {}
        try:
            return BrokerSession(
                jwt_token=data["jwtToken"],
                feed_token=data["feedToken"],
                client_id=link_data["client_id"],
            )
        except KeyError as exc:
            raise BrokerAPIError(
                f"Angel One response missing expected field: {exc}"
            ) from exc

    def _validate_logout_credentials(
        self, link_data: dict[str, Any], cached_session: dict[str, str]
    ) -> None:
        """Require a stored client_id/api_key and a cached jwt_token."""
        if not link_data.get("client_id"):
            raise InvalidBrokerCredentialsError(
                "Angel One link is missing a client_id."
            )
        if not link_data.get("api_key"):
            raise InvalidBrokerCredentialsError("Angel One link is missing an api_key.")
        if not cached_session.get("jwt_token"):
            raise InvalidBrokerCredentialsError(
                "No cached Angel One jwt_token to log out with."
            )

    def _call_broker_logout(
        self, link_data: dict[str, Any], cached_session: dict[str, str]
    ) -> None:
        """Build Angel One's clientcode-only logout body and dispatch it.

        Authenticates via the cached `jwt_token` as a Bearer token (this is
        what distinguishes logout from login — no fresh password/TOTP is
        submitted) plus `X-PrivateKey` from the stored link, matching Angel
        One's real logout contract.
        """
        headers = {
            **self.endpoint.default_headers,
            "Authorization": f"Bearer {cached_session['jwt_token']}",
            "X-PrivateKey": link_data["api_key"],
        }
        body = {"clientcode": link_data["client_id"]}
        raw_response = self._dispatch_request(headers=headers, body=body)
        if raw_response.get("status") is not True:
            message = raw_response.get("message", "Angel One logout failed.")
            raise BrokerAPIError(f"Angel One rejected the logout: {message}")
