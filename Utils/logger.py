"""Structured logging — replaces server/utils/logger.js."""

import logging
import sys

logging.basicConfig(
    # level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}',
    stream=sys.stdout,
)

logger = logging.getLogger("society-backend")
