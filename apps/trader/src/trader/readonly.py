"""Read-only connectivity checks for Hyperliquid."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Mapping, Sequence

from .config import AppConfig

LOGGER = logging.getLogger(__name__)


def _fetch_json(url: str, *, timeout: float) -> Mapping[str, Any] | None:
    request = urllib.request.Request(url=url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            data: Mapping[str, Any] = json.loads(response.read())
            return data
    except urllib.error.URLError as exc:  # pragma: no cover - network environments vary
        LOGGER.warning("Read-only probe failed", extra={"error": str(exc), "url": url})
        return None


def perform_readonly_check(
    config: AppConfig, *, symbols: Sequence[str] | None = None
) -> Mapping[str, Any]:
    """Probe Hyperliquid read-only endpoints.

    This check avoids any trading side effects and only issues simple GET requests.
    """

    targets = symbols or config.readonly_symbols or ("BTC", "ETH")
    base_url = config.hyperliquid.base_url.rstrip("/")
    info_url = f"{base_url}/info"
    market_url = f"{base_url}/market"

    info_payload = _fetch_json(info_url, timeout=config.request_timeout)
    market_payload = _fetch_json(market_url, timeout=config.request_timeout)

    return {
        "status": "ok" if info_payload or market_payload else "degraded",
        "wallet": config.hyperliquid.display_wallet,
        "environment": config.hyperliquid.environment,
        "symbols": list(targets),
        "urls": {"info": info_url, "market": market_url},
        "info_sample": info_payload if info_payload else {},
        "market_sample": market_payload if market_payload else {},
    }


def enforce_live_trading_enabled(config: AppConfig) -> None:
    """Guard function to prevent unintended live execution."""

    if (
        not config.hyperliquid.live_trading
        or (config.hyperliquid.risk_ack or "").strip() != "I_UNDERSTAND"
    ):
        raise RuntimeError(
            "Live trading is disabled. Set HL_LIVE_TRADING=true and HL_RISK_ACK=I_UNDERSTAND "
            "to enable, and ensure downstream execution adapters are implemented."
        )
