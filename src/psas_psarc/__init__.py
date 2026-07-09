import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

__all__ = ["setup_loggers"]
