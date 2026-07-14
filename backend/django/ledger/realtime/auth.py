"""First-message JWT authentication for WebSocket connections.

The REST API authenticates via a JWT `Authorization: Bearer <token>` header
(see `ledger.api.auth.DenylistCheckingJWTAuth`) — but a browser's native
`WebSocket` constructor cannot set custom headers, and putting the token in
the connection URL (`?token=...`) leaks it into server/proxy access logs and
browser history. Instead, this module authenticates *after* the WebSocket
handshake completes: the client connects, then sends one JSON message
carrying its access token before anything else happens. The token never
appears in a URL, header, or log line for the handshake itself.

Reuses `DenylistCheckingJWTAuth.validate_and_get_user` — the same
signature/expiry checks and Redis denylist/logout-all checks the REST API
uses — so a revoked or expired access token is rejected identically on
both transports, from one source of truth.
"""

import json
from typing import TYPE_CHECKING

from django.contrib.auth.models import AbstractBaseUser
from ninja_jwt.exceptions import AuthenticationFailed, TokenError

from ledger.api.auth import DenylistCheckingJWTAuth

if TYPE_CHECKING:
    from accounts.models import User

# How long a newly-connected socket has to send its auth message before
# being closed. Bounds how many unauthenticated sockets can sit open at
# once (a lightweight resource-exhaustion guard), without needing a token
# in the handshake itself.
AUTH_MESSAGE_TIMEOUT_SECONDS = 5


class WebSocketAuthError(Exception):
    """Raised when the first message isn't a valid, currently-good auth message.

    Callers (the consumer) catch this and close the connection with an
    appropriate code — the message here is for server-side logging only,
    never sent to the client directly.
    """


def authenticate_first_message(raw_message: str) -> User:
    """Validate the client's first WebSocket message and return its user.

    Expects `raw_message` to be a JSON string shaped like
    `{"type": "auth", "access_token": "<jwt>"}`. Raises
    `WebSocketAuthError` if the message is malformed, isn't an auth
    message, or the token is missing/invalid/expired/revoked.

    Synchronous (not a coroutine) since JSON parsing and JWT verification
    are both CPU-only — the consumer wraps this in `database_sync_to_async`
    for the one part (`get_user`) that does hit the database.
    """
    try:
        payload = json.loads(raw_message)
    except (json.JSONDecodeError, TypeError) as exc:
        raise WebSocketAuthError("First message was not valid JSON.") from exc

    if not isinstance(payload, dict) or payload.get("type") != "auth":
        raise WebSocketAuthError(
            "First message must be {'type': 'auth', 'access_token': ...}."
        )

    access_token = payload.get("access_token")
    if not access_token or not isinstance(access_token, str):
        raise WebSocketAuthError("Auth message missing a string access_token.")

    try:
        user: AbstractBaseUser = DenylistCheckingJWTAuth().validate_and_get_user(
            access_token
        )
    except (TokenError, AuthenticationFailed) as exc:
        # TokenError: bad signature/expired (raised by get_validated_token).
        # AuthenticationFailed (and its InvalidToken subclass): revoked via
        # denylist, or the user was deleted/deactivated since the token was
        # issued (raised by validate_and_get_user/get_user).
        raise WebSocketAuthError(f"Invalid or expired token: {exc}") from exc

    return user  # type: ignore[return-value]
