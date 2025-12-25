"""Simple rule-based provider for smoke testing."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from trader.decision.base import DecisionProvider, ensure_numeric
from trader.schemas import (
    AccountState,
    Action,
    MarketSnapshot,
    PortfolioConstraints,
    Side,
    TraceContext,
    TradePlan,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class RuleBasedProvider(DecisionProvider):
    """Trend-following heuristic suitable for dry-runs."""

    min_confidence: float = 0.35

    def propose_plan(
        self,
        snapshot: MarketSnapshot,
        account: AccountState,
        constraints: PortfolioConstraints,
        trace: TraceContext,
        draft_plan: TradePlan | None = None,
    ) -> TradePlan:
        if draft_plan is not None:
            return draft_plan
        short_trend = snapshot.ohlcv_1h.close - snapshot.ohlcv_1h.open
        long_trend = snapshot.ohlcv_4h.close - snapshot.ohlcv_4h.open
        direction = None
        if short_trend > 0 and long_trend > 0:
            direction = Side.LONG
        elif short_trend < 0 and long_trend < 0:
            direction = Side.SHORT

        if direction is None:
            return TradePlan(action=Action.HOLD, symbol=snapshot.symbol, rationale="No alignment")

        notional = ensure_numeric(account.equity * 0.01, fallback=100.0)
        leverage = constraints.max_leverage_for_symbol(snapshot.symbol)
        limit_price = snapshot.price
        LOGGER.debug(
            "RuleBasedProvider proposes plan",
            extra={"symbol": snapshot.symbol, "side": direction.value, "notional": notional},
        )
        return TradePlan(
            action=Action.OPEN,
            symbol=snapshot.symbol,
            side=direction,
            leverage=leverage,
            notional=notional,
            order_type="LIMIT",
            limit_price=limit_price,
            tp_sl={"stop_loss": limit_price * 0.99},
            confidence=self.min_confidence,
            rationale="1h/4h trend alignment",
        )
