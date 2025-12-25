"""Translate signals into high-level trade intents."""

from __future__ import annotations

from dataclasses import dataclass

from trader.schemas import Action, Side
from trader.strategy.signals import SignalFeatures


@dataclass
class TradeIntent:
    """High-level intent before converting to a TradePlan."""

    action: Action
    side: Side | None
    conviction: float
    rationale: str


class IntentBuilder:
    """Simple swing intent builder based on trend agreement and volatility."""

    def __init__(self, min_conviction: float = 0.1, max_conviction: float = 0.6):
        self.min_conviction = min_conviction
        self.max_conviction = max_conviction

    def build(self, features: SignalFeatures) -> TradeIntent:
        bias = features.agreement
        if abs(bias) < self.min_conviction:
            return TradeIntent(Action.HOLD, None, conviction=0.0, rationale="neutral")

        side = Side.LONG if bias > 0 else Side.SHORT
        scaled_conviction = min(self.max_conviction, max(self.min_conviction, abs(bias)))
        rationale = f"agreement={features.agreement:.4f}, atr_pct={features.atr_pct:.4f}"
        return TradeIntent(Action.OPEN, side, conviction=scaled_conviction, rationale=rationale)
