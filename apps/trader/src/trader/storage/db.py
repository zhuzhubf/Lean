"""Lightweight SQLite storage for audit records and order state."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from trader.schemas import ExecutionMode


@dataclass
class TraderStorage:
    db_path: Path

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_tables(self) -> None:
        conn = self._connect()
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS decisions (
                trace_id TEXT PRIMARY KEY,
                provider TEXT,
                model TEXT,
                raw_output TEXT,
                parsed_plan TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS risk_events (
                trace_id TEXT,
                decision TEXT,
                reasons TEXT,
                adjusted_plan TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS executions (
                trace_id TEXT,
                mode TEXT,
                status TEXT,
                result TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS pnl_snapshots (
                ts INTEGER,
                equity REAL,
                unrealized REAL,
                daily_pnl REAL,
                drawdown REAL
            );
            CREATE TABLE IF NOT EXISTS orders (
                client_order_id TEXT PRIMARY KEY,
                trace_id TEXT,
                symbol TEXT,
                side TEXT,
                notional REAL,
                mode TEXT,
                state TEXT,
                last_error TEXT,
                created_ts INTEGER,
                updated_ts INTEGER
            );
            CREATE TABLE IF NOT EXISTS live_events (
                ts INTEGER,
                actor TEXT,
                event TEXT,
                metadata TEXT
            );
            """
        )
        self._ensure_column(
            cur, "decisions", "model", "ALTER TABLE decisions ADD COLUMN model TEXT"
        )
        conn.commit()
        conn.close()

    def _ensure_column(self, cur: sqlite3.Cursor, table: str, column: str, alter_sql: str) -> None:
        cur.execute(f"PRAGMA table_info({table})")
        columns = {row[1] for row in cur.fetchall()}
        if column not in columns:
            cur.execute(alter_sql)

    def record_decision(
        self,
        trace_id: str,
        provider: str,
        model: str | None,
        raw_output: Mapping[str, Any],
        parsed_plan: Mapping[str, Any],
        created_at: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                (
                    "INSERT OR REPLACE INTO decisions(trace_id, provider, model, raw_output, "
                    "parsed_plan, created_at) VALUES (?,?,?,?,?,?)"
                ),
                (
                    trace_id,
                    provider,
                    model,
                    json.dumps(raw_output),
                    json.dumps(parsed_plan),
                    created_at,
                ),
            )

    def record_risk(
        self,
        trace_id: str,
        decision: str,
        reasons: list[str],
        adjusted_plan: Mapping[str, Any] | None,
        created_at: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                (
                    "INSERT INTO risk_events(trace_id, decision, reasons, adjusted_plan, "
                    "created_at) VALUES (?,?,?,?,?)"
                ),
                (
                    trace_id,
                    decision,
                    json.dumps(reasons),
                    json.dumps(adjusted_plan) if adjusted_plan else None,
                    created_at,
                ),
            )

    def record_execution(
        self,
        trace_id: str,
        mode: ExecutionMode,
        status: str,
        result: Mapping[str, Any],
        created_at: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                (
                    "INSERT INTO executions(trace_id, mode, status, result, created_at) "
                    "VALUES (?,?,?,?,?)"
                ),
                (trace_id, mode.value, status, json.dumps(result), created_at),
            )

    def upsert_order(
        self,
        client_order_id: str,
        trace_id: str,
        symbol: str,
        side: str,
        notional: float,
        mode: ExecutionMode,
        state: str,
        error: str | None,
        ts: int | None = None,
    ) -> None:
        now = ts or int(time.time())
        with self._connect() as conn:
            conn.execute(
                (
                    "INSERT INTO orders(client_order_id, trace_id, symbol, side, notional, "
                    "mode, state, last_error, created_ts, updated_ts) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(client_order_id) DO UPDATE SET "
                    "state=excluded.state, last_error=excluded.last_error, updated_ts=excluded.updated_ts"
                ),
                (
                    client_order_id,
                    trace_id,
                    symbol,
                    side,
                    notional,
                    mode.value,
                    state,
                    error,
                    now,
                    now,
                ),
            )

    def fetch_order_by_trace(self, trace_id: str) -> Mapping[str, Any] | None:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT client_order_id, trace_id, symbol, side, notional, mode, state, last_error, created_ts, updated_ts "
                "FROM orders WHERE trace_id=?",
                (trace_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            keys = [
                "client_order_id",
                "trace_id",
                "symbol",
                "side",
                "notional",
                "mode",
                "state",
                "last_error",
                "created_ts",
                "updated_ts",
            ]
            return dict(zip(keys, row))

    def fetch_orders_by_state(self, states: Sequence[str]) -> list[Mapping[str, Any]]:
        placeholders = ",".join("?" for _ in states)
        with self._connect() as conn:
            cur = conn.execute(
                f"SELECT client_order_id, trace_id, symbol, state, created_ts, updated_ts FROM orders WHERE state IN ({placeholders})",
                tuple(states),
            )
            rows = cur.fetchall()
            keys = ["client_order_id", "trace_id", "symbol", "state", "created_ts", "updated_ts"]
            return [dict(zip(keys, row)) for row in rows]

    def record_live_event(
        self, actor: str, event: str, metadata: Mapping[str, Any] | None = None
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO live_events(ts, actor, event, metadata) VALUES (?,?,?,?)",
                (int(time.time()), actor, event, json.dumps(metadata or {})),
            )

    def count_orders_since(self, ts_threshold: int, *, modes: Iterable[ExecutionMode]) -> int:
        placeholders = ",".join("?" for _ in modes)
        with self._connect() as conn:
            cur = conn.execute(
                f"SELECT COUNT(*) FROM orders WHERE created_ts>=? AND mode IN ({placeholders})",
                (ts_threshold, *[mode.value for mode in modes]),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def record_pnl_snapshot(
        self, ts: int, equity: float, unrealized: float, daily_pnl: float, drawdown: float
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                (
                    "INSERT INTO pnl_snapshots(ts, equity, unrealized, daily_pnl, drawdown) "
                    "VALUES (?,?,?,?,?)"
                ),
                (ts, equity, unrealized, daily_pnl, drawdown),
            )

    def status(self) -> Mapping[str, Any]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM decisions")
            decisions = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM executions")
            executions = cur.fetchone()[0]
            cur.execute("SELECT decision, COUNT(*) FROM risk_events GROUP BY decision")
            risk_rows = {row[0]: row[1] for row in cur.fetchall()}
            cur.execute(
                "SELECT trace_id, created_at FROM decisions ORDER BY created_at DESC LIMIT 1"
            )
            last = cur.fetchone()
            return {
                "decisions": decisions,
                "executions": executions,
                "risk_breakdown": risk_rows,
                "last_trace_id": last[0] if last else None,
                "last_created_at": last[1] if last else None,
            }
