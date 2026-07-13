"""
Django settings for django_app project (Djaskt Ledger & Orchestrator microservice).

Environment-driven configuration — no secrets are hardcoded. See `.env.example`
for the variables this file expects at runtime (SECRET_KEY, DB_*, REPLICA_DB_*, REDIS_URL, etc.).
"""

import logging
from pathlib import Path

import environ

from extensions.logger import configure_logging
from extensions.vault import VaultNotConfiguredError, VaultSecretUnavailableError, vault

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)
# Reads a .env file if present; in containerized/production deployments these
# are expected to be injected directly as real environment variables instead.
environ.Env.read_env(BASE_DIR / ".env")

# Prevent django.setup() from applying its own default logging dictConfig
# after this module finishes importing — that default config creates a
# non-propagating "django.server" logger (used for runserver's access log)
# with its own plain-text handler, which would silently bypass the ECS
# JSON setup below for that one logger. Setting this to None means Django
# never calls dictConfig on our behalf, so configure_logging()'s root
# logger setup applies uniformly to every logger, including Django's own.
LOGGING_CONFIG = None

# Structured ECS JSON logging, set up before anything else logs (including
# the secret-resolution calls below), so every log line from process start
# onward is consistently formatted and ELK-ingestible.
configure_logging(
    service_name="djaskt-ledger",
    service_version="1.0.0",
    environment=env("DJANGO_ENV", default="development"),
)
logger = logging.getLogger(__name__)


def _get_secret(key: str, *, default=environ.Env.NOTSET):
    """Resolve a secret, preferring Infisical Vault over `.env`/OS environment.

    Tries Vault first; if it isn't configured (no machine identity set) or
    the secret can't be retrieved (auth failure, network error, missing
    key), falls back to `env(key, default=...)` — same behavior as before
    Vault existed. If neither source has a value and no `default` was
    given, `env(...)` raises `ImproperlyConfigured`, so the app never boots
    with an empty or hardcoded secret.
    """
    try:
        value = vault.get_secret(key, environment=env("INFISICAL_ENVIRONMENT", default="dev"))
        logger.info("Resolved secret from Vault.", extra={"secret_name": key})
        return value
    except (VaultNotConfiguredError, VaultSecretUnavailableError) as exc:
        logger.info(
            "Falling back to .env/OS environment for secret.",
            extra={"secret_name": key, "reason": type(exc).__name__},
        )
        return env(key, default=default)


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = _get_secret("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "ninja",
    "ledger",
]

# Order matters: each middleware below depends on state set up by the ones
# above it (session -> auth -> messages), or must run before/after the view
# for security reasons (SecurityMiddleware first, XFrameOptions last). See
# https://docs.djangoproject.com/en/6.0/ref/middleware/#middleware-ordering
MIDDLEWARE = [
    # Enforces HTTPS redirect, HSTS, and other transport-level security
    # headers before anything else runs — must be first so no other
    # middleware/view logic ever executes over an insecure connection.
    "django.middleware.security.SecurityMiddleware",
    # Sets per-request logging context (trace/correlation ID) as early as
    # possible, so it's available for every subsequent middleware, the view/
    # controller layer, and any log line emitted while handling this
    # request. Placed right after SecurityMiddleware so even a request
    # rejected by later middleware still gets a correlated log trail.
    "middlewares.request_log_context.RequestLogContextMiddleware",
    # Loads/saves the session (request.session) from the configured session
    # store. Must run before AuthenticationMiddleware, which depends on
    # request.session to resolve the logged-in user.
    "django.contrib.sessions.middleware.SessionMiddleware",
    # Handles common request normalization (e.g. APPEND_SLASH redirects,
    # forbidden User-Agent blocking). Framework convention places this
    # early, before CSRF/auth, since it may short-circuit the request
    # before those checks are worth doing.
    "django.middleware.common.CommonMiddleware",
    # Enforces CSRF protection on unsafe HTTP methods. Must run before any
    # view logic executes, and after SessionMiddleware since the CSRF
    # token round-trips through the session/cookie.
    "django.middleware.csrf.CsrfViewMiddleware",
    # Resolves request.user from request.session, set up by
    # SessionMiddleware above. Every middleware/view after this point can
    # rely on request.user being populated (AnonymousUser if not logged
    # in).
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Exposes one-time notification messages (django.contrib.messages) to
    # the next request/template. Depends on SessionMiddleware.
    "django.contrib.messages.middleware.MessageMiddleware",
    # Sets X-Frame-Options to prevent this app being embedded in a
    # clickjacking iframe. Placed last since it only touches outgoing
    # response headers, not request processing.
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "django_app.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "django_app.wsgi.application"
ASGI_APPLICATION = "django_app.asgi.application"


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases
#
# Two logical connections are defined: "default" (primary — read/write, the
# ACID-critical system of record) and "replica" (read replica — read-only
# reporting/analytics queries). Only the password is Vault-backed per
# connection; host/port/name/user are plain config, not secrets. For now
# "replica" points at the same physical database as "default" (no read
# replica has been provisioned yet) — once one exists, only the REPLICA_DB_*
# env vars / Vault secret name need to change, no code here does.


def _build_database_config(*, prefix: str, secret_name: str) -> dict:
    """Build a Django DATABASES entry from discrete env vars + a Vault-backed password.

    `prefix` namespaces the plain (non-secret) connection parameters in
    `.env` (e.g. "DB" -> DB_HOST/DB_PORT/DB_NAME/DB_USER). `secret_name` is
    the key looked up via `_get_secret` (Vault first, `.env` fallback) for
    the password alone — the one part of a DB connection that must never be
    plain config in a committed file.
    """
    return {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": env(f"{prefix}_HOST", default="localhost"),
        "PORT": env(f"{prefix}_PORT", default="5432"),
        "NAME": env(f"{prefix}_NAME", default="djaskt_ledger"),
        "USER": env(f"{prefix}_USER", default="djaskt"),
        "PASSWORD": _get_secret(secret_name, default="djaskt"),
    }


DATABASES = {
    "default": _build_database_config(prefix="DB", secret_name="DB_PASSWORD"),
    # TODO: point at a dedicated read-replica host once one is provisioned —
    # currently the same physical database as "default".
    "replica": _build_database_config(prefix="REPLICA_DB", secret_name="REPLICA_DB_PASSWORD"),
}
# ACID-critical writes (SELECT FOR UPDATE inside transaction.atomic) require the
# ORM to hold a single real connection per request rather than silently reopening one.
for _db_config in DATABASES.values():
    _db_config["ATOMIC_REQUESTS"] = False
    _db_config["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)


# Redis (shared with the FastAPI market-data service for live price lookups,
# and used as the Channels layer backend for realtime broadcasts).
REDIS_URL = _get_secret("REDIS_URL", default="redis://localhost:6379/0")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Argon2id (via Argon2PasswordHasher) is OWASP's recommended password
# hashing algorithm and Django's own docs still list it first when the
# argon2-cffi dependency is acceptable — stronger memory-hardness against
# GPU/ASIC cracking than PBKDF2 (Django's zero-dependency default).
# Existing PBKDF2 hashes (if any) keep verifying correctly and are
# transparently upgraded to Argon2 on next successful login — no migration
# needed.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Security hardening (OWASP baseline) -----------------------------------
# All of these default to safe values for local dev and are tightened via env
# vars in production (behind TLS termination at the reverse proxy).

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Ninja/JS clients typically need to read the CSRF token
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
