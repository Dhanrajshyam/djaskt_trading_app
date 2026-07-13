"""Infisical Vault integration for sourcing secrets at settings-load time.

Wraps the official `infisicalsdk` client in a thread-safe singleton
(`InfisicalVaultManager`) that `django_app/settings.py` uses to fetch
`SECRET_KEY`, `DB_PASSWORD`/`REPLICA_DB_PASSWORD`, and `REDIS_URL` from
Infisical, falling back to `.env`/OS environment variables when Vault isn't
configured or isn't reachable. This module never hardcodes a secret value
or falls back to one itself — callers decide what to do when both sources
come up empty.
"""

import logging
import os
import threading
from typing import Optional

from infisical_sdk import InfisicalSDKClient
from infisical_sdk.infisical_requests import InfisicalError

logger = logging.getLogger(__name__)


class VaultNotConfiguredError(Exception):
    """Raised when no Vault machine identity credentials are present.

    This is the expected, non-error state for local development before a
    machine identity has been provisioned in Infisical — callers should
    treat it as a signal to fall back to `.env`/OS environment variables,
    not as an outage.
    """


class VaultSecretUnavailableError(Exception):
    """Raised when Vault is configured but a secret could not be retrieved.

    Covers authentication failure (after one defensive retry), network
    errors, and secrets that don't exist under the configured project/
    environment/path.
    """


class InfisicalVaultManager:
    """Thread-safe singleton wrapper around the Infisical Python SDK.

    Authentication is lazy: the constructor only reads configuration from
    the OS environment (no network I/O), and the first call to
    `get_secret()` triggers Universal Auth login. This keeps importing this
    module (and instantiating the module-level `vault` singleton below)
    safe to do unconditionally at Django settings-load time, even when
    Vault is unreachable or unconfigured.
    """

    _instance: Optional["InfisicalVaultManager"] = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "InfisicalVaultManager":
        """Enforce thread-safe singleton instantiation."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Read Vault connection parameters from the OS environment.

        No network calls happen here — only `get_secret()` triggers
        authentication, and only on first use.
        """
        if self._initialized:
            return

        self.vault_url = os.getenv("INFISICAL_URL", "http://localhost:8081").rstrip("/")
        self.client_id = os.getenv("INFISICAL_CLIENT_ID")
        self.client_secret = os.getenv("INFISICAL_CLIENT_SECRET")
        self.project_id = os.getenv("INFISICAL_PROJECT_ID")
        self.default_environment = os.getenv("INFISICAL_ENVIRONMENT", "dev")
        self.secret_path = os.getenv("INFISICAL_SECRET_PATH", "/")

        self._client = InfisicalSDKClient(host=self.vault_url)
        self._authenticated = False
        self._auth_lock = threading.Lock()
        self._initialized = True

    def _authenticate(self) -> None:
        """Log in via Universal Auth, if not already authenticated.

        Raises `VaultNotConfiguredError` immediately (no network call) if
        machine identity credentials aren't set at all — the normal state
        before Vault has been provisioned for this environment.
        """
        if self._authenticated:
            return

        if not self.client_id or not self.client_secret:
            raise VaultNotConfiguredError(
                "INFISICAL_CLIENT_ID / INFISICAL_CLIENT_SECRET are not set; "
                "Vault machine identity is not configured."
            )

        with self._auth_lock:
            if self._authenticated:
                return
            try:
                self._client.auth.universal_auth.login(
                    client_id=self.client_id, client_secret=self.client_secret
                )
            except InfisicalError as exc:
                # Never log client_secret or any secret value — only
                # identifiers and outcomes (OWASP A09 / sensitive data
                # exposure).
                logger.error(
                    "Vault authentication failed.",
                    extra={"vault_url": self.vault_url},
                )
                raise VaultSecretUnavailableError(
                    f"Failed to authenticate with Infisical Vault: {exc}"
                ) from exc
            logger.info(
                "Authenticated with Infisical Vault.",
                extra={"vault_url": self.vault_url},
            )
            self._authenticated = True

    def get_secret(self, secret_name: str, environment: str | None = None) -> str:
        """Return the value of `secret_name` from Vault.

        Authenticates lazily on first call. If a call fails after a
        successful prior authentication (e.g. the access token expired —
        the SDK's own token-refresh behavior isn't documented, so this is
        a defensive measure rather than an assumption), retries once after
        forcing a fresh login before giving up.

        Raises `VaultNotConfiguredError` if no machine identity is
        configured, or `VaultSecretUnavailableError` if Vault is configured
        but the secret can't be retrieved (auth failure, network error,
        missing secret). Never returns a default value — that decision
        belongs to the caller.
        """
        self._authenticate()
        try:
            return self._fetch(secret_name, environment)
        except InfisicalError:
            # Defensive re-auth: force a fresh login once, in case the
            # cached token expired, then retry a single time.
            logger.warning(
                "Secret fetch failed; retrying after a fresh Vault login.",
                extra={"secret_name": secret_name},
            )
            self._authenticated = False
            self._authenticate()
            try:
                return self._fetch(secret_name, environment)
            except InfisicalError as exc:
                logger.error(
                    "Secret unavailable in Vault after retry.",
                    extra={"secret_name": secret_name},
                )
                raise VaultSecretUnavailableError(
                    f"Secret '{secret_name}' not found or unreachable in Vault: {exc}"
                ) from exc

    def _fetch(self, secret_name: str, environment: str | None) -> str:
        """Perform the actual `get_secret_by_name` SDK call and return its value."""
        secret = self._client.secrets.get_secret_by_name(
            secret_name=secret_name,
            project_id=self.project_id,
            environment_slug=environment or self.default_environment,
            secret_path=self.secret_path,
        )
        return secret.secretValue


# Module-level singleton, imported directly by django_app/settings.py.
vault = InfisicalVaultManager()
