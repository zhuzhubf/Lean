"""Order management and reconciliation helpers."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping, Sequence

from trader.schemas import ExecutionMode, TradePlan
from trader.storage.db import TraderStorage


class OrderState(str, Enum):
    SUBMITTED = "submitted"
    ACKED = "acked"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass
class OrderRecord:
    trace_id: str
    client_order_id: str
    symbol: str
    side: str
    notional: float
    mode: ExecutionMode
    state: OrderState
    last_error: str | None = None
    created_ts: int | None = None
    updated_ts: int | None = None


@dataclass
class ReconciliationResult:
    mismatches: list[str]
    entered_safe_mode: bool


@dataclass
class CanaryConstraints:
    enabled: bool = False
    allowed_symbols: Sequence[str] | None = None
    max_daily_orders: int = 2
    per_order_notional_cap_pct: float = 0.02
    total_notional_cap_pct: float = 0.05


class OrderManager:
    """Stateful manager providing idempotent order tracking."""

    def __init__(self, storage: TraderStorage, canary: CanaryConstraints | None = None) -> None:
        self.storage = storage
        self.canary = canary or CanaryConstraints(enabled=False)

    def _derive_client_order_id(self, trace_id: str, plan: TradePlan) -> str:
        suffix = uuid.uuid5(uuid.NAMESPACE_URL, trace_id + plan.symbol).hex[:8]
        return f"{trace_id[:12]}-{plan.symbol.lower()}-{suffix}"

    def submit(
        self, plan: TradePlan, trace_id: str, mode: ExecutionMode, equity: float
    ) -> OrderRecord:
        existing = self.storage.fetch_order_by_trace(trace_id)
        if existing:
            return self._record_from_row(existing)
        if mode == ExecutionMode.LIVE:
            self._enforce_canary(plan, equity)
        client_order_id = self._derive_client_order_id(trace_id, plan)
        record = OrderRecord(
            trace_id=trace_id,
            client_order_id=client_order_id,
            symbol=plan.symbol,
            side=plan.side,
            notional=plan.notional,
            mode=mode,
            state=OrderState.SUBMITTED,
        )
        self._persist(record)
        return record

    def transition(
        self, record: OrderRecord, state: OrderState, error: str | None = None
    ) -> OrderRecord:
        record.state = state
        record.last_error = error
        record.updated_ts = int(time.time())
        self._persist(record)
        return record

    def reconcile(self, *, stale_after_seconds: int = 900) -> ReconciliationResult:
        now = int(time.time())
        open_states = [
            OrderState.SUBMITTED.value,
            OrderState.ACKED.value,
            OrderState.PARTIALLY_FILLED.value,
        ]
        open_orders = self.storage.fetch_orders_by_state(open_states)
        mismatches: list[str] = []
        for row in open_orders:
            age = now - int(row.get("updated_ts", now))
            if age > stale_after_seconds:
                mismatches.append(row["client_order_id"])
        entered_safe_mode = bool(mismatches)
        return ReconciliationResult(mismatches=mismatches, entered_safe_mode=entered_safe_mode)

    def _persist(self, record: OrderRecord) -> None:
        self.storage.upsert_order(
            client_order_id=record.client_order_id,
            trace_id=record.trace_id,
            symbol=record.symbol,
            side=record.side,
            notional=record.notional,
            mode=record.mode,
            state=record.state.value,
            error=record.last_error,
            ts=record.updated_ts,
        )

    def _record_from_row(self, row: Mapping[str, object]) -> OrderRecord:
        return OrderRecord(
            trace_id=row.get("trace_id", "") or "",
            client_order_id=row["client_order_id"],
            symbol=row["symbol"],
            side=row["side"],
            notional=float(row["notional"]),
            mode=ExecutionMode(row["mode"]),
            state=OrderState(row["state"]),
            last_error=row.get("last_error") if isinstance(row, Mapping) else None,
            created_ts=int(row.get("created_ts", 0)),
            updated_ts=int(row.get("updated_ts", 0)),
        )

    def _enforce_canary(self, plan: TradePlan, equity: float) -> None:
        if not self.canary.enabled:
            raise RuntimeError("Live trading requires canary mode enabled")
        allowed = set(symbol.upper() for symbol in (self.canary.allowed_symbols or []))
        if allowed and plan.symbol.upper() not in allowed:
            raise RuntimeError("Plan symbol not permitted in canary mode")
        per_order_cap = equity * self.canary.per_order_notional_cap_pct
        if plan.notional > per_order_cap:
            raise RuntimeError("Canary per-order notional cap exceeded")
        window_start = int(time.time()) - 24 * 3600
        daily_orders = self.storage.count_orders_since(window_start, modes=[ExecutionMode.LIVE])
        if daily_orders >= self.canary.max_daily_orders:
            raise RuntimeError("Canary daily order budget exceeded")
        total_cap = equity * self.canary.total_notional_cap_pct
        # Treat open orders as part of total; conservative check using count * per order.
        if (daily_orders + 1) * plan.notional > total_cap:
            raise RuntimeError("Canary total notional cap exceeded")
