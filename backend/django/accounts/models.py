"""Custom user model: email is the login identifier, not username.

Django's stock `auth.User` treats `username` as the natural key and leaves
`email` optional/non-unique. This app inverts that: `email` is required,
unique, and the sole login credential (`USERNAME_FIELD`); `username` is
kept only because `AbstractUser`/Django admin internals expect the field to
exist, auto-derived from the email's local part at creation time, and
never used for authentication or shown to the user.
"""

from typing import Any

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserManager(BaseUserManager["User"]):
    """Manager for `User`, keyed on `email` rather than `username`.

    `AbstractUser`'s inherited manager (`django.contrib.auth.models
    .UserManager`) hardcodes `username` as `create_user`/`create_superuser`'s
    first positional argument regardless of `USERNAME_FIELD` — a
    well-known gotcha with custom user models. Without this override,
    `manage.py createsuperuser` fails with `TypeError:
    UserManager.create_superuser() missing 1 required positional argument:
    'username'`, since its prompt flow is driven by `USERNAME_FIELD`/
    `REQUIRED_FIELDS` and never learns to supply one.
    """

    use_in_migrations = True

    def _create_user(
        self, email: str, password: str | None, **extra_fields: Any
    ) -> User:
        """Create and save a user with the given email and password.

        `username` is auto-derived from the email's local part here too
        (matching `accounts.api.AuthController.signup`'s behavior), so
        every creation path — signup endpoint, `createsuperuser`, the
        Django admin's "add user" form — populates it consistently.
        """
        if not email:
            raise ValueError("The given email must be set")
        email = self.normalize_email(email)
        extra_fields.setdefault("username", email.split("@")[0])
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        """Create a regular (non-staff, non-superuser) user."""
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        """Create a superuser — used by `manage.py createsuperuser`."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Djaskt platform user, authenticated by email + password.

    `REQUIRED_FIELDS` is empty (beyond the implicit password) so
    `createsuperuser` only prompts for email — `first_name`/`last_name`
    are optional profile fields, not required for account creation.
    """

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    email = models.EmailField(unique=True)
    # Inherited from AbstractUser; kept for framework compatibility only —
    # auto-derived from the email local-part at signup, never used to log
    # in and never surfaced to the user. Not unique: collisions between
    # two emails with the same local part (e.g. a@x.com vs a@y.com) are
    # expected and harmless since this field carries no identity meaning.
    username = models.CharField(max_length=150, blank=True)

    # django-stubs types AbstractUser.objects as UserManager[User] (Django's
    # own manager); this project's custom UserManager is a deliberate
    # replacement with a different, email-first _create_user signature, so
    # the override is intentional, not a type error.
    objects: UserManager = UserManager()  # type: ignore[assignment,misc]

    def __str__(self) -> str:
        """Human-readable label used in the Django admin and shell."""
        return self.email
