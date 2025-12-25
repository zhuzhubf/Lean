"""Hard rule risk gateway implementation driven by versioned configs."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict

from trader.schemas import (
    AccountState,
    Action,
    MarketSnapshot,
    OrderType,
    PortfolioConstraints,
    RiskDecision,
    RiskDecisionType,
    TradePlan,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class FrequencyState:
    last_open_timestamp: float | None = None
    last_side: str | None = None


@dataclass
class RiskGateway:
    """Risk gateway implementing hard rules."""

    constraints: PortfolioConstraints
    frequency_state: Dict[str, FrequencyState] = field(default_factory=dict)

    def evaluate(
        self, plan: TradePlan, snapshot: MarketSnapshot, account: AccountState
    ) -> RiskDecision:
        reasons: list[str] = []
        symbol = snapshot.symbol.upper()

        if plan.action == Action.HOLD:
            return RiskDecision(decision=RiskDecisionType.ALLOW, reasons=["hold"])

        if symbol not in {sym.upper() for sym in self.constraints.whitelist}:
            return RiskDecision(
                decision=RiskDecisionType.REJECT,
                reasons=["symbol_not_whitelisted"],
            )

        asset_class = self.constraints.asset_class_for_symbol(symbol)
        if asset_class is None:
            return RiskDecision(decision=RiskDecisionType.REJECT, reasons=["unknown_asset_class"])

        if account.daily_pnl <= -account.equity * self.constraints.daily_loss_limit_fraction:
            if plan.action == Action.OPEN:
                return RiskDecision(
                    decision=RiskDecisionType.REJECT,
                    reasons=["daily_loss_circuit_breaker"],
                )
            reasons.append("circuit_breaker_active")

        if plan.order_type == OrderType.MARKET and (
            snapshot.spread_bps > self.constraints.max_spread_bps
            or (
                snapshot.atr
                and snapshot.atr > 0
                and snapshot.atr * self.constraints.volatility_guard_atr_mult
                < abs(snapshot.price - snapshot.ohlcv_1h.close)
            )
        ):
            return RiskDecision(
                decision=RiskDecisionType.REJECT,
                reasons=["spread_too_high"],
            )

        adjusted = plan
        max_leverage = self.constraints.max_leverage_for_symbol(symbol)
        if plan.leverage and plan.leverage > max_leverage:
            adjusted = adjusted.model_copy(update={"leverage": max_leverage})
            reasons.append("leverage_capped")

        if plan.tp_sl is None or plan.tp_sl.stop_loss is None:
            return RiskDecision(decision=RiskDecisionType.REJECT, reasons=["missing_stop_loss"])

        entry_price = plan.limit_price or snapshot.price
        stop_loss = plan.tp_sl.stop_loss
        if stop_loss <= 0 or entry_price <= 0 or stop_loss == entry_price:
            return RiskDecision(decision=RiskDecisionType.REJECT, reasons=["invalid_stop_loss"])

        # Risk budget sizing
        requested_notional = adjusted.notional
        if requested_notional is None and adjusted.size is not None:
            requested_notional = adjusted.size * entry_price
        if requested_notional is None:
            return RiskDecision(decision=RiskDecisionType.REJECT, reasons=["missing_notional"])

        allowed_loss = account.equity * self.constraints.single_trade_risk_fraction
        sl_distance = abs(entry_price - stop_loss)
        allowed_notional = allowed_loss * entry_price / sl_distance
        if requested_notional > allowed_notional:
            adjusted = adjusted.model_copy(update={"notional": allowed_notional})
            reasons.append("risk_budget_scaled")

        # Exposure checks
        current_symbol_exposure = self._symbol_exposure(symbol, account, snapshot)
        projected_symbol_exposure = current_symbol_exposure + (adjusted.notional or 0)
        symbol_cap_fraction = self.constraints.per_symbol_cap_fraction(symbol)
        symbol_cap = account.equity * symbol_cap_fraction
        if projected_symbol_exposure > symbol_cap:
            scaled_notional = max(symbol_cap - current_symbol_exposure, 0)
            if scaled_notional <= 0:
                return RiskDecision(
                    decision=RiskDecisionType.REJECT, reasons=["symbol_exposure_cap"]
                )
            adjusted = adjusted.model_copy(update={"notional": scaled_notional})
            reasons.append("symbol_exposure_scaled")

        total_exposure = self._total_exposure(account, snapshot)
        projected_total = total_exposure + (adjusted.notional or 0)
        total_cap = account.equity * self.constraints.total_exposure_fraction
        if projected_total > total_cap:
            scaled_notional = max(total_cap - total_exposure, 0)
            if scaled_notional <= 0:
                return RiskDecision(
                    decision=RiskDecisionType.REJECT, reasons=["total_exposure_cap"]
                )
            adjusted = adjusted.model_copy(update={"notional": scaled_notional})
            reasons.append("total_exposure_scaled")

        class_cap_fraction = self.constraints.class_cap_fraction(asset_class)
        if class_cap_fraction:
            class_exposure = self._class_exposure(asset_class, account, snapshot)
            projected_class = class_exposure + (adjusted.notional or 0)
            class_cap = account.equity * class_cap_fraction
            if projected_class > class_cap:
                scaled_notional = max(class_cap - class_exposure, 0)
                if scaled_notional <= 0:
                    return RiskDecision(
                        decision=RiskDecisionType.REJECT, reasons=["class_exposure_cap"]
                    )
                adjusted = adjusted.model_copy(update={"notional": scaled_notional})
                reasons.append("class_exposure_scaled")

        freq_state = self.frequency_state.get(symbol, FrequencyState())
        now = time.time()
        if plan.action == Action.OPEN:
            if (
                freq_state.last_open_timestamp
                and now - freq_state.last_open_timestamp
                < self.constraints.open_cooldown_for_symbol(symbol)
            ):
                return RiskDecision(decision=RiskDecisionType.REJECT, reasons=["frequency_limit"])
            freq_state.last_open_timestamp = now
            freq_state.last_side = plan.side.value if plan.side else None
            self.frequency_state[symbol] = freq_state
        elif plan.action == Action.REDUCE and freq_state.last_side:
            if now - (
                freq_state.last_open_timestamp or 0
            ) < self.constraints.add_cooldown_for_symbol(symbol):
                reasons.append("add_cooldown_active")

        return RiskDecision(
            decision=RiskDecisionType.ALLOW, reasons=reasons, adjusted_plan=adjusted
        )

    def _symbol_exposure(
        self, symbol: str, account: AccountState, snapshot: MarketSnapshot
    ) -> float:
        price = snapshot.price
        exposure = 0.0
        for position in account.positions:
            if position.symbol.upper() != symbol.upper():
                continue
            exposure += abs(position.size * price)
        return exposure

    def _total_exposure(self, account: AccountState, snapshot: MarketSnapshot) -> float:
        price = snapshot.price
        exposure = 0.0
        for position in account.positions:
            exposure += abs(position.size * price)
        return exposure

    def _class_exposure(
        self, classification: str, account: AccountState, snapshot: MarketSnapshot
    ) -> float:
        price = snapshot.price
        exposure = 0.0
        for position in account.positions:
            if self.constraints.asset_class_for_symbol(position.symbol) != classification:
                continue
            exposure += abs(position.size * price)
        return exposure
