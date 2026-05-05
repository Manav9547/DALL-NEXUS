"""NexusID — Structured Logging with trace_id.

Every log line carries a trace_id for request correlation.
JSON-formatted for production log aggregation.
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable for trace_id
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="no-trace")


def get_trace_id() -> str:
    return trace_id_var.get()


def add_trace_id(logger: logging.Logger, method_name: str, event_dict: dict) -> dict:
    event_dict["trace_id"] = get_trace_id()
    return event_dict


def setup_logging(log_level: str = "INFO"):
    """Configure structlog for JSON output."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            add_trace_id,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


class TraceIDMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns a trace_id to every request.

    The trace_id is:
    1. Read from X-Trace-ID header if provided
    2. Otherwise generated as a UUID4
    3. Set in context var for all downstream logging
    4. Returned in the response X-Trace-ID header
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        tid = request.headers.get("x-trace-id", str(uuid.uuid4())[:12])
        trace_id_var.set(tid)

        log = structlog.get_logger()
        log.info("request_started",
                 method=request.method,
                 path=str(request.url.path),
                 query=str(request.url.query) if request.url.query else None)

        try:
            response = await call_next(request)
            response.headers["X-Trace-ID"] = tid

            log.info("request_completed",
                     method=request.method,
                     path=str(request.url.path),
                     status=response.status_code)

            return response
        except Exception as exc:
            log.error("request_failed",
                      method=request.method,
                      path=str(request.url.path),
                      error=str(exc))
            raise


def get_logger(name: str = "nexusid") -> structlog.BoundLogger:
    """Get a structured logger with the current trace_id."""
    return structlog.get_logger(name)
