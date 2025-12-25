"""Core data contracts for the trader service.

All public models are defined with Pydantic v2 to ensure strict validation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from pydantic import BaseModel, Field, ValidationError, model_validator


class Action(str, Enum):
    """Supported trade actions."""

    OPEN = "OPEN"
    CLOSE = "CLOSE"
    REDUCE = "REDUCE"
    HOLD = "HOLD"


class Side(str, Enum):
    """Position side."""

    LONG = "LONG"
    SHORT = "SHORT"


class OrderType(str, Enum):
    """Order type."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"


class TimeInForce(str, Enum):
    """Time in force options."""

    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


class RiskDecisionType(str, Enum):
    """Risk decision outcome."""

    ALLOW = "ALLOW"
    REJECT = "REJECT"


class ExecutionMode(str, Enum):
    """Execution modes."""

    SHADOW = "shadow"
    LIVE = "live"


class OHLCV(BaseModel):
    """Simple OHLCV container."""

    open: float = Field(..., ge=0)
    high: float = Field(..., ge=0)
    low: float = Field(..., ge=0)
    close: float = Field(..., ge=0)
    volume: float = Field(..., ge=0)

    model_config = {
        "extra": "ignore",
        "populate_by_name": True,
    }


class Position(BaseModel):
    """Current position details."""

    symbol: str
    side: Side
    size: float = Field(..., gt=0)
    entry_price: float = Field(..., gt=0)
    leverage: float | None = Field(default=None, gt=0)
    unrealized_pnl: float | None = None

    model_config = {"extra": "ignore"}


class MarketSnapshot(BaseModel):
    """Aggregated market snapshot for decision making."""

    symbol: str
    timestamp: int
    price: float = Field(..., gt=0)
    spread_bps: float = Field(..., ge=0)
    atr: float | None = Field(default=None, ge=0)
    funding_rate: float | None = None
    liquidity_score: float | None = Field(default=None, ge=0, le=1)
    ohlcv_1h: OHLCV
    ohlcv_4h: OHLCV

    model_config = {"extra": "ignore"}


class AccountState(BaseModel):
    """Account state representation."""

    equity: float = Field(..., gt=0)
    available_margin: float | None = Field(default=None, ge=0)
    positions: list[Position] = Field(default_factory=list)
    unrealized_pnl: float | None = None
    daily_pnl: float = 0.0

    model_config = {"extra": "ignore"}


class PortfolioMode(str, Enum):
    """Risk modes."""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class PortfolioConstraints(BaseModel):
    """Risk and portfolio constraints."""

    mode: PortfolioMode = PortfolioMode.MODERATE
    profile_name: str = "moderate"
    profile_version: int = 1
    whitelist: list[str] = Field(default_factory=lambda: ["BTC", "ETH"])
    class_membership: dict[str, str] = Field(default_factory=dict)
    asset_classes: Mapping[str, Mapping[str, Any]] = Field(default_factory=dict)
    risk_weights: dict[str, float] = Field(default_factory=dict)
    leverage_limit: Mapping[str, float] = Field(default_factory=dict)
    per_symbol_exposure_fraction_default: Mapping[str, float] = Field(default_factory=dict)
    per_symbol_exposure_fraction: Mapping[str, float] = Field(default_factory=dict)
    class_exposure_fraction: Mapping[str, float] = Field(default_factory=dict)
    total_exposure_fraction: float = Field(default=0.75, gt=0, lt=1)
    single_trade_risk_fraction: float = Field(default=0.015, gt=0, lt=0.1)
    daily_loss_limit_fraction: float = Field(default=0.1, gt=0, lt=1)
    open_cooldown_seconds: Mapping[str, int] = Field(default_factory=dict)
    add_cooldown_seconds: Mapping[str, int] = Field(default_factory=dict)
    max_spread_bps: float = Field(default=35.0, gt=0)
    volatility_guard_atr_mult: float = Field(default=2.5, gt=0)
    forbid_market_orders_when_guarded: bool = True
    decision_interval_seconds: int = Field(default=900, gt=0)
    timeframe: str = "1h-4h"

    model_config = {"extra": "ignore"}

    def asset_class_for_symbol(self, symbol: str) -> str | None:
        return self.class_membership.get(symbol.upper())

    def max_leverage_for_symbol(self, symbol: str) -> float:
        classification = self.asset_class_for_symbol(symbol) or "alts"
        return self.leverage_limit.get(classification, self.leverage_limit.get("alts", 1.0))

    def per_symbol_cap_fraction(self, symbol: str) -> float:
        symbol_upper = symbol.upper()
        if symbol_upper in self.per_symbol_exposure_fraction:
            return float(self.per_symbol_exposure_fraction[symbol_upper])
        classification = self.asset_class_for_symbol(symbol_upper) or "alts"
        return float(self.per_symbol_exposure_fraction_default.get(classification, 0))

    def class_cap_fraction(self, classification: str) -> float:
        return float(self.class_exposure_fraction.get(classification, 0))

    def open_cooldown_for_symbol(self, symbol: str) -> int:
        classification = self.asset_class_for_symbol(symbol) or "alts"
        return int(self.open_cooldown_seconds.get(classification, 0))

    def add_cooldown_for_symbol(self, symbol: str) -> int:
        classification = self.asset_class_for_symbol(symbol) or "alts"
        return int(self.add_cooldown_seconds.get(classification, 0))


class TakeProfitStopLoss(BaseModel):
    """Container for TP/SL levels."""

    take_profit: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)

    model_config = {"extra": "ignore"}


class TradePlan(BaseModel):
    """Structured trade proposal."""

    action: Action
    symbol: str
    side: Side | None = None
    leverage: float | None = Field(default=None, gt=0)
    notional: float | None = Field(default=None, gt=0)
    size: float | None = Field(default=None, gt=0)
    order_type: OrderType = OrderType.LIMIT
    limit_price: float | None = Field(default=None, gt=0)
    tp_sl: TakeProfitStopLoss | None = None
    time_in_force: TimeInForce = TimeInForce.GTC
    valid_until: int | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    rationale: str | None = None

    model_config = {
        "extra": "forbid",
        "validate_assignment": True,
    }

    @model_validator(mode="after")
    def _validate_payload(self) -> "TradePlan":
        if self.action in {Action.OPEN, Action.REDUCE} and self.side is None:
            raise ValueError("side is required for OPEN/REDUCE actions")
        if self.action == Action.HOLD:
            return self
        if self.notional is None and self.size is None:
            raise ValueError("notional or size is required for non-HOLD actions")
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit_price is required for LIMIT orders")
        if self.order_type == OrderType.MARKET and self.limit_price is not None:
            # Avoid mixing price for market orders to keep accounting simple.
            raise ValueError("limit_price must be omitted for MARKET orders")
        return self


class RiskDecision(BaseModel):
    """Result of risk evaluation."""

    decision: RiskDecisionType
    reasons: list[str] = Field(default_factory=list)
    adjusted_plan: TradePlan | None = None

    model_config = {"extra": "forbid"}


class TraceContext(BaseModel):
    """Trace metadata for auditability."""

    trace_id: str
    run_id: str | None = None
    provider_id: str | None = None
    model_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"extra": "ignore"}


def validate_trade_plan_payload(payload: Any) -> TradePlan:
    """Validate arbitrary payload as a TradePlan, raising on failure."""

    if isinstance(payload, TradePlan):
        return payload
    try:
        return TradePlan.model_validate(payload)
    except ValidationError as exc:  # pragma: no cover - delegated to unit tests
        raise ValueError(f"Invalid TradePlan: {exc}") from exc


def merge_constraints(
    base: PortfolioConstraints, overrides: Mapping[str, Any] | None
) -> PortfolioConstraints:
    """Create a new constraint object with overrides applied."""

    if not overrides:
        return base
    data = base.model_dump()
    for key, value in overrides.items():
        if key in data and value is not None:
            data[key] = value
    return PortfolioConstraints.model_validate(data)


__all__ = [
    "Action",
    "Side",
    "OrderType",
    "TimeInForce",
    "RiskDecisionType",
    "ExecutionMode",
    "MarketSnapshot",
    "AccountState",
    "PortfolioConstraints",
    "PortfolioMode",
    "TradePlan",
    "RiskDecision",
    "TraceContext",
    "validate_trade_plan_payload",
    "merge_constraints",
    "Position",
    "OHLCV",
    "TakeProfitStopLoss",
]
