"""Load versioned risk/universe configs and build constraints."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from trader.config.canary import CanaryProfile, canary_profile_path, load_canary_profile
from trader.config.risk_profile import RiskProfileConfig, load_risk_profile
from trader.config.universe import UniverseConfig, load_universe
from trader.schemas import PortfolioConstraints, PortfolioMode

CONFIG_ROOT = Path(__file__).resolve().parent.parent.parent / "config"
DEFAULT_RISK_PROFILE = "moderate_v1"
DEFAULT_UNIVERSE_PROFILE = "universe_v2"
DEFAULT_CANARY_PROFILE = "canary_v1"


class ConfigLoaderError(RuntimeError):
    """Raised when configuration fails to load or validate."""


def _profile_path(name: str, subdir: str) -> Path:
    return CONFIG_ROOT / subdir / f"{name}.yaml"


def load_profiles(
    env: Mapping[str, str] | None = None,
) -> tuple[RiskProfileConfig, UniverseConfig, CanaryProfile]:
    source = env or os.environ
    risk_profile_name = source.get("RISK_PROFILE", DEFAULT_RISK_PROFILE)
    universe_profile_name = source.get("UNIVERSE_PROFILE", DEFAULT_UNIVERSE_PROFILE)
    canary_profile_name = source.get("CANARY_PROFILE", DEFAULT_CANARY_PROFILE)
    risk_path = _profile_path(risk_profile_name, "risk_profiles")
    universe_path = _profile_path(universe_profile_name, "universe")
    canary_path = canary_profile_path(CONFIG_ROOT, canary_profile_name)
    if not risk_path.exists():
        raise ConfigLoaderError(f"Risk profile not found: {risk_path}")
    if not universe_path.exists():
        raise ConfigLoaderError(f"Universe profile not found: {universe_path}")
    if not canary_path.exists():
        raise ConfigLoaderError(f"Canary profile not found: {canary_path}")
    return (
        load_risk_profile(str(risk_path)),
        load_universe(str(universe_path)),
        load_canary_profile(str(canary_path)),
    )


def _enforce_override(value: float, default: float, cap: float, name: str) -> float:
    max_allowed = min(default, cap)
    if value > max_allowed:
        raise ConfigLoaderError(f"{name} override exceeds max allowed {max_allowed}")
    return value


def build_constraints(
    risk: RiskProfileConfig, universe: UniverseConfig, env: Mapping[str, str] | None = None
) -> PortfolioConstraints:
    source = env or os.environ
    daily_limit = float(
        source.get("DAILY_LOSS_LIMIT_PCT", risk.risk_budget.daily_loss_limit_pct_default)
    )
    daily_limit = _enforce_override(
        daily_limit,
        risk.risk_budget.daily_loss_limit_pct_default,
        risk.risk_budget.daily_loss_limit_pct_cap,
        "DAILY_LOSS_LIMIT_PCT",
    )
    total_max_notional = float(
        source.get(
            "TOTAL_MAX_NOTIONAL_PCT",
            risk.portfolio_limits.total_max_notional_pct,
        )
    )
    total_max_notional = _enforce_override(
        total_max_notional,
        risk.portfolio_limits.total_max_notional_pct,
        risk.portfolio_limits.total_max_notional_pct,
        "TOTAL_MAX_NOTIONAL_PCT",
    )

    membership = {symbol.upper(): "majors" for symbol in universe.majors}
    for symbol in universe.alts:
        membership[symbol.upper()] = "alts"

    return PortfolioConstraints(
        mode=PortfolioMode(risk.mode.value if isinstance(risk.mode, PortfolioMode) else risk.mode),
        profile_name=risk.profile_name,
        profile_version=risk.version,
        whitelist=[sym.upper() for sym in universe.whitelist],
        class_membership=membership,
        asset_classes=risk.asset_classes,
        risk_weights={
            symbol: risk.asset_classes[membership[symbol]].weight
            for symbol in membership
            if membership[symbol] in risk.asset_classes
        },
        single_trade_risk_fraction=risk.risk_budget.per_trade_max_loss_pct,
        total_exposure_fraction=total_max_notional,
        per_symbol_exposure_fraction=risk.portfolio_limits.per_symbol_max_notional_pct_override,
        per_symbol_exposure_fraction_default={
            "majors": risk.asset_classes["majors"].per_symbol_max_notional_pct,
            "alts": risk.asset_classes["alts"].per_symbol_max_notional_pct,
        },
        class_exposure_fraction={
            "majors": risk.asset_classes["majors"].total_class_max_notional_pct,
            "alts": risk.asset_classes["alts"].total_class_max_notional_pct,
        },
        leverage_limit={
            "majors": risk.asset_classes["majors"].max_leverage,
            "alts": risk.asset_classes["alts"].max_leverage,
        },
        daily_loss_limit_fraction=daily_limit,
        open_cooldown_seconds={
            "majors": risk.asset_classes["majors"].new_position_cooldown_sec,
            "alts": risk.asset_classes["alts"].new_position_cooldown_sec,
        },
        add_cooldown_seconds={
            "majors": risk.asset_classes["majors"].add_position_cooldown_sec,
            "alts": risk.asset_classes["alts"].add_position_cooldown_sec,
        },
        max_spread_bps=risk.market_protections.max_spread_bps,
        volatility_guard_atr_mult=risk.market_protections.volatility_guard_atr_mult,
        forbid_market_orders_when_guarded=risk.market_protections.forbid_market_orders_when_guarded,
        decision_interval_seconds=risk.defaults.decision_interval_sec,
        timeframe=risk.defaults.timeframe,
    )
