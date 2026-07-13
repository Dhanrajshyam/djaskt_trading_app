"""Django app configuration for the `accounts` app."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """App config for the accounts app.

    Registers the `accounts` app with Django using the default auto field
    behavior; no custom `ready()` hooks are needed since the app has no
    signal handlers to wire up at startup.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
