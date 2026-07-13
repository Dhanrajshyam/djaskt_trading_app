"""Django middleware for the Djaskt ledger service.

Currently contains `request_log_context.RequestLogContextMiddleware`, which
attaches a per-request trace/correlation ID to the structured logging
context defined in `extensions.log_context`.
"""
