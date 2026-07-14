"""URL configuration for django_app (Djaskt Ledger & Orchestrator).

Also wires up the API's global exception handlers (see
`_register_exception_handlers`) so every error the controller layer doesn't
explicitly catch and map still comes back as the app's standard
`{"detail": ...}` JSON shape, never a bare traceback or Django's default
HTML error page.
"""

import logging

from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.urls import path
from ninja.errors import ValidationError
from ninja_extra import NinjaExtraAPI

from accounts.api import AuthController
from django_app.health import liveness, readiness
from ledger.api.router import LedgerController
from ledger.exceptions import LedgerServiceError

logger = logging.getLogger(__name__)

api = NinjaExtraAPI(title="Djaskt Ledger API", version="1.0.0")
api.register_controllers(AuthController, LedgerController)


def _register_exception_handlers(api: NinjaExtraAPI) -> None:
    """Register global exception handlers so every API error is consistently shaped.

    Individual controller actions still catch and map the domain exceptions
    they know how to recover from (see `ledger.api.router`); these handlers
    are the safety net for anything that reaches this point uncaught —
    a stray `LedgerServiceError`, a validation error, or a genuinely
    unexpected bug/infrastructure failure (e.g. Redis or the database being
    unreachable) — so clients always get `{"detail": ...}` JSON instead of a
    raw traceback (DEBUG) or Django's default HTML 500 page (production).
    """

    @api.exception_handler(ValidationError)
    def handle_validation_error(
        request: HttpRequest, exc: ValidationError
    ) -> HttpResponse:
        """Map Ninja's request-schema validation failures to the app's error shape."""
        return api.create_response(request, {"detail": exc.errors}, status=422)

    @api.exception_handler(LedgerServiceError)
    def handle_ledger_service_error(
        request: HttpRequest, exc: LedgerServiceError
    ) -> HttpResponse:
        """Catch-all for domain errors a controller action didn't map itself.

        409 is the same status the controllers use for business-rule
        violations; this only fires if a new LedgerServiceError subclass is
        raised somewhere that hasn't been given an explicit mapping yet.
        """
        logger.warning("Unhandled LedgerServiceError: %s", exc)
        return api.create_response(request, {"detail": str(exc)}, status=409)

    @api.exception_handler(Exception)
    def handle_unexpected_error(request: HttpRequest, exc: Exception) -> HttpResponse:
        """Last-resort handler for anything else (infra failures, bugs).

        Always logs the full exception server-side and always returns a
        generic 500 JSON body — never the exception message or a traceback,
        which could leak internal details (OWASP A09 / information
        exposure) regardless of DEBUG.
        """
        logger.exception("Unhandled exception in ledger API: %s", exc)
        return api.create_response(
            request, {"detail": "An unexpected error occurred."}, status=500
        )


_register_exception_handlers(api)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", liveness, name="liveness"),
    path("readyz", readiness, name="readiness"),
    path("api/v1/", api.urls),
]
