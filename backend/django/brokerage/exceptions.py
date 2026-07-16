"""Domain-level exceptions for the brokerage app.

These are raised by the strategy/service layer and translated to HTTP status
codes by the API contract layer (`brokerage/api/router.py`). Mirrors
`ledger.exceptions`'s flat, single-base-class shape.
"""


class BrokerageServiceError(Exception):
    """Base class for all brokerage domain errors."""


class UnknownBrokerError(BrokerageServiceError):
    """Raised when a `brokerage_name` has no registered strategy or active row."""


class NoBrokerageLinkError(BrokerageServiceError):
    """Raised when a user attempts to log in to a brokerage they haven't linked."""


class BrokerAPIError(BrokerageServiceError):
    """Raised when a brokerage's own API call fails (network, timeout, non-2xx,
    or a well-formed but unsuccessful response body)."""


class InvalidBrokerCredentialsError(BrokerageServiceError):
    """Raised when required link/login fields are missing before any broker call."""


class BrokerRateLimitedError(BrokerageServiceError):
    """Raised when a login is attempted before the brokerage's cooldown has elapsed."""
