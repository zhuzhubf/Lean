"""Execution layer supporting shadow and guarded live modes."""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any, Mapping

from trader.execution.order_manager import OrderManager, OrderState
from trader.schemas import ExecutionMode, MarketSnapshot, RiskDecision, TradePlan

LOGGER = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    status: str
    mode: ExecutionMode
    price: float | None
    executed_notional: float | None
    error: str | None = None
    client_order_id: str | None = None
    raw: Mapping[str, Any] | None = None


class Executor:
    """Execution entrypoint."""

    def __init__(self) -> None:
        self.client = None  # placeholder for Hyperliquid SDK in future

    def execute(
        self,
        plan: TradePlan,
        decision: RiskDecision,
        snapshot: MarketSnapshot,
        mode: ExecutionMode,
        *,
        order_manager: OrderManager | None = None,
        trace_id: str | None = None,
        equity: float | None = None,
    ) -> ExecutionResult:
        record = None
        if order_manager and trace_id and equity is not None:
            record = order_manager.submit(plan, trace_id, mode, equity)
        if mode == ExecutionMode.LIVE:
            self._enforce_live_guardrails()
            result = self._execute_live(plan, decision, snapshot)
        else:
            result = self._execute_shadow(plan, decision, snapshot)
        if record:
            final_state = OrderState.FILLED if result.status == "filled" else OrderState.FAILED
            order_manager.transition(record, final_state, result.error)
        return result

    def _execute_shadow(
        self, plan: TradePlan, decision: RiskDecision, snapshot: MarketSnapshot
    ) -> ExecutionResult:
        fill_price = plan.limit_price or snapshot.price
        executed_notional = plan.notional
        client_order_id = f"shadow-{uuid.uuid4().hex[:12]}"
        LOGGER.info(
            "Shadow execution recorded",
            extra={
                "trace_id": client_order_id,
                "symbol": plan.symbol,
                "notional": executed_notional,
                "price": fill_price,
                "decision": decision.reasons,
            },
        )
        return ExecutionResult(
            status="filled",
            mode=ExecutionMode.SHADOW,
            price=fill_price,
            executed_notional=executed_notional,
            client_order_id=client_order_id,
        )

    def _execute_live(
        self, plan: TradePlan, decision: RiskDecision, snapshot: MarketSnapshot
    ) -> ExecutionResult:
        # Live execution stubbed until Hyperliquid SDK wiring is enabled.
        raise NotImplementedError("Live execution is guarded and not yet implemented")

    def _enforce_live_guardrails(self) -> None:
        if os.getenv("LIVE_TRADING", "false").lower() != "true":
            raise RuntimeError("Live trading disabled via environment")
        if os.getenv("RISK_ACK", "").strip() != "I_UNDERSTAND_LIVE_TRADING":
            raise RuntimeError("RISK_ACK not acknowledged")
        if os.getenv("HL_API_WALLET_CONFIGURED", "false").lower() != "true":
            raise RuntimeError("Hyperliquid wallet not configured for live trading")
        token = os.getenv("LIVE_ENABLE_TOKEN")
        token_path = os.getenv("LIVE_ENABLE_TOKEN_PATH")
        if not token:
            raise RuntimeError("LIVE_ENABLE_TOKEN not provided; live disabled")
        if token_path:
            try:
                with open(token_path, "r", encoding="utf-8") as handle:
                    content = handle.read().strip()
            except OSError as exc:  # pragma: no cover - defensive
                raise RuntimeError("Live enable token file not readable") from exc
            if content != token:
                raise RuntimeError("Live enable token mismatch; aborting live mode")
