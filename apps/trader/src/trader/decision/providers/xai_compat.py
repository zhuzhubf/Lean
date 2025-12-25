"""xAI-compatible provider skeleton."""

from __future__ import annotations

import json
import logging
from typing import Callable

from trader.decision.base import DecisionProvider, RateLimiter, safe_hold
from trader.schemas import (
    AccountState,
    MarketSnapshot,
    PortfolioConstraints,
    TraceContext,
    TradePlan,
    validate_trade_plan_payload,
)

LOGGER = logging.getLogger(__name__)

ChatCaller = Callable[[str], str]


class XAICompatProvider(DecisionProvider):
    """Lightweight xAI-compatible provider."""

    def __init__(
        self,
        chat_caller: ChatCaller,
        rate_limiter: RateLimiter | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.chat_caller = chat_caller
        self.rate_limiter = rate_limiter
        self.timeout_seconds = timeout_seconds

    def _prompt(
        self,
        snapshot: MarketSnapshot,
        account: AccountState,
        constraints: PortfolioConstraints,
        trace: TraceContext,
        draft_plan: TradePlan | None = None,
    ) -> str:
        schema = TradePlan.model_json_schema()
        payload = {
            "instruction": "Respond strictly with JSON matching the TradePlan schema.",
            "schema": schema,
            "symbol": snapshot.symbol,
            "price": snapshot.price,
            "equity": account.equity,
            "mode": constraints.mode.value,
            "trace_id": trace.trace_id,
        }
        if draft_plan is not None:
            payload["draft_plan"] = draft_plan.model_dump()
        return json.dumps(payload)

    def propose_plan(
        self,
        snapshot: MarketSnapshot,
        account: AccountState,
        constraints: PortfolioConstraints,
        trace: TraceContext,
        draft_plan: TradePlan | None = None,
    ) -> TradePlan:
        if self.rate_limiter:
            self.rate_limiter()
        try:
            prompt = self._prompt(snapshot, account, constraints, trace, draft_plan=draft_plan)
            raw = self.chat_caller(prompt)
            plan = validate_trade_plan_payload(json.loads(raw))
            return plan
        except Exception as exc:  # pragma: no cover - exercised in integration
            LOGGER.warning(
                "xAI provider failure, returning HOLD",
                extra={"error": str(exc), "symbol": snapshot.symbol},
            )
            if draft_plan is not None:
                return draft_plan.model_copy(update={"rationale": f"xai_error: {exc}"})
            return safe_hold(f"provider_error: {exc}", snapshot)
