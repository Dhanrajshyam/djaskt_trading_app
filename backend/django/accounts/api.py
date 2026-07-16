"""Authentication REST endpoints: signup, login, token refresh, logout.

No JWT library ships signup/logout endpoints — they're inherently
application-specific (password validation, what "logout" means for this
app's revocation model). This module builds all four on top of
`django-ninja-jwt`'s token machinery: `EmailTokenObtainPairInputSchema`
customizes login to key off `email` and to expire access tokens at UTC
midnight (capped at 24h) instead of ninja_jwt's fixed-timedelta default;
`/logout/` and the refresh-rotation path both write to the Redis denylist
(`extensions.token_denylist`) rather than ninja_jwt's DB-backed blacklist,
which is intentionally not installed (see `django_app/settings.py`).
"""

import logging
from datetime import datetime, timedelta
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone
from ninja import Schema
from ninja_extra import api_controller, http_post
from ninja_extra.permissions import AllowAny
from ninja_jwt.exceptions import TokenError
from ninja_jwt.schema import TokenObtainPairInputSchema, TokenObtainPairOutputSchema
from ninja_jwt.settings import api_settings
from ninja_jwt.tokens import AccessToken, RefreshToken
from pydantic import EmailStr

from extensions.token_denylist import TokenDenylist
from ledger.api.auth import DenylistCheckingJWTAuth
from ledger.services.authorization import create_user_portfolio

logger = logging.getLogger(__name__)

User = get_user_model()


def _seconds_until_utc_midnight(now: datetime) -> timedelta:
    """Return the timedelta from `now` to the next UTC midnight, capped at 24h.

    E.g. 11:00 -> 13:00:00 (13h) until 00:00 the same day; 00:05 -> ~23h55m
    until the following midnight. The cap only ever matters at exactly
    midnight itself (a zero-length window), included defensively so this
    function can never return a lifetime longer than 24h.
    """
    tomorrow = now + timedelta(days=1)
    midnight = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    return min(midnight - now, timedelta(hours=24))


class EmailTokenObtainPairInputSchema(TokenObtainPairInputSchema):
    """Login schema: authenticates by `email` (this app's `USERNAME_FIELD`),
    and mints an access token that expires at UTC midnight rather than
    ninja_jwt's fixed `ACCESS_TOKEN_LIFETIME`.

    `TokenObtainPairInputSchema` already resolves its username field from
    `get_user_model().USERNAME_FIELD` (confirmed via `ninja_jwt.schema`
    reading `user_name_field` at import time) — since `accounts.User` sets
    `USERNAME_FIELD = "email"`, the inherited field is already named
    `email`; only `get_token()` needs overriding here.
    """

    @classmethod
    def get_token(cls, user: AbstractUser) -> dict[str, str]:
        """Build refresh + access tokens, with a UTC-midnight-capped access expiry.

        `RefreshToken.access_token` (the normal path) always uses the
        class-level `AccessToken.lifetime` (bound to the fixed
        `NINJA_JWT["ACCESS_TOKEN_LIFETIME"]` setting) with no per-call
        override — so the access token is built manually here instead,
        copying `RefreshToken`'s claims (matching what `.access_token`
        does internally) and then explicitly overriding its `exp` claim.
        """
        refresh = cast(RefreshToken, RefreshToken.for_user(user))

        access = AccessToken()
        for claim, value in refresh.payload.items():
            if claim in refresh.no_copy_claims:
                continue
            access[claim] = value

        now = timezone.now()
        access.set_exp(from_time=now, lifetime=_seconds_until_utc_midnight(now))

        return {"refresh": str(refresh), "access": str(access)}


class SignupInputSchema(Schema):
    """Payload for `POST /api/v1/auth/signup/`."""

    email: EmailStr
    password: str
    first_name: str = ""
    last_name: str = ""


class SignupResponseSchema(Schema):
    """Response body for a successful signup."""

    email: str
    first_name: str
    last_name: str


class RefreshInputSchema(Schema):
    """Payload for `POST /api/v1/auth/token/refresh/`."""

    refresh: str


class LogoutInputSchema(Schema):
    """Payload for `POST /api/v1/auth/logout/`.

    Both tokens are optional individually but at least one must be
    provided — logout should revoke whichever tokens the client still
    holds, and a client may have already discarded one of the two.
    """

    access: str | None = None
    refresh: str | None = None


class LogoutResponseSchema(Schema):
    """Response body for a successful logout."""

    detail: str


class ErrorSchema(Schema):
    """Generic error response body used across the auth endpoints."""

    detail: str


@api_controller("/auth", tags=["auth"], permissions=[AllowAny])
class AuthController:
    """Signup, login, token refresh, and logout endpoints.

    Login/refresh delegate to `django-ninja-jwt`'s token schemas (customized
    via `EmailTokenObtainPairInputSchema` for email login + midnight-capped
    expiry); signup and logout are fully custom, since no JWT library
    provides either.
    """

    def __init__(self) -> None:
        """Initialize the controller with its own denylist instance."""
        self._denylist = TokenDenylist()

    @http_post(
        "/signup/",
        response={201: SignupResponseSchema, 409: ErrorSchema},
        url_name="auth_signup",
    )
    def signup(
        self, request: HttpRequest, payload: SignupInputSchema
    ) -> tuple[int, SignupResponseSchema | ErrorSchema]:
        """Create a new user account and their portfolio.

        Returns 409 if the email is already registered. Portfolio creation
        happens in the same call (not a signal) so account creation stays
        a single, traceable, testable operation — see
        `ledger.services.authorization.create_user_portfolio`.
        """
        if User.objects.filter(email=payload.email).exists():
            return 409, ErrorSchema(detail="An account with this email already exists.")

        with transaction.atomic():
            # username is auto-derived from the email local-part by
            # UserManager._create_user (accounts.models) — not passed here.
            user = User.objects.create_user(
                email=payload.email,
                password=payload.password,
                first_name=payload.first_name,
                last_name=payload.last_name,
            )
            create_user_portfolio(user)

        logger.info("New user signed up.", extra={"user_id": user.id})
        return 201, SignupResponseSchema(
            email=user.email, first_name=user.first_name, last_name=user.last_name
        )

    @http_post(
        "/login/",
        response={200: TokenObtainPairOutputSchema, 401: ErrorSchema},
        url_name="auth_login",
    )
    def login(
        self, request: HttpRequest, payload: EmailTokenObtainPairInputSchema
    ) -> tuple[int, Any]:
        """Authenticate by email + password, returning a refresh/access token pair.

        The access token expires at UTC midnight (capped at 24h) rather
        than a fixed lifetime — see `EmailTokenObtainPairInputSchema`.

        Return type is `tuple[int, Any]` rather than a precise schema union:
        `to_response_schema()` builds its return value dynamically from
        `EmailTokenObtainPairInputSchema.get_token()`'s dict via ninja_jwt's
        own schema machinery, with no static type exposed for it to narrow to.
        """
        payload.check_user_authentication_rule()
        return 200, payload.to_response_schema()

    @http_post(
        "/token/refresh/",
        response={200: TokenObtainPairOutputSchema, 401: ErrorSchema},
        url_name="auth_token_refresh",
    )
    def refresh(
        self, request: HttpRequest, payload: RefreshInputSchema
    ) -> tuple[int, Any]:
        """Exchange a refresh token for a new access/refresh pair.

        Always rotates the refresh token (denylisting the old one in Redis)
        regardless of `NINJA_JWT` settings — ninja_jwt's own
        `ROTATE_REFRESH_TOKENS`/`BLACKLIST_AFTER_ROTATION` write to its
        DB-backed blacklist app, which isn't installed here, so rotation is
        implemented directly against the Redis denylist instead.
        """
        try:
            old_refresh = RefreshToken(payload.refresh)
        except TokenError as exc:
            return 401, ErrorSchema(detail=str(exc))

        # api_settings.JTI_CLAIM/USER_ID_CLAIM are typed str | None (a
        # settings object that could theoretically be overridden to None),
        # but always resolve to a real string in practice — same pattern as
        # ledger.api.auth.DenylistCheckingJWTAuth.authenticate.
        jti_claim = api_settings.JTI_CLAIM or "jti"
        user_id_claim = api_settings.USER_ID_CLAIM or "user_id"

        old_jti = old_refresh[jti_claim]
        if self._denylist.is_denied(old_jti):
            # Reused a refresh token that was already rotated away (or
            # explicitly logged out) — reject rather than silently minting
            # another pair, since a legitimate client never needs to reuse
            # a refresh token it already exchanged.
            return 401, ErrorSchema(detail="Refresh token has been revoked.")

        user = User.objects.get(
            **{api_settings.USER_ID_FIELD: old_refresh[user_id_claim]}
        )

        old_exp = old_refresh["exp"]
        remaining_ttl = old_exp - int(timezone.now().timestamp())
        self._denylist.deny(old_jti, ttl_seconds=remaining_ttl)

        token_data = EmailTokenObtainPairInputSchema.get_token(user)
        logger.info("Refresh token rotated.", extra={"user_id": user.id})
        # TokenObtainPairOutputSchema's non-token field is named after
        # USERNAME_FIELD (AuthUserSchema.Meta.fields = [user_name_field]) —
        # "email" for this app's User model, not "user_id". This field is
        # added dynamically at runtime (confirmed: TokenObtainPairOutputSchema
        # .model_fields includes "email"), which mypy's static stub can't
        # see — hence the ignore, not a real invalid-kwarg error.
        return 200, TokenObtainPairOutputSchema(
            email=user.email,  # type: ignore[call-arg]
            **token_data,
        )

    @http_post(
        "/logout/",
        response={200: LogoutResponseSchema},
        auth=DenylistCheckingJWTAuth(),
        url_name="auth_logout",
    )
    def logout(
        self, request: HttpRequest, payload: LogoutInputSchema
    ) -> tuple[int, LogoutResponseSchema]:
        """Revoke the caller's access and/or refresh token immediately.

        Requires a valid (not-yet-revoked) access token to call this
        endpoint at all (enforced by `DenylistCheckingJWTAuth`), then
        denylists whichever of the access/refresh tokens the client
        supplied in the body. If never called, tokens simply expire
        naturally at their `exp` claim — logout only ever shortens a
        token's life early, it's not required for tokens to become invalid.
        """
        now_ts = int(timezone.now().timestamp())
        jti_claim = api_settings.JTI_CLAIM or "jti"

        for raw_token, token_cls in (
            (payload.access, AccessToken),
            (payload.refresh, RefreshToken),
        ):
            if not raw_token:
                continue
            try:
                token = token_cls(raw_token)
            except TokenError:
                continue
            jti = token[jti_claim]
            remaining_ttl = token["exp"] - now_ts
            self._denylist.deny(jti, ttl_seconds=remaining_ttl)

        logger.info("User logged out.", extra={"user_id": request.user.id})
        return 200, LogoutResponseSchema(detail="Logged out.")

    @http_post(
        "/logout-all/",
        response={200: LogoutResponseSchema},
        auth=DenylistCheckingJWTAuth(),
        url_name="auth_logout_all",
    )
    def logout_all(self, request: HttpRequest) -> tuple[int, LogoutResponseSchema]:
        """Revoke every access/refresh token issued to the caller, on every device.

        Unlike `/logout/` (which revokes only the specific token(s) the
        client sends), this needs no token in the body — it revokes by
        user ID, via a timestamp cutoff (see
        `extensions.token_denylist.TokenDenylist.deny_all_for_user`) rather
        than tracking every individual token ever issued. Any token
        already outstanding (on this device or any other) stops working on
        its very next request; a fresh login afterward works normally.
        """
        cutoff = int(timezone.now().timestamp())
        # request.user.id is int | None per django-stubs (AbstractBaseUser's
        # generic pk type), but DenylistCheckingJWTAuth on this action
        # guarantees an authenticated, persisted user with a real int pk.
        user_id = cast(int, request.user.id)
        self._denylist.deny_all_for_user(user_id, cutoff_timestamp=cutoff)
        logger.info("User logged out of all sessions.", extra={"user_id": user_id})
        return 200, LogoutResponseSchema(detail="Logged out of all sessions.")
