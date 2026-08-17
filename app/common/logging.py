from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


def configure_logging(service_name: str) -> logging.Logger:
    logger = logging.getLogger(service_name)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def log(logger: logging.Logger, message: str, **fields: Any) -> None:
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": "INFO",
        "message": message,
        **fields,
    }
    logger.info(json.dumps(payload, default=str, sort_keys=True))
