import sys

import structlog
from structlog.stdlib import BoundLogger

from yl_rag.settings import settings


def configure_logger():
    is_dev = settings.ENVIRONMENT == "dev" or sys.stdout.isatty()

    if is_dev:
        from structlog.dev import ConsoleRenderer

        renderer = ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(settings.log_level.value),
        cache_logger_on_first_use=True,
    )


configure_logger()
log: BoundLogger = structlog.get_logger()
