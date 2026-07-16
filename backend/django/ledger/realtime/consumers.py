"""WebSocket consumer broadcasting portfolio state changes to their owner.

Trades are executed entirely through the REST contract layer; this consumer
is a read-only, push-only channel — clients never send trade instructions
over the socket. The one message a client ever sends is the first-message
auth payload (see `ledger.realtime.auth`); after that the channel is
push-only from the server's side.
"""

import asyncio
import json
import logging
import uuid
from typing import TYPE_CHECKING, Any

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from ledger.realtime.auth import (
    AUTH_MESSAGE_TIMEOUT_SECONDS,
    WebSocketAuthError,
    authenticate_first_message,
)

if TYPE_CHECKING:
    from accounts.models import User
    from ledger.models import Portfolio

logger = logging.getLogger(__name__)

TRADE_HISTORY_LIMIT = 50

GROUP_NAME_TEMPLATE = "portfolio_{portfolio_id}"


def portfolio_group_name(portfolio_id: uuid.UUID | str) -> str:
    """Return the Channels group name a portfolio's updates are broadcast to.

    Shared by both this consumer (to join the group on connect) and
    `LedgerOrchestratorService` (to broadcast into it), so the naming
    convention lives in exactly one place.
    """
    return GROUP_NAME_TEMPLATE.format(portfolio_id=portfolio_id)


class PortfolioConsumer(AsyncWebsocketConsumer):
    """Streams cash balance, position, and trade-history updates for a
    single portfolio.

    Authenticates via a "first message" handshake rather than the
    connection URL or headers (see `ledger.realtime.auth` module docstring
    for why): the raw WebSocket connection is accepted immediately, but the
    client must send one JSON message — `{"type": "auth", "access_token":
    "<jwt>"}` — before anything else happens. Only once that token is
    validated (same checks the REST API uses, including Redis
    revocation) and the resolved user is confirmed to own the requested
    portfolio does the connection actually start receiving data. A
    connection that never sends a valid auth message within
    `AUTH_MESSAGE_TIMEOUT_SECONDS` is closed.
    """

    async def connect(self) -> None:
        """Accept the raw connection and start the auth-message timeout.

        Deliberately does *no* authentication here — the connection is
        provisionally open but inert until `receive()` gets and validates
        the first (auth) message. This keeps the JWT out of the connection
        URL and headers entirely.
        """
        self.portfolio_id = self.scope["url_route"]["kwargs"]["portfolio_id"]
        self._authenticated = False
        self.group_name: str | None = None
        self.user_id: int | None = None

        await self.accept()

        # If the client never sends a valid auth message in time, close the
        # socket rather than leaving it open indefinitely — bounds how many
        # unauthenticated connections can accumulate.
        self._auth_timeout_task = asyncio.ensure_future(self._enforce_auth_timeout())

    async def _enforce_auth_timeout(self) -> None:
        """Close the connection if it isn't authenticated within the timeout."""
        await asyncio.sleep(AUTH_MESSAGE_TIMEOUT_SECONDS)
        if not self._authenticated:
            logger.warning(
                "WebSocket connection closed: no auth message received in time.",
                extra={"portfolio_id": self.portfolio_id},
            )
            await self.close(code=4401)

    async def receive(
        self, text_data: str | None = None, bytes_data: bytes | None = None
    ) -> None:
        """Handle the client's first (and only expected) inbound message.

        Everything after the first message is ignored — this is otherwise
        a push-only channel (see class docstring). The first message must
        be the auth payload; anything else, or an invalid/expired/revoked
        token, closes the connection.
        """
        if self._authenticated:
            return  # Push-only channel — ignore anything sent after auth.

        if text_data is None:
            await self.close(code=4401)
            return

        try:
            user = await sync_to_async(authenticate_first_message)(text_data)
        except WebSocketAuthError as exc:
            logger.warning(
                "WebSocket connection rejected: auth message invalid.",
                extra={"portfolio_id": self.portfolio_id, "reason": str(exc)},
            )
            await self.close(code=4401)
            return

        portfolio = await self._get_owned_portfolio(user, self.portfolio_id)
        if portfolio is None:
            logger.warning(
                "WebSocket connection rejected: portfolio not found or not owned.",
                extra={"portfolio_id": self.portfolio_id, "user_id": user.id},
            )
            await self.close(code=4403)
            return

        self._authenticated = True
        self._auth_timeout_task.cancel()
        self.group_name = portfolio_group_name(self.portfolio_id)
        self.user_id = user.id
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        logger.info(
            "WebSocket authenticated and connected.",
            extra={"portfolio_id": self.portfolio_id, "user_id": self.user_id},
        )

        # Newest-first trade history snapshot, sent once on successful auth
        # so the client has context before any live "portfolio.update"
        # broadcasts arrive. Trade.Meta.ordering is already "-timestamp".
        trades = await self._get_recent_trades(self.portfolio_id)
        await self.send(
            text_data=json.dumps({"type": "trade_history", "trades": trades})
        )

    async def disconnect(self, code: int) -> None:
        """Leave the portfolio's broadcast group, if it was ever joined."""
        auth_timeout_task = getattr(self, "_auth_timeout_task", None)
        if auth_timeout_task is not None:
            auth_timeout_task.cancel()

        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info(
                "WebSocket disconnected.",
                extra={
                    "portfolio_id": getattr(self, "portfolio_id", None),
                    "user_id": self.user_id,
                    "close_code": code,
                },
            )

    async def portfolio_update(self, event: dict[str, Any]) -> None:
        """Handler for `type: "portfolio.update"` group_send messages."""
        await self.send(text_data=json.dumps(event["payload"]))

    @staticmethod
    async def _get_owned_portfolio(user: User, portfolio_id: str) -> Portfolio | None:
        """Async wrapper around the shared `get_owned_portfolio_or_none` helper.

        Reuses the same authorization logic as the REST layer
        (`ledger.services.authorization`) so ownership checks can't drift
        between the two contract layers.
        """
        from ledger.services.authorization import get_owned_portfolio_or_none

        return await sync_to_async(get_owned_portfolio_or_none)(user, portfolio_id)

    @staticmethod
    async def _get_recent_trades(
        portfolio_id: str, limit: int = TRADE_HISTORY_LIMIT
    ) -> list[dict[str, str]]:
        """Fetch the portfolio's most recent trades, newest first, as plain dicts.

        Returns JSON-serializable dicts (not model instances) since the
        result is sent directly over the WebSocket.
        """
        from ledger.models import Trade

        def _fetch() -> list[dict[str, str]]:
            trades = Trade.objects.filter(portfolio_id=portfolio_id).order_by(
                "-timestamp"
            )[:limit]
            return [
                {
                    "trade_id": str(t.id),
                    "ticker": t.ticker,
                    "trade_type": t.trade_type,
                    "quantity": str(t.quantity),
                    "price": str(t.price),
                    "total_value": str(t.total_value),
                    "timestamp": t.timestamp.isoformat(),
                }
                for t in trades
            ]

        return await sync_to_async(_fetch)()
