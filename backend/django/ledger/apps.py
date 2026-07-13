"""Django app configuration for the `ledger` app."""

from django.apps import AppConfig


class LedgerConfig(AppConfig):
    """App config for the ledger app.

    Registers the `ledger` app with Django using the default auto field
    behavior; no custom `ready()` hooks are needed since the app has no
    signal handlers to wire up at startup.
    """

    name = 'ledger'
