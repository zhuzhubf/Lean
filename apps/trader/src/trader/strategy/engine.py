"""Strategy orchestrator for swing trading plans."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from trader.schemas import (
    AccountState,
    MarketSnapshot,
    PortfolioConstraints,
    TraceContext,
    TradePlan,
)
from trader.strategy.intent import IntentBuilder
from trader.strategy.plan_builder import PlanBuilder
from trader.strategy.signals import SignalEngine

LOGGER = logging.getLogger(__name__)


@dataclass
class StrategyContext:
    snapshot: MarketSnapshot
    account: AccountState
    constraints: PortfolioConstraints
    trace: TraceContext


class StrategyEngine:
    """Compute draft TradePlans from signals and intents."""

    def __init__(self) -> None:
        self.signals = SignalEngine()
        self.intent_builder = IntentBuilder()
        self.plan_builder = PlanBuilder()

    def draft_plan(self, context: StrategyContext) -> TradePlan:
        features = self.signals.compute(context.snapshot)
        intent = self.intent_builder.build(features)
        plan = self.plan_builder.build(
            intent=intent,
            features=features,
            snapshot=context.snapshot,
            account=context.account,
            constraints=context.constraints,
        )
        LOGGER.debug(
            "draft_plan",
            extra={
                "trace_id": context.trace.trace_id,
                "symbol": context.snapshot.symbol,
                "intent": intent.rationale,
                "action": plan.action.value,
            },
        )
        return plan
