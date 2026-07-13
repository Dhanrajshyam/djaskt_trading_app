"""Domain-level exceptions for the ledger app.

These are raised by the service layer and translated to HTTP status codes by
the API contract layer (`ledger/api/router.py`). Keeping them here — rather
than inside `services/` — reflects that they describe the ledger domain
itself, not any one service's implementation.
"""


class LedgerServiceError(Exception):
    """Base class for all ledger domain errors."""


class PortfolioNotFoundError(LedgerServiceError):
    """Raised when the referenced portfolio does not exist."""


class PriceUnavailableError(LedgerServiceError):
    """Raised when no fresh live price is available for the requested ticker."""


class InsufficientFundsError(LedgerServiceError):
    """Raised when a BUY would overdraw the portfolio's cash balance."""


class InsufficientPositionError(LedgerServiceError):
    """Raised when a SELL exceeds the quantity currently held."""


class InvalidTradeRequestError(LedgerServiceError):
    """Raised for structurally invalid trade requests (bad type, non-positive quantity, etc.)."""
