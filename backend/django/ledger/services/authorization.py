"""Shared object-level authorization helpers.

A single source of truth for "does this user own this portfolio" so the
check can't drift between the REST contract layer and the WebSocket layer
(OWASP A01 — broken access control).
"""

import logging

from ledger.models import Portfolio

logger = logging.getLogger(__name__)


def get_owned_portfolio_or_none(user, portfolio_id) -> Portfolio | None:
    """Return the Portfolio identified by `portfolio_id` only if `user` owns it.

    Returns None both when the portfolio doesn't exist and when it belongs to
    someone else — callers must not distinguish the two in their response,
    to avoid leaking which portfolio IDs exist to unauthorized users.
    """
    portfolio = Portfolio.objects.for_user(user).filter(id=portfolio_id).first()
    if portfolio is None:
        # OWASP A01 signal: an authenticated user requested a portfolio they
        # don't own (or that doesn't exist) — worth its own alertable
        # pattern in ELK, distinct from a plain "not found".
        logger.warning(
            "Portfolio access denied: not found or not owned by requesting user.",
            extra={"user_id": getattr(user, "id", None), "portfolio_id": str(portfolio_id)},
        )
    return portfolio
