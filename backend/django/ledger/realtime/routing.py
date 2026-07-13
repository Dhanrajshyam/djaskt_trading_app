"""Channels URL routing table for the ledger app's WebSocket consumers.

Wired into the ASGI application in `django_app/asgi.py` under the
`websocket` protocol type.
"""

from django.urls import re_path

from ledger.realtime.consumers import PortfolioConsumer

websocket_urlpatterns = [
    re_path(
        r"^ws/v1/ledger/portfolio/(?P<portfolio_id>[0-9a-fA-F-]{36})/$",
        PortfolioConsumer.as_asgi(),
    ),
]
