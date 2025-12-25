"""Versioned risk profile configuration models."""

from __future__ import annotations

from typing import Mapping

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator

from trader.schemas import PortfolioMode


class AssetClassConfig(BaseModel):
    weight: float = Field(..., gt=0)
    max_leverage: float = Field(..., gt=0)
    per_symbol_max_notional_pct: float = Field(..., gt=0, lt=1)
    total_class_max_notional_pct: float = Field(..., gt=0, lt=1)
    new_position_cooldown_sec: int = Field(..., ge=0)
    add_position_cooldown_sec: int = Field(..., ge=0)

    model_config = {"extra": "forbid"}


class PortfolioLimits(BaseModel):
    total_max_notional_pct: float = Field(..., gt=0, lt=1)
    per_symbol_max_notional_pct_override: Mapping[str, float] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class RiskBudget(BaseModel):
    per_trade_max_loss_pct: float = Field(..., gt=0, lt=0.1)
    daily_loss_limit_pct_default: float = Field(..., gt=0, lt=1)
    daily_loss_limit_pct_cap: float = Field(..., gt=0, lt=1)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _validate_limits(self) -> "RiskBudget":
        if self.daily_loss_limit_pct_default > self.daily_loss_limit_pct_cap:
            raise ValueError("default daily loss limit exceeds cap")
        return self


class MarketProtections(BaseModel):
    max_spread_bps: float = Field(..., gt=0)
    volatility_guard_atr_mult: float = Field(..., gt=0)
    forbid_market_orders_when_guarded: bool = True

    model_config = {"extra": "forbid"}


class DefaultSchedule(BaseModel):
    decision_interval_sec: int = Field(..., gt=0)
    timeframe: str

    model_config = {"extra": "forbid"}


class RiskProfileConfig(BaseModel):
    profile_name: str
    version: int = Field(..., ge=1)
    defaults: DefaultSchedule
    asset_classes: Mapping[str, AssetClassConfig]
    portfolio_limits: PortfolioLimits
    risk_budget: RiskBudget
    market_protections: MarketProtections
    mode: PortfolioMode = PortfolioMode.MODERATE

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _validate_classes(self) -> "RiskProfileConfig":
        for name in ("majors", "alts"):
            if name not in self.asset_classes:
                raise ValueError(f"missing asset class config: {name}")
        return self


def load_risk_profile(path: str) -> RiskProfileConfig:
    """Load and validate a risk profile YAML file."""

    with open(path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    try:
        return RiskProfileConfig.model_validate(raw)
    except ValidationError as exc:  # pragma: no cover - delegated to tests
        raise ValueError(f"Invalid risk profile config at {path}: {exc}") from exc
