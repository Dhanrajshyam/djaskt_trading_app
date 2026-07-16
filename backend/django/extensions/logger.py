"""Structured, ELK-compatible logging setup for the ledger service.

Emits every log record as an Elastic Common Schema (ECS)-shaped JSON line —
`service.*`, `host.*`, `log.*`, `error.*`, plus `trace`/`transaction`/`http`/
`url` blocks populated per-request by `middlewares.request_log_context` —
so log output can be ingested directly by an ELK stack without a separate
field-remapping step.

The actual write to stdout happens on a single background thread via
`logging.handlers.QueueHandler`/`QueueListener`, so a slow write (or a
burst of log calls) never blocks the request-handling coroutine or thread
— this is the "async logging" the app's latency goal calls for; the
`logger.info(...)`/`logger.warning(...)` call sites themselves stay
ordinary synchronous calls, which is what makes them usable from both sync
and async code without extra ceremony.

Call `configure_logging(...)` exactly once, at Django settings-load time.
After that, any module's plain `logger = logging.getLogger(__name__)` call
automatically inherits ECS JSON formatting and request context via
propagation to the root logger — no per-module setup needed.
"""

import atexit
import logging
import logging.config
import queue
import socket
import sys
from logging.handlers import QueueHandler, QueueListener
from typing import Any

from pythonjsonlogger.json import JsonFormatter

from extensions.log_context import request_metadata_var

_listener: QueueListener | None = None


class ECSDeepJsonFormatter(JsonFormatter):
    """Reshapes a flat log record into Elastic Common Schema (ECS) JSON.

    Built on `pythonjsonlogger.json.JsonFormatter` (the current, non-deprecated
    import path — `pythonjsonlogger.jsonlogger` is a compatibility shim as of
    python-json-logger 4.x and emits a DeprecationWarning).
    """

    def __init__(
        self,
        *args: Any,
        service_name: str = "djaskt-ledger",
        service_version: str = "1.0.0",
        environment: str = "development",
        **kwargs: Any,
    ) -> None:
        """Initialize the formatter, capturing static service/host metadata.

        `service_name`/`service_version`/`environment` are attached to
        every log record under ECS's `service.*` fields; `host.name` is
        resolved once at startup rather than per record.
        """
        super().__init__(*args, **kwargs)
        self.service_info = {
            "name": service_name,
            "version": service_version,
            "environment": environment,
        }
        self.host_name = socket.gethostname()

    def process_log_record(self, log_record: dict[str, Any]) -> dict[str, Any]:
        """Reshape the flat field dict `add_fields()` built into ECS nesting.

        By this point `log_record` already contains any extra attributes
        the `ECSContextFilter` attached to the `LogRecord` (`trace`,
        `transaction`, `http`, `url`) as flat top-level keys — this method
        moves them into their ECS-correct positions, builds the `log.*`/
        `service.*`/`host.*`/`error.*` blocks, and collects anything left
        over under `extra.*` so no caller-supplied `extra=` data is lost.
        """
        ecs_record = {
            "@timestamp": log_record.get("asctime", ""),
            "message": log_record.get("message", ""),
            "log": {
                "level": log_record.get("levelname", "INFO").lower(),
                "logger": log_record.get("name", ""),
                "origin": {
                    "file": {
                        "name": log_record.get("filename", ""),
                        "line": log_record.get("lineno", 0),
                    },
                    "function": log_record.get("funcName", ""),
                },
            },
            "service": self.service_info,
            "host": {"name": self.host_name},
            "thread": {"name": log_record.get("threadName", "")},
        }

        if log_record.get("exc_info"):
            trace_string = log_record["exc_info"]
            error_type = (
                trace_string.splitlines()[-1].split(":")[0]
                if trace_string
                else "Exception"
            )
            ecs_record["error"] = {
                "type": error_type,
                "message": str(log_record.get("message")),
                "stack_trace": trace_string,
            }

        for ecs_block in ("trace", "transaction", "http", "url", "error"):
            if ecs_block in log_record:
                ecs_record[ecs_block] = log_record.pop(ecs_block)

        standard_keys = {
            "asctime",
            "message",
            "levelname",
            "name",
            "filename",
            "lineno",
            "funcName",
            "threadName",
            "exc_info",
            "taskName",
        }
        custom_extra = {k: v for k, v in log_record.items() if k not in standard_keys}
        if custom_extra:
            ecs_record["extra"] = custom_extra

        return ecs_record


class ECSContextFilter(logging.Filter):
    """Attaches the current request's trace/transaction/http/url context to each record.

    Reads `extensions.log_context.request_metadata_var`, populated by
    `RequestLogContextMiddleware` for the duration of a request. Outside a
    request (startup logs, background tasks with no request context), the
    ContextVar is unset and this filter is a no-op — log records simply
    won't carry those fields.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Attach request metadata to `record`, if set for the current context."""
        metadata = request_metadata_var.get()
        if metadata:
            record.trace = metadata.get("trace")
            record.transaction = metadata.get("transaction")
            record.http = metadata.get("http")
            record.url = metadata.get("url")
        return True


def configure_logging(
    *,
    service_name: str = "djaskt-ledger",
    service_version: str = "1.0.0",
    environment: str = "development",
    level: int = logging.INFO,
) -> None:
    """Install ECS JSON formatting and non-blocking log I/O on the root logger.

    Idempotent-safe to call more than once (e.g. under Django's autoreloader,
    which re-executes settings.py in the child process) — a second call
    tears down and replaces the previous queue/listener rather than layering
    another one on top, so no duplicate log lines or leaked threads result.

    After this call, every module's plain `logging.getLogger(__name__)`
    automatically inherits ECS JSON output and request-context enrichment
    via propagation to the root logger — application code never needs to
    call this function or a custom logger factory itself.
    """
    global _listener

    if _listener is not None:
        _listener.stop()
        _listener = None

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.filters.clear()

    log_format = (
        "%(asctime)s %(levelname)s %(name)s %(filename)s %(lineno)d "
        "%(funcName)s %(threadName)s %(message)s"
    )
    ecs_formatter = ECSDeepJsonFormatter(
        log_format,
        service_name=service_name,
        service_version=service_version,
        environment=environment,
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ecs_formatter)

    log_queue: queue.Queue[logging.LogRecord] = queue.Queue(-1)
    queue_handler = QueueHandler(log_queue)
    # The context filter must live on the *handler*, not the logger: a
    # logging.Logger only runs its own .filters for records logged directly
    # on it, not for records reaching it via propagation from a child
    # logger (which is how almost every call site — logging.getLogger(
    # __name__) in application modules — actually logs). A Handler's
    # filters, by contrast, run for every record that reaches that handler
    # regardless of which logger it originated from, which is what we need
    # here so request context gets attached uniformly application-wide.
    queue_handler.addFilter(ECSContextFilter())
    root_logger.addHandler(queue_handler)

    _listener = QueueListener(log_queue, console_handler, respect_handler_level=True)
    _listener.start()
    atexit.register(_listener.stop)
