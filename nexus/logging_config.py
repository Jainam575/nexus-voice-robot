"""Nexus Robot — Structured logging configuration (Bug #25)."""
import logging
import sys


def setup_logging(level=logging.INFO):
    """Configure structured logging with levels for all subsystems."""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        stream=sys.stdout,
        force=True,
    )
    # Reduce noise from libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    return logging.getLogger("Nexus")


logger = setup_logging()
