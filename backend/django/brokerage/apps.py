"""Django app configuration for the `brokerage` app."""

from django.apps import AppConfig


class BrokerageConfig(AppConfig):
    """App config for the brokerage app.

    Registers the `brokerage` app with Django using the default auto field
    behavior; no custom `ready()` hooks are needed since the app has no
    signal handlers to wire up at startup.
    """

    name = "brokerage"
