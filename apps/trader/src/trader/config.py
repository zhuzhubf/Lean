"""Configuration loader for the trader bootstrap."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from trader.config.loader import build_constraints, load_profiles
from trader.schemas import PortfolioConstraints


@dataclass(frozen=True)
class LLMSettings:
    """Provider and model configuration for the decision engine."""

    provider: str
    openai_api_key: str | None
    openai_base_url: str | None
    openai_model: str
    openai_timeout: float
    openai_max_retries: int
    xai_api_key: str | None
    xai_base_url: str | None
    xai_model: str
    xai_timeout: float
    xai_max_retries: int


@dataclass(frozen=True)
class HyperliquidSettings:
    """Hyperliquid-specific connectivity settings."""

    base_url: str
    wallet_address: str | None
    environment: str
    live_trading: bool
    risk_ack: str | None

    @property
    def display_wallet(self) -> str:
        """Return a redacted wallet for logging."""

        if not self.wallet_address:
            return "(not set)"
        return f"{self.wallet_address[:6]}...{self.wallet_address[-4:]}"


@dataclass(frozen=True)
class AppConfig:
    """Top-level configuration for the trader service."""

    hyperliquid: HyperliquidSettings
    llm: LLMSettings
    canary: "CanarySettings"
    readonly_symbols: tuple[str, ...]
    request_timeout: float
    constraints: PortfolioConstraints
    risk_profile: str
    universe_profile: str
    provider: str
    db_path: Path
    run_interval_seconds: int
    run_iterations: int


@dataclass(frozen=True)
class CanarySettings:
    profile: str
    allowed_symbols: tuple[str, ...]
    max_daily_orders: int
    per_order_notional_cap_pct: float
    total_notional_cap_pct: float


def _get_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_symbols(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return tuple()
    candidates: Iterable[str] = (symbol.strip().upper() for symbol in raw.split(","))
    return tuple(symbol for symbol in candidates if symbol)


def load_config(env: Mapping[str, str] | None = None) -> AppConfig:
    """Load configuration from environment variables.

    Parameters
    ----------
    env: Mapping[str, str] | None
        Optional mapping to read values from; defaults to ``os.environ``.
    """

    source = env or os.environ
    base_url = source.get("HL_HYPERLIQUID_BASE_URL", "https://api.hyperliquid.xyz")
    wallet = source.get("HL_HYPERLIQUID_WALLET") or source.get("HL_WALLET_ADDRESS")
    environment = source.get("HL_ENVIRONMENT", "development")
    live_trading = _get_bool(source.get("HL_LIVE_TRADING"), default=False)
    risk_ack = source.get("HL_RISK_ACK")
    readonly_symbols = _get_symbols(source.get("HL_READONLY_SYMBOLS"))
    timeout = float(source.get("HL_REQUEST_TIMEOUT", "10"))
    risk_profile, universe_profile, canary_profile = load_profiles(source)
    constraints = build_constraints(risk_profile, universe_profile, source)
    provider = source.get("HL_DECISION_PROVIDER", source.get("LLM_PROVIDER", "openai"))
    llm_settings = LLMSettings(
        provider=provider,
        openai_api_key=source.get("OPENAI_API_KEY"),
        openai_base_url=source.get("OPENAI_BASE_URL"),
        openai_model=source.get("OPENAI_MODEL", "gpt-5.2"),
        openai_timeout=float(source.get("OPENAI_TIMEOUT_SEC", "30")),
        openai_max_retries=int(source.get("OPENAI_MAX_RETRIES", "2")),
        xai_api_key=source.get("XAI_API_KEY"),
        xai_base_url=source.get("XAI_BASE_URL"),
        xai_model=source.get("XAI_MODEL", "grok-1"),
        xai_timeout=float(source.get("XAI_TIMEOUT_SEC", "20")),
        xai_max_retries=int(source.get("XAI_MAX_RETRIES", "1")),
    )
    db_path = Path(source.get("HL_DB_PATH", "./trader.db"))
    run_interval = int(source.get("HL_RUN_INTERVAL", str(constraints.decision_interval_seconds)))
    iterations = int(source.get("HL_RUN_ITERATIONS", "1"))

    canary = CanarySettings(
        profile=f"{canary_profile.profile_name}_v{canary_profile.version}",
        allowed_symbols=tuple(symbol.upper() for symbol in canary_profile.allowed_symbols),
        max_daily_orders=canary_profile.max_daily_orders,
        per_order_notional_cap_pct=canary_profile.per_order_notional_cap_pct,
        total_notional_cap_pct=canary_profile.total_notional_cap_pct,
    )

    return AppConfig(
        hyperliquid=HyperliquidSettings(
            base_url=base_url,
            wallet_address=wallet,
            environment=environment,
            live_trading=live_trading,
            risk_ack=risk_ack,
        ),
        llm=llm_settings,
        canary=canary,
        readonly_symbols=readonly_symbols,
        request_timeout=timeout,
        constraints=constraints,
        risk_profile=f"{risk_profile.profile_name}_v{risk_profile.version}",
        universe_profile=f"universe_v{universe_profile.version}",
        provider=provider,
        db_path=db_path,
        run_interval_seconds=run_interval,
        run_iterations=iterations,
    )
