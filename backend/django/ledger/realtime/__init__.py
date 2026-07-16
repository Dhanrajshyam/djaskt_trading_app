"""Realtime (WebSocket) layer for the ledger app, built on Django Channels.

Contains `PortfolioConsumer` (`consumers.py`), which streams trade history
and live portfolio state updates to their owning user, and the Channels
URL routing table (`routing.py`) that maps WebSocket URLs to it.
"""
