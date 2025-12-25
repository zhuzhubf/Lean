"""Main orchestration loop for decision -> risk -> execution."""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Sequence

from trader.audit.logger import configure_json_logging
from trader.decision import (
    OpenAICompatProvider,
    ProviderRouter,
    RuleBasedProvider,
    XAICompatProvider,
)
from trader.decision.base import DecisionProvider
from trader.execution.executor import ExecutionMode, Executor
from trader.execution.order_manager import CanaryConstraints, OrderManager
from trader.risk.gateway import RiskGateway
from trader.schemas import (
    OHLCV,
    AccountState,
    Action,
    MarketSnapshot,
    PortfolioConstraints,
    RiskDecisionType,
    TraceContext,
)
from trader.storage.db import TraderStorage
from trader.strategy import StrategyContext, StrategyEngine

LOGGER = logging.getLogger(__name__)


def build_router(
    provider_name: str,
    openai_kwargs: dict | None = None,
    xai_kwargs: dict | None = None,
) -> ProviderRouter:
    fallback = RuleBasedProvider()

    def _openai_factory() -> DecisionProvider:
        return OpenAICompatProvider(**(openai_kwargs or {}))

    def _xai_factory() -> DecisionProvider:
        return XAICompatProvider(**(xai_kwargs or {}))

    return ProviderRouter(
        provider_name=provider_name,
        openai_factory=_openai_factory if openai_kwargs is not None else None,
        xai_factory=_xai_factory if xai_kwargs is not None else None,
        fallback_provider=fallback,
    )


def synthetic_snapshot(symbol: str) -> MarketSnapshot:
    now = int(time.time())
    base_price = 50000 if symbol.upper() == "BTC" else 3000
    close_1h = float(base_price)
    return MarketSnapshot(
        symbol=symbol.upper(),
        timestamp=now,
        price=float(base_price),
        spread_bps=12.0,
        atr=base_price * 0.002,
        funding_rate=0.0,
        liquidity_score=0.8,
        ohlcv_1h=OHLCV(
            open=close_1h * 0.995,
            high=close_1h * 1.01,
            low=close_1h * 0.99,
            close=close_1h,
            volume=10_000,
        ),
        ohlcv_4h=OHLCV(
            open=close_1h * 0.99,
            high=close_1h * 1.02,
            low=close_1h * 0.985,
            close=close_1h * 1.001,
            volume=40_000,
        ),
    )


def default_account_state(symbols: Sequence[str]) -> AccountState:
    return AccountState(equity=100000.0, positions=[], daily_pnl=0.0)


def run_once(
    symbols: Sequence[str],
    constraints: PortfolioConstraints,
    router: ProviderRouter,
    executor: Executor,
    storage: TraderStorage,
    order_manager: OrderManager,
    mode: ExecutionMode,
    run_id: str,
    model_name: str | None = None,
    strategy: StrategyEngine | None = None,
    safe_mode: bool = False,
) -> bool:
    gateway = RiskGateway(constraints)
    planner = strategy or StrategyEngine()
    entered_safe_mode = safe_mode
    for symbol in symbols:
        snapshot = synthetic_snapshot(symbol)
        account = default_account_state(symbols)
        trace = TraceContext(
            trace_id=str(uuid.uuid4()),
            run_id=run_id,
            model_id=model_name,
        )
        strategy_ctx = StrategyContext(
            snapshot=snapshot, account=account, constraints=constraints, trace=trace
        )
        draft_plan = planner.draft_plan(strategy_ctx)
        plan = router.propose_plan(snapshot, account, constraints, trace, draft_plan=draft_plan)
        storage.record_decision(
            trace.trace_id,
            trace.provider_id or "unknown",
            trace.model_id,
            {"draft_plan": draft_plan.model_dump()},
            plan.model_dump(),
            trace.created_at.isoformat(),
        )
        risk = gateway.evaluate(plan, snapshot, account)
        storage.record_risk(
            trace.trace_id,
            risk.decision.value,
            risk.reasons,
            risk.adjusted_plan.model_dump() if risk.adjusted_plan else None,
            trace.created_at.isoformat(),
        )
        if risk.decision == RiskDecisionType.REJECT:
            LOGGER.info(
                "Plan rejected",
                extra={"trace_id": trace.trace_id, "symbol": symbol, "reasons": risk.reasons},
            )
            continue
        if entered_safe_mode and plan.action == Action.OPEN:
            LOGGER.warning(
                "Skipping open due to safe mode",
                extra={"trace_id": trace.trace_id, "symbol": symbol},
            )
            continue
        plan_to_execute = risk.adjusted_plan or plan
        result = executor.execute(
            plan_to_execute,
            risk,
            snapshot,
            mode,
            order_manager=order_manager,
            trace_id=trace.trace_id,
            equity=account.equity,
        )
        storage.record_execution(
            trace.trace_id,
            mode,
            result.status,
            {
                "price": result.price,
                "notional": result.executed_notional,
                "error": result.error,
                "client_order_id": result.client_order_id,
            },
            trace.created_at.isoformat(),
        )
        reconciliation = order_manager.reconcile()
        if reconciliation.entered_safe_mode:
            LOGGER.error(
                "Entering safe mode due to reconciliation mismatches",
                extra={"mismatches": reconciliation.mismatches},
            )
            entered_safe_mode = True
    return entered_safe_mode


def run_loop(
    symbols: Sequence[str],
    constraints: PortfolioConstraints,
    provider_name: str,
    mode: ExecutionMode,
    db_path: Path,
    iterations: int = 1,
    interval_seconds: int = 900,
    openai_kwargs: dict | None = None,
    xai_kwargs: dict | None = None,
    canary: CanaryConstraints | None = None,
) -> None:
    configure_json_logging()
    router = build_router(provider_name, openai_kwargs=openai_kwargs, xai_kwargs=xai_kwargs)
    executor = Executor()
    storage = TraderStorage(db_path)
    order_manager = OrderManager(storage, canary=canary)
    strategy = StrategyEngine()
    run_id = uuid.uuid4().hex
    safe_mode = False
    for _ in range(iterations):
        safe_mode = run_once(
            symbols,
            constraints,
            router,
            executor,
            storage,
            order_manager,
            mode,
            run_id,
            model_name=(openai_kwargs or {}).get("model") if provider_name == "openai" else None,
            strategy=strategy,
            safe_mode=safe_mode,
        )
        if iterations > 1:
            time.sleep(interval_seconds)
