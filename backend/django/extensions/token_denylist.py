"""Redis-backed JWT denylist for immediate token revocation.

django-ninja-jwt's own blacklist (`ninja_jwt.token_blacklist`) is hardcoded
to its own DB-backed models (`OutstandingToken`/`BlacklistedToken`) — not
pluggable via settings. This app intentionally does not install that
sub-app; instead, `ledger.api.auth.DenylistCheckingJWTAuth` checks this
Redis denylist on every authenticated request, not just at refresh time.

This is a denylist (only revoked token IDs are stored), not an allowlist
(storing every issued token) — the industry-standard shape, since an
allowlist would require a lookup-and-track step for every token ever
issued, reintroducing the per-request database/cache dependency JWTs exist
to avoid. A denylist entry only ever exists for a token someone explicitly
revoked (logout, or the previous refresh token during rotation), and
self-expires via Redis TTL matching the token's own remaining lifetime, so
there is no cleanup job to run.

Single-session logout (`deny`/`is_denied`) revokes one token by its `jti`.
Mass revocation ("log out everywhere", `deny_all_for_user`/
`is_denied_for_user`) uses a *timestamp cutoff* per user instead of
tracking every issued `jti` — one Redis write invalidates every token
(past and currently outstanding) issued before that moment, with no need
to maintain a growing per-user token registry.
"""

import redis

from extensions.redis_client import redis_manager

DENYLIST_KEY_TEMPLATE = "deny:{jti}"
USER_CUTOFF_KEY_TEMPLATE = "logout_all:{user_id}"

# How long a user's "logout everywhere" cutoff needs to stay in Redis: at
# least as long as the longest-lived token this app issues (the refresh
# token lifetime, NINJA_JWT["REFRESH_TOKEN_LIFETIME"]) — after that, every
# token that could have predated the cutoff has expired on its own anyway,
# so the cutoff key is safe to let expire too.
USER_CUTOFF_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days, matches REFRESH_TOKEN_LIFETIME


class TokenDenylist:
    """Records and checks revoked JWT tokens (single-session and mass revocation).

    Takes a Redis client via constructor injection (defaulting to the
    shared, process-wide client from `extensions.redis_client`) rather than
    constructing its own — matches the dependency-injection pattern already
    used throughout `ledger.services`, and avoids yet another Redis
    connection pool being built per instantiation.
    """

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        """Initialize the denylist, optionally injecting a Redis client.

        Accepting a client via constructor injection lets tests supply a
        fake client without touching a real Redis instance.
        """
        self._redis = redis_client or redis_manager.get_client()

    def deny(self, jti: str, ttl_seconds: int) -> None:
        """Revoke the token identified by `jti` for `ttl_seconds`.

        `ttl_seconds` should be the token's remaining lifetime (seconds
        until its own `exp` claim) — the denylist entry self-expires at the
        same moment the token itself would have stopped being valid
        anyway, so it never outlives the thing it's blocking. A
        non-positive `ttl_seconds` (an already-expired token) is a no-op:
        there's nothing to revoke that isn't already invalid.
        """
        if ttl_seconds <= 0:
            return
        self._redis.set(DENYLIST_KEY_TEMPLATE.format(jti=jti), "1", ex=ttl_seconds)

    def is_denied(self, jti: str) -> bool:
        """Return True if the token identified by `jti` has been revoked."""
        return bool(self._redis.exists(DENYLIST_KEY_TEMPLATE.format(jti=jti)))

    def deny_all_for_user(self, user_id: int, cutoff_timestamp: int) -> None:
        """Revoke every token issued to `user_id` at or before `cutoff_timestamp`.

        Used for "log out everywhere" — one write invalidates every
        outstanding session for the user (every device/browser they're
        logged into), without needing to know each token's `jti`
        individually. `cutoff_timestamp` should be the current time (an
        integer Unix timestamp); any token whose `iat` claim is not
        strictly after this value is treated as revoked by
        `is_denied_for_user`.
        """
        self._redis.set(
            USER_CUTOFF_KEY_TEMPLATE.format(user_id=user_id),
            str(cutoff_timestamp),
            ex=USER_CUTOFF_TTL_SECONDS,
        )

    def is_denied_for_user(self, user_id: int, issued_at: int) -> bool:
        """Return True if `issued_at` predates the user's logout-all cutoff.

        `issued_at` is the token's own `iat` claim. Tokens minted after a
        "logout everywhere" call (e.g. from a subsequent fresh login) have
        an `iat` after the cutoff and are correctly treated as valid.
        """
        cutoff = self._redis.get(USER_CUTOFF_KEY_TEMPLATE.format(user_id=user_id))
        if cutoff is None:
            return False
        return issued_at <= int(cutoff)
