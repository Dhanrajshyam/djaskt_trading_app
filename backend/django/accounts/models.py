"""Custom user model: email is the login identifier, not username.

Django's stock `auth.User` treats `username` as the natural key and leaves
`email` optional/non-unique. This app inverts that: `email` is required,
unique, and the sole login credential (`USERNAME_FIELD`); `username` is
kept only because `AbstractUser`/Django admin internals expect the field to
exist, auto-derived from the email's local part at creation time, and
never used for authentication or shown to the user.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


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

    def __str__(self) -> str:
        """Human-readable label used in the Django admin and shell."""
        return self.email
