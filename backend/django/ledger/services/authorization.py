"""Shared object-level authorization helpers.

A single source of truth for "does this user own this portfolio" so the
check can't drift between the REST contract layer and the WebSocket layer
(OWASP A01 — broken access control).
"""

import logging
import uuid
from typing import TYPE_CHECKING

from ledger.models import Portfolio

if TYPE_CHECKING:
    from accounts.models import User

logger = logging.getLogger(__name__)


def get_owned_portfolio_or_none(
    user: User, portfolio_id: uuid.UUID | str
) -> Portfolio | None:
    """Return the Portfolio identified by `portfolio_id` only if `user` owns it.

    Returns None both when the portfolio doesn't exist and when it belongs to
    someone else — callers must not distinguish the two in their response,
    to avoid leaking which portfolio IDs exist to unauthorized users. Used
    where a client supplies a portfolio ID directly (e.g. the WebSocket
    route's URL-embedded `portfolio_id`, a plain `str` since that route is a
    regex `re_path`, not a `<uuid:...>` converter) — REST trade/cash-transfer
    endpoints no longer take a client-supplied ID at all (see
    `get_portfolio_for_user`), since `Portfolio.user` is a strict
    one-to-one relationship and there's nothing to check ownership *of*.
    """
    portfolio = Portfolio.objects.for_user(user).filter(id=portfolio_id).first()
    if portfolio is None:
        # OWASP A01 signal: an authenticated user requested a portfolio they
        # don't own (or that doesn't exist) — worth its own alertable
        # pattern in ELK, distinct from a plain "not found".
        logger.warning(
            "Portfolio access denied: not found or not owned by requesting user.",
            extra={
                "user_id": getattr(user, "id", None),
                "portfolio_id": str(portfolio_id),
            },
        )
    return portfolio


def get_portfolio_for_user(user: User) -> Portfolio | None:
    """Return the authenticated user's own portfolio, or None if they have none.

    `Portfolio.user` is a strict `OneToOneField` — every user has at most
    one portfolio, created at signup (see `create_user_portfolio`). This is
    the resolver REST endpoints use instead of trusting a client-supplied
    `portfolio_id`: there is no ID to validate ownership of, only "does
    this user have a portfolio at all" (a 404 case if not, not a 403 —
    there's no other user's data to have leaked information about).
    """
    return Portfolio.objects.filter(user=user).first()


def create_user_portfolio(user: User) -> Portfolio:
    """Create and return a new, zero-balance Portfolio for `user`.

    Called once, at signup (`accounts.api.AuthController.signup`) — the
    natural place to create it given the one-to-one relationship. Raises
    `django.db.IntegrityError` if the user already has a portfolio (the
    `OneToOneField` constraint), which should never happen in practice
    since this is only ever called from the signup flow for a brand-new
    user.
    """
    portfolio = Portfolio.objects.create(user=user)
    logger.info("Portfolio created for new user.", extra={"user_id": user.id})
    return portfolio
