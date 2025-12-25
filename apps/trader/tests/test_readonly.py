from typing import Any
from unittest import mock

import pytest

from trader.config import load_config
from trader.readonly import enforce_live_trading_enabled, perform_readonly_check


def test_enforce_live_trading_disabled_by_default():
    config = load_config({})
    with pytest.raises(RuntimeError):
        enforce_live_trading_enabled(config)


def test_enforce_live_trading_enabled_with_ack():
    config = load_config(
        {
            "HL_LIVE_TRADING": "true",
            "HL_RISK_ACK": "I_UNDERSTAND",
        }
    )
    # Should not raise
    enforce_live_trading_enabled(config)


def test_perform_readonly_check_uses_network_payload(monkeypatch):
    config = load_config({"HL_HYPERLIQUID_BASE_URL": "https://example.com"})

    def fake_fetch(url: str, *, timeout: float) -> dict[str, Any]:
        return {"url": url, "timeout": timeout}

    with mock.patch("trader.readonly._fetch_json", side_effect=fake_fetch):
        payload = perform_readonly_check(config, symbols=["BTC"])

    assert payload["status"] == "ok"
    assert payload["symbols"] == ["BTC"]
    assert "market_sample" in payload
