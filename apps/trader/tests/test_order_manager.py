import time

import pytest

from trader.execution.order_manager import CanaryConstraints, OrderManager, OrderState
from trader.schemas import ExecutionMode, TradePlan, validate_trade_plan_payload
from trader.storage.db import TraderStorage


def _plan(symbol: str = "BTC", notional: float = 1000.0) -> TradePlan:
    return validate_trade_plan_payload(
        {
            "action": "OPEN",
            "side": "BUY",
            "symbol": symbol,
            "order_type": "LIMIT",
            "limit_price": 100.0,
            "notional": notional,
            "leverage": 2,
            "tp": 110.0,
            "sl": 95.0,
        }
    )


def test_idempotent_submit(tmp_path):
    storage = TraderStorage(tmp_path / "orders.db")
    manager = OrderManager(storage)
    plan = _plan()
    first = manager.submit(plan, "trace-1", ExecutionMode.SHADOW, 100_000)
    second = manager.submit(plan, "trace-1", ExecutionMode.SHADOW, 100_000)
    assert first.client_order_id == second.client_order_id
    manager.transition(first, OrderState.FILLED)
    record = storage.fetch_order_by_trace("trace-1")
    assert record["state"] == OrderState.FILLED.value


def test_reconciliation_trips_safe_mode(tmp_path):
    storage = TraderStorage(tmp_path / "orders.db")
    manager = OrderManager(storage)
    plan = _plan()
    record = manager.submit(plan, "trace-2", ExecutionMode.SHADOW, 100_000)
    # Simulate staleness
    manager.transition(record, OrderState.ACKED)
    old_ts = int(time.time()) - 2000
    storage.upsert_order(
        client_order_id=record.client_order_id,
        trace_id="trace-2",
        symbol=plan.symbol,
        side=plan.side,
        notional=plan.notional,
        mode=ExecutionMode.SHADOW,
        state=OrderState.ACKED.value,
        error=None,
        ts=old_ts,
    )
    result = manager.reconcile(stale_after_seconds=100)
    assert result.entered_safe_mode
    assert record.client_order_id in result.mismatches


def test_canary_rejects_risky_orders(tmp_path):
    storage = TraderStorage(tmp_path / "orders.db")
    manager = OrderManager(
        storage,
        canary=CanaryConstraints(
            enabled=True,
            allowed_symbols=["BTC"],
            max_daily_orders=1,
            per_order_notional_cap_pct=0.02,
            total_notional_cap_pct=0.05,
        ),
    )
    plan = _plan(notional=10_000)
    with pytest.raises(RuntimeError):
        manager.submit(plan, "trace-3", ExecutionMode.LIVE, 100_000)
