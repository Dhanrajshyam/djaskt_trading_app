"""JWT authentication with per-request Redis denylist checking.

Standard `ninja_jwt.authentication.JWTAuth` only verifies a token's
signature and expiry — it has no revocation concept unless
`ninja_jwt.token_blacklist` (a DB-backed app, intentionally not installed
here) is configured. `DenylistCheckingJWTAuth` layers a Redis lookup on
top of that verification so a revoked token (via `/auth/logout/`, or the
prior refresh token during rotation) stops working on its very next
request — not just once it naturally expires. This matters more for a
financial ledger than a typical API: a stolen or logged-out access token
could otherwise keep moving money until its `exp` claim passes.
"""

from typing import cast

from django.contrib.auth.models import AbstractBaseUser
from django.http import HttpRequest
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.exceptions import InvalidToken
from ninja_jwt.settings import api_settings
from ninja_jwt.tokens import Token

from extensions.token_denylist import TokenDenylist


class DenylistCheckingJWTAuth(JWTAuth):
    """`JWTAuth` extended with a Redis denylist check on every request.

    Verification order: signature/expiry first (via the parent class —
    cheapest failure path, no Redis round-trip for a token that's already
    invalid on its face), then the denylist check. A token that fails
    either step is rejected identically (401), so a client can't
    distinguish "expired" from "revoked" by response shape.
    """

    def __init__(self, denylist: TokenDenylist | None = None) -> None:
        """Initialize the auth class, optionally injecting a `TokenDenylist`.

        Constructor injection (rather than instantiating one internally)
        lets tests supply a fake denylist without touching Redis. The
        denylist itself is built lazily (see `_get_denylist`), not here —
        `auth=` instances are constructed at controller class-decoration
        time (module import), and ninja-extra's route registration
        deep-copies operation metadata including the auth instance; a
        live `redis.Redis` client (holding a threading lock internally)
        can't survive that deepcopy, so no Redis connection may be built
        eagerly in `__init__`.
        """
        super().__init__()
        self._denylist = denylist

    def _get_denylist(self) -> TokenDenylist:
        """Return the injected denylist, or lazily build the default one."""
        if self._denylist is None:
            self._denylist = TokenDenylist()
        return self._denylist

    def authenticate(self, request: HttpRequest, token: str) -> AbstractBaseUser:
        """Verify the JWT and reject it if it's been individually or mass-revoked.

        Delegates to `validate_and_get_user`, then attaches the result to
        `request.user` — the one piece of behavior specific to the REST
        (HttpRequest-based) auth path. `ledger.realtime.auth` calls
        `validate_and_get_user` directly for WebSocket connections, which
        have no `HttpRequest` to attach a user to.
        """
        user = self.validate_and_get_user(token)
        # HttpRequest.user is typed User | AnonymousUser by django-stubs,
        # but ninja_jwt's authenticate() contract is to attach the resolved
        # AbstractBaseUser here regardless of concrete type — matches the
        # base JWTAuth.authenticate() implementation being overridden.
        request.user = user  # type: ignore[assignment]
        return user

    def validate_and_get_user(self, token: str) -> AbstractBaseUser:
        """Verify a raw JWT and return its user, checking Redis revocation.

        Decodes the token once (via `get_validated_token`) and reuses that
        result for the single-token denylist check, the "logout everywhere"
        cutoff check, and user resolution, rather than letting the token be
        parsed twice. Checks the cheap single-`jti` denylist first, then
        the per-user cutoff — both are O(1) Redis lookups, ordering here is
        just for readability, not performance.

        This is the shared core both `authenticate()` (REST, has an
        `HttpRequest`) and `ledger.realtime.auth.authenticate_first_message`
        (WebSocket, no `HttpRequest`) call, so token validation and
        revocation logic can't drift between the two transports.
        """
        # ninja_jwt.authentication.JWTAuth.get_validated_token is mistyped
        # upstream as `-> Type[Token]` (a class) when it actually returns a
        # `Token` instance (confirmed by reading the real implementation:
        # `return AuthToken(raw_token)`) — this cast corrects it to the real
        # runtime type so `.get(...)` below resolves to Token's actual
        # instance method instead of an unbound-method false positive.
        validated_token = cast(Token, self.get_validated_token(token))
        jti_claim = api_settings.JTI_CLAIM or "jti"
        jti = validated_token.get(jti_claim)
        if jti and self._get_denylist().is_denied(jti):
            raise InvalidToken("Token has been revoked.")

        user_id = validated_token.get(api_settings.USER_ID_CLAIM)
        issued_at = validated_token.get("iat")
        if (
            user_id is not None
            and issued_at is not None
            and self._get_denylist().is_denied_for_user(user_id, issued_at)
        ):
            raise InvalidToken("All sessions for this account have been logged out.")

        return self.get_user(validated_token)
