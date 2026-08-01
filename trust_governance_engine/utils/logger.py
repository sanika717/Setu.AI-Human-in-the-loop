import logging
import sys
from ..config import settings


def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), stream=sys.stdout)
    logger = logging.getLogger(name)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    return logger
