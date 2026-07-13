"""Shared object-level authorization helpers.

A single source of truth for "does this user own this portfolio" so the
check can't drift between the REST contract layer and the WebSocket layer
(OWASP A01 — broken access control).
"""

from ledger.models import Portfolio


def get_owned_portfolio_or_none(user, portfolio_id) -> Portfolio | None:
    """Return the Portfolio identified by `portfolio_id` only if `user` owns it.

    Returns None both when the portfolio doesn't exist and when it belongs to
    someone else — callers must not distinguish the two in their response,
    to avoid leaking which portfolio IDs exist to unauthorized users.
    """
    return Portfolio.objects.for_user(user).filter(id=portfolio_id).first()
