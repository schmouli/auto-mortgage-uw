"""Logging configuration."""

import logging
import sys
from pathlib import Path

def setup_logger(name: str) -> logging.Logger:
    """Setup application logger."""
    logger = logging.getLogger(name)

    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    return logger

logger = setup_logger(__name__)
