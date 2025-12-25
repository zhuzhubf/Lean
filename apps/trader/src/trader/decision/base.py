"""Decision provider abstractions."""

from __future__ import annotations

import abc
import logging
from typing import Protocol

from trader.schemas import (
    AccountState,
    MarketSnapshot,
    PortfolioConstraints,
    TraceContext,
    TradePlan,
)

LOGGER = logging.getLogger(__name__)


class DecisionProvider(abc.ABC):
    """Abstract decision provider."""

    @abc.abstractmethod
    def propose_plan(
        self,
        snapshot: MarketSnapshot,
        account: AccountState,
        constraints: PortfolioConstraints,
        trace: TraceContext,
        draft_plan: TradePlan | None = None,
    ) -> TradePlan:
        """Return a TradePlan for the provided context."""


class RateLimiter(Protocol):
    """Simple callable rate limiter protocol."""

    def __call__(self) -> None:  # pragma: no cover - implementations are injected
        ...


def safe_hold(reason: str, snapshot: MarketSnapshot) -> TradePlan:
    """Create a HOLD plan with rationale set."""

    LOGGER.debug("Returning HOLD plan", extra={"reason": reason, "symbol": snapshot.symbol})
    return TradePlan(action="HOLD", symbol=snapshot.symbol, rationale=reason)


def ensure_numeric(value: float | None, fallback: float) -> float:
    """Utility to coerce numeric values."""

    return fallback if value is None else float(value)


__all__ = ["DecisionProvider", "RateLimiter", "safe_hold", "ensure_numeric"]
