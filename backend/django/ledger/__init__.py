"""Ledger app: the ACID-critical core of the Djaskt trading platform.

Owns the ``Portfolio``, ``Position``, ``Trade``, and ``CashTransaction``
models (see ``ledger.models``), the trade/cash execution services
(``ledger.services``), the Django Ninja Extra REST contract layer
(``ledger.api``), and the WebSocket realtime layer (``ledger.realtime``)
that broadcasts portfolio state changes to their owning user.
"""
