"""Shared request-context state for structured logging.

Holds the single `ContextVar` that `middlewares.request_log_context`
(writer) and `extensions.logger` (reader) both depend on. Living here,
rather than inside either the middleware or the logger module, lets both
import it without either depending on the other.
"""

import contextvars
from typing import Any, TypedDict


class RequestLogMetadata(TypedDict):
    """Shape of the per-request metadata attached to log records.

    Mirrors the Elastic Common Schema (ECS) field groups it will be nested
    under when a log record is formatted: `trace`/`transaction` carry the
    correlation ID, `http`/`url` describe the originating request. Field
    values are `dict[str, Any]` rather than a fully-nested TypedDict since
    each block's shape varies (e.g. `http` nests a further `request` dict) —
    this type exists to fix the top-level keys, not police ECS internals.
    """

    trace: dict[str, Any]
    transaction: dict[str, Any]
    http: dict[str, Any]
    url: dict[str, Any]


request_metadata_var: contextvars.ContextVar[RequestLogMetadata | None] = (
    contextvars.ContextVar("request_metadata", default=None)
)
