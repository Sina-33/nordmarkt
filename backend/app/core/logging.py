import logging
import sys
from contextvars import ContextVar

import structlog

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
actor_id_ctx: ContextVar[str | None] = ContextVar("actor_id", default=None)


def _inject_context(_: object, __: str, event_dict: dict) -> dict:
    if rid := request_id_ctx.get():
        event_dict["request_id"] = rid
    if aid := actor_id_ctx.get():
        event_dict["actor_id"] = aid
    return event_dict


def configure_logging(*, debug: bool = False) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _inject_context,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
