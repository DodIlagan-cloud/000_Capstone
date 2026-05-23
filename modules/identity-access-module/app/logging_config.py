"""M1 - User Access Management Start
Configures logging for the standalone Identity Access API.
M1 End"""

import logging


LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Configure application logging from settings."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=LOG_FORMAT,
    )
