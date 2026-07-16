"""Django Ninja Extra contract layer for the brokerage app.

Thin by design, matching `ledger.api.router`'s convention: validate the
request shape (schemas.py already did that), enforce object-level
authorization, delegate to the orchestrator, and map domain exceptions to
HTTP status codes. No business logic lives here.
"""

from typing import cast
from uuid import UUID

from django.http import HttpRequest
from ninja_extra import api_controller, http_delete, http_get, http_post

from accounts.models import User
from brokerage.api.schemas import (
    BrokerLoginRequestSchema,
    BrokerLoginResponseSchema,
    BrokerLogoutRequestSchema,
    BrokerLogoutResponseSchema,
    ErrorSchema,
    UserBrokerageLinkCreateSchema,
    UserBrokerageLinkResponseSchema,
)
from brokerage.exceptions import (
    BrokerAPIError,
    BrokerRateLimitedError,
    InvalidBrokerCredentialsError,
    NoBrokerageLinkError,
    UnknownBrokerError,
)
from brokerage.models import Brokerage, UserBrokerageLink
from brokerage.services.orchestrator import BrokerAuthOrchestrator
from ledger.api.auth import DenylistCheckingJWTAuth


@api_controller("/brokerage", tags=["brokerage"], auth=DenylistCheckingJWTAuth())
class BrokerageController:
    """User-facing brokerage endpoints: manage links and log in to a broker.

    `Brokerage`/`BrokerageEndpoint` (which brokers exist, how to call their
    APIs) are operator-configured platform data managed via Django admin
    (`brokerage/admin.py`), not exposed here.
    """

    def __init__(self) -> None:
        """Initialize the controller with its own orchestrator instance."""
        self._orchestrator = BrokerAuthOrchestrator()

    @http_post(
        "/links/",
        response={
            201: UserBrokerageLinkResponseSchema,
            404: ErrorSchema,
            409: ErrorSchema,
        },
    )
    def create_link(
        self, request: HttpRequest, payload: UserBrokerageLinkCreateSchema
    ) -> tuple[int, UserBrokerageLinkResponseSchema | ErrorSchema]:
        """Link the authenticated user to a brokerage, storing their identifiers.

        Returns 404 if no active `Brokerage` row exists for the given name,
        or 409 if the user has already linked this brokerage (the
        `UserBrokerageLink` unique-together constraint).
        """
        user = cast(User, request.user)
        try:
            brokerage = Brokerage.objects.get(
                name=payload.brokerage_name, is_active=True
            )
        except Brokerage.DoesNotExist:
            return 404, ErrorSchema(detail="Unknown or inactive brokerage.")

        already_linked = (
            UserBrokerageLink.objects.for_user(user)
            .filter(brokerage=brokerage)
            .exists()
        )
        if already_linked:
            return 409, ErrorSchema(detail="This brokerage is already linked.")

        link = UserBrokerageLink.objects.create(
            user=user,
            brokerage=brokerage,
            user_brokerage_data=payload.user_brokerage_data,
        )
        return 201, UserBrokerageLinkResponseSchema(
            id=link.id,
            brokerage_name=brokerage.name,
            user_brokerage_data=link.user_brokerage_data,
        )

    @http_get("/links/", response={200: list[UserBrokerageLinkResponseSchema]})
    def list_links(self, request: HttpRequest) -> list[UserBrokerageLinkResponseSchema]:
        """Return the authenticated user's own brokerage links."""
        user = cast(User, request.user)
        links = UserBrokerageLink.objects.for_user(user).select_related("brokerage")
        return [
            UserBrokerageLinkResponseSchema(
                id=link.id,
                brokerage_name=link.brokerage.name,
                user_brokerage_data=link.user_brokerage_data,
            )
            for link in links
        ]

    @http_delete("/links/{link_id}/", response={204: None, 404: ErrorSchema})
    def delete_link(
        self, request: HttpRequest, link_id: UUID
    ) -> tuple[int, None | ErrorSchema]:
        """Unlink the authenticated user's own brokerage link.

        Scoped via `for_user()` so a client can't unlink another user's
        link by guessing its ID (OWASP A01).
        """
        user = cast(User, request.user)
        deleted_count, _ = (
            UserBrokerageLink.objects.for_user(user).filter(id=link_id).delete()
        )
        if deleted_count == 0:
            return 404, ErrorSchema(detail="Brokerage link not found.")
        return 204, None

    @http_post(
        "/login/",
        response={
            200: BrokerLoginResponseSchema,
            404: ErrorSchema,
            409: ErrorSchema,
            429: ErrorSchema,
            502: ErrorSchema,
        },
    )
    def broker_login(
        self, request: HttpRequest, payload: BrokerLoginRequestSchema
    ) -> tuple[int, BrokerLoginResponseSchema | ErrorSchema]:
        """Authenticate the caller against a linked brokerage and cache the session.

        Returns 404 if the brokerage is unknown/inactive or the caller
        hasn't linked it yet, 409 for structurally invalid credentials, 429
        if called again within the broker's login cooldown, or 502 if the
        broker's own API call fails — never the broker's raw error detail
        (OWASP A09), only a generic message.
        """
        user = cast(User, request.user)
        try:
            session, ttl_seconds = self._orchestrator.authenticate_and_cache(
                user=user,
                brokerage_name=payload.brokerage_name,
                login_secrets=payload.user_credentials,
            )
        except UnknownBrokerError as exc:
            return 404, ErrorSchema(detail=str(exc))
        except NoBrokerageLinkError as exc:
            return 404, ErrorSchema(detail=str(exc))
        except InvalidBrokerCredentialsError as exc:
            return 409, ErrorSchema(detail=str(exc))
        except BrokerRateLimitedError as exc:
            return 429, ErrorSchema(detail=str(exc))
        except BrokerAPIError:
            return 502, ErrorSchema(detail="Broker authentication failed.")

        return 200, BrokerLoginResponseSchema(
            brokerage_name=payload.brokerage_name,
            client_id=session.client_id,
            expires_in_seconds=ttl_seconds,
        )

    @http_post(
        "/logout/",
        response={200: BrokerLogoutResponseSchema, 404: ErrorSchema},
    )
    def broker_logout(
        self, request: HttpRequest, payload: BrokerLogoutRequestSchema
    ) -> tuple[int, BrokerLogoutResponseSchema | ErrorSchema]:
        """Log the caller out of a brokerage and clear their cached session.

        Returns 404 if the brokerage is unknown/inactive or the caller
        hasn't linked it yet. A broker-side logout failure is never
        surfaced as an error here — the local session is cleared
        regardless (see `BrokerAuthOrchestrator.logout_and_clear`), so this
        always returns 200 once a link exists, whether or not a session
        was actually cached to clear.
        """
        user = cast(User, request.user)
        try:
            disconnected = self._orchestrator.logout_and_clear(
                user=user, brokerage_name=payload.brokerage_name
            )
        except UnknownBrokerError as exc:
            return 404, ErrorSchema(detail=str(exc))
        except NoBrokerageLinkError as exc:
            return 404, ErrorSchema(detail=str(exc))

        message = "Logged out." if disconnected else "Already logged out."
        return 200, BrokerLogoutResponseSchema(
            brokerage_name=payload.brokerage_name,
            disconnected=disconnected,
            message=message,
        )
