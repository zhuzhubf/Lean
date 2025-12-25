"""Convert intents into executable TradePlans."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from trader.schemas import (
    AccountState,
    Action,
    MarketSnapshot,
    PortfolioConstraints,
    Side,
    TakeProfitStopLoss,
    TradePlan,
)
from trader.strategy.intent import TradeIntent
from trader.strategy.signals import SignalFeatures


class PlanBuilder:
    """Plan builder that enforces TP/SL and size suggestions."""

    def __init__(self, tp_multiple: float = 2.5, sl_multiple: float = 1.5):
        self.tp_multiple = tp_multiple
        self.sl_multiple = sl_multiple

    def _target_notional(
        self,
        symbol: str,
        account: AccountState,
        constraints: PortfolioConstraints,
        conviction: float,
    ) -> float:
        cap_fraction = constraints.per_symbol_cap_fraction(symbol)
        weight = constraints.risk_weights.get(symbol.upper(), 1.0)
        total_cap = constraints.total_exposure_fraction
        notional_fraction = min(cap_fraction * weight, total_cap)
        adjusted_fraction = min(max(conviction, 0.1), 1.0) * notional_fraction
        return account.equity * adjusted_fraction

    def build(
        self,
        intent: TradeIntent,
        features: SignalFeatures,
        snapshot: MarketSnapshot | None,
        account: AccountState,
        constraints: PortfolioConstraints,
    ) -> TradePlan:
        if intent.action == Action.HOLD or intent.side is None:
            return TradePlan(action=Action.HOLD, symbol=features.symbol, rationale=intent.rationale)

        price = snapshot.price if snapshot else 0.0  # type: ignore[attr-defined]
        atr = snapshot.atr if snapshot else 0.0  # type: ignore[attr-defined]
        atr_distance = atr if atr and atr > 0 else price * 0.003
        stop_distance = max(atr_distance * self.sl_multiple, price * 0.001)
        tp_distance = max(atr_distance * self.tp_multiple, price * 0.002)

        if intent.side == Side.LONG:
            stop_loss = price - stop_distance
            take_profit = price + tp_distance
        else:
            stop_loss = price + stop_distance
            take_profit = price - tp_distance

        valid_until = int((datetime.now(timezone.utc) + timedelta(hours=6)).timestamp())
        notional = self._target_notional(features.symbol, account, constraints, intent.conviction)

        return TradePlan(
            action=intent.action,
            symbol=features.symbol,
            side=intent.side,
            leverage=constraints.max_leverage_for_symbol(features.symbol),
            notional=notional,
            order_type="LIMIT",
            limit_price=price,
            tp_sl=TakeProfitStopLoss(take_profit=take_profit, stop_loss=stop_loss),
            confidence=min(1.0, max(0.0, intent.conviction)),
            valid_until=valid_until,
            rationale=intent.rationale,
        )
