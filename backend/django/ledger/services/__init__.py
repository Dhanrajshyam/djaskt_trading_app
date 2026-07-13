"""Service layer for the ledger app.

Framework-agnostic business logic, decoupled from the API/routing and
realtime layers per the project's clean-architecture standard. Contains:

- `price_service.PriceCacheService` — live price lookups from Redis.
- `trade_service.TradeExecutionService` — ACID-critical trade execution.
- `cash_service.CashTransferService` — ACID-critical cash deposit/withdrawal.
- `main_service.LedgerOrchestratorService` — single entry point the API and
  realtime layers call; coordinates the above and triggers WebSocket
  broadcasts after a successful commit.
- `authorization.get_owned_portfolio_or_none` — shared per-user data
  isolation helper used by both the REST and WebSocket layers.
"""
