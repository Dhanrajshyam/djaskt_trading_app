"""Attaches a per-request trace/correlation ID to the structured logging context.

Pairs with `extensions.logger`: every log line emitted while a request is
in flight automatically picks up this middleware's trace/transaction/http/
url metadata via `extensions.log_context.request_metadata_var`, without
call sites having to pass it explicitly.
"""

import uuid
from inspect import iscoroutinefunction

from asgiref.sync import markcoroutinefunction
from django.http import HttpRequest, HttpResponse

from extensions.log_context import request_metadata_var


class RequestLogContextMiddleware:
    """Middleware that sets request-scoped logging context, sync or async.

    Declares both `sync_capable` and `async_capable`. Which mode actually
    runs is detected once, at construction, from whether `get_response`
    (the next handler in the chain) is itself a coroutine function — the
    same self-adapting pattern Django's own `MiddlewareMixin` uses. This
    matters because a middleware that is *only* `async_capable` breaks the
    chain when placed between synchronous built-ins under a WSGI server
    (confirmed by testing under `runserver`'s WSGI dev server: forcing just
    this one middleware into async mode inside an otherwise-sync chain
    produced a coroutine Django's WSGI handler never awaited, crashing every
    request with a 500). Supporting both modes natively — not forcing async
    everywhere — is what actually keeps this middleware from adding latency
    regardless of how the app is served (WSGI dev server today, ASGI/
    Channels in production).
    """

    sync_capable = True
    async_capable = True

    def __init__(self, get_response) -> None:
        """Store the next handler and detect which mode to run in."""
        self.get_response = get_response
        self.async_mode = iscoroutinefunction(get_response)
        if self.async_mode:
            markcoroutinefunction(self)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Dispatch to the sync or async implementation, per detected mode."""
        if self.async_mode:
            return self._acall(request)
        return self._call_sync(request)

    def _call_sync(self, request: HttpRequest) -> HttpResponse:
        """Synchronous request path — used when the chain below is sync."""
        token = self._start(request)
        try:
            response = self.get_response(request)
        finally:
            request_metadata_var.reset(token)
        return self._finish(request, response)

    async def _acall(self, request: HttpRequest) -> HttpResponse:
        """Asynchronous request path — used when the chain below is async."""
        token = self._start(request)
        try:
            response = await self.get_response(request)
        finally:
            request_metadata_var.reset(token)
        return self._finish(request, response)

    @staticmethod
    def _start(request: HttpRequest):
        """Resolve/generate the trace ID and set it as the active log context.

        Resolves a trace/correlation ID from the `X-Request-ID` or
        `X-Correlation-ID` request header if the caller supplied one
        (enabling cross-service correlation in ELK), generating a fresh
        UUID otherwise. Returns the `ContextVar` reset token the caller must
        pass back to `request_metadata_var.reset(...)` once the response has
        been produced — including on an unhandled exception — so this
        request's context can never leak into a later request reusing the
        same thread/task.
        """
        trace_id = (
            request.headers.get("X-Request-ID")
            or request.headers.get("X-Correlation-ID")
            or str(uuid.uuid4())
        )
        metadata = {
            "trace": {"id": trace_id},
            "transaction": {"id": trace_id},
            "http": {"request": {"method": request.method, "id": trace_id}},
            "url": {"path": request.path},
        }
        request.trace_id = trace_id
        return request_metadata_var.set(metadata)

    @staticmethod
    def _finish(request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Stamp the resolved trace ID onto the outgoing response headers."""
        response["X-Request-ID"] = request.trace_id
        return response
