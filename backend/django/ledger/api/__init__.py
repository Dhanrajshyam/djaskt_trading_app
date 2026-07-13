"""REST contract layer for the ledger app (Django Ninja Extra).

Contains the Pydantic/Ninja request-response schemas (`schemas.py`) and the
class-based `LedgerController` (`router.py`) that exposes the ledger's
service layer over HTTP. Validation and authorization happen here;
business logic does not — see `ledger.services` for that.
"""
