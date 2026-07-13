"""ASGI config for django_app project.

Routes HTTP through Django's standard ASGI application and WebSocket
connections through Channels, guarded by session-based auth so consumers can
identify `scope["user"]`.
"""

import os

import django
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_app.settings")
django.setup()

django_asgi_app = get_asgi_application()

from ledger.realtime.routing import websocket_urlpatterns  # noqa: E402  (must follow django.setup())

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
