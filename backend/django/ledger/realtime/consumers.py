"""WebSocket consumer broadcasting portfolio state changes to their owner.

Trades are executed entirely through the REST contract layer; this consumer
is a read-only, push-only channel — clients never send trade instructions
over the socket.
"""

import json
import logging
import uuid
from typing import TYPE_CHECKING, Any

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

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

    Connection is only accepted if the authenticated user owns the requested
    portfolio, preventing one user from subscribing to another's ledger state
    (OWASP broken object-level authorization).
    """

    async def connect(self) -> None:
        """Authenticate, authorize, and accept the WebSocket connection.

        Closes with code 4401 if the user isn't authenticated, or 4403 if
        they don't own the requested portfolio (OWASP broken object-level
        authorization). On success, joins the portfolio's broadcast group
        and immediately sends a newest-first trade history snapshot.
        """
        self.portfolio_id = self.scope["url_route"]["kwargs"]["portfolio_id"]
        user = self.scope.get("user")

        if user is None or not user.is_authenticated:
            logger.warning(
                "WebSocket connection rejected: unauthenticated.",
                extra={"portfolio_id": self.portfolio_id},
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

        self.group_name = portfolio_group_name(self.portfolio_id)
        self.user_id = user.id
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(
            "WebSocket connected.",
            extra={"portfolio_id": self.portfolio_id, "user_id": self.user_id},
        )

        # Newest-first trade history snapshot, sent once on connect so the
        # client has context before any live "portfolio.update" broadcasts
        # arrive. Trade.Meta.ordering is already "-timestamp".
        trades = await self._get_recent_trades(self.portfolio_id)
        await self.send(
            text_data=json.dumps({"type": "trade_history", "trades": trades})
        )

    async def disconnect(self, code: int) -> None:
        """Leave the portfolio's broadcast group, if it was ever joined."""
        group_name = getattr(self, "group_name", None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)
            logger.info(
                "WebSocket disconnected.",
                extra={
                    "portfolio_id": getattr(self, "portfolio_id", None),
                    "user_id": getattr(self, "user_id", None),
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
