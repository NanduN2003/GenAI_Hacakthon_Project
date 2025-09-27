import logging
import sys
from typing import Final

# --- Constants ---
LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# --- Logger Setup ---

def get_logger(name: str) -> logging.Logger:
    """
    Initializes and configures a logger with a standardized format.

    This function sets up a logger that streams to standard output. It ensures
    that handlers are not added multiple times to the same logger instance.

    Args:
        name: The name for the logger, typically __name__.

    Returns:
        A configured logging.Logger instance.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(LOG_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger
    