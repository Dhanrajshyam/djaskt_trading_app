"""User accounts app: authentication identity for the Djaskt platform.

Owns the custom `User` model (email-based login, see `models.py`) and the
signup/login/refresh/logout REST endpoints (`api.py`). Kept separate from
`ledger` because identity/authentication is a distinct concern from the
trading domain — `ledger.Portfolio` links to `accounts.User` via a
one-to-one relationship, but nothing in this app knows about trades.
"""
