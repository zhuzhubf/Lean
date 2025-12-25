from trader.config import HyperliquidSettings, load_config


def test_load_config_defaults():
    config = load_config({})
    assert isinstance(config.hyperliquid, HyperliquidSettings)
    assert config.hyperliquid.base_url.startswith("https://")
    assert config.hyperliquid.environment == "development"
    assert config.readonly_symbols == tuple()
    assert config.constraints.whitelist[:2] == ["BTC", "ETH"]
    assert config.provider == "openai"
    assert config.llm.openai_model == "gpt-5.2"
    assert config.risk_profile == "moderate_v1"


def test_load_config_custom_env():
    config = load_config(
        {
            "HL_HYPERLIQUID_BASE_URL": "https://example.com/api",
            "HL_WALLET_ADDRESS": "0xabcdef123456",
            "HL_ENVIRONMENT": "staging",
            "HL_LIVE_TRADING": "true",
            "HL_RISK_ACK": "I_UNDERSTAND",
            "HL_READONLY_SYMBOLS": "BTC,eth , sol",
            "HL_REQUEST_TIMEOUT": "5.5",
            "RISK_PROFILE": "moderate_v1",
            "UNIVERSE_PROFILE": "universe_v1",
            "HL_DECISION_PROVIDER": "xai",
            "HL_DB_PATH": "/tmp/trader.db",
            "OPENAI_API_KEY": "dummy",
            "OPENAI_MODEL": "gpt-4.1",
            "XAI_API_KEY": "dummy-xai",
        }
    )

    assert config.hyperliquid.base_url == "https://example.com/api"
    assert config.hyperliquid.display_wallet.startswith("0xab")
    assert config.hyperliquid.live_trading is True
    assert config.hyperliquid.risk_ack == "I_UNDERSTAND"
    assert config.readonly_symbols == ("BTC", "ETH", "SOL")
    assert isinstance(config.request_timeout, float)
    assert config.constraints.mode.value == "moderate"
    assert "SOL" in config.constraints.whitelist
    assert config.provider == "xai"
    assert str(config.db_path) == "/tmp/trader.db"
    assert config.llm.openai_model == "gpt-4.1"
    assert config.llm.xai_api_key == "dummy-xai"
    assert config.risk_profile.startswith("moderate_v1")
