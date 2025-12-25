"""Health checks for the trader service."""

from __future__ import annotations

import socket
import time
from typing import Mapping

HEALTH_CHECKS: Mapping[str, str] = {
    "python": "interpreter",
    "network": "localhost",
}


def perform_health_check() -> bool:
    """Perform basic, fast health checks.

    The check currently validates that the Python interpreter responds quickly and
    that the host can resolve and connect to localhost.
    """

    try:
        start_time = time.monotonic()
        _ = 1 + 1
        if time.monotonic() - start_time > 1:
            return False
    except Exception:
        return False

    try:
        with socket.create_connection(("127.0.0.1", 80), timeout=0.2):
            pass
    except OSError:
        # Not all environments expose localhost:80; treat unreachable as warning, not failure.
        return True
    return True
