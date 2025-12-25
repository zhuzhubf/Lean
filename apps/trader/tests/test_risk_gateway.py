import time

from trader.config.loader import build_constraints, load_profiles
from trader.risk.gateway import RiskGateway
from trader.schemas import (
    OHLCV,
    AccountState,
    Action,
    MarketSnapshot,
    OrderType,
    Position,
    RiskDecisionType,
    Side,
    TakeProfitStopLoss,
    TradePlan,
)


def _constraints():
    risk, universe, _ = load_profiles({})
    return build_constraints(risk, universe, {})


def _snapshot(symbol: str, price: float = 20000.0) -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        timestamp=int(time.time()),
        price=price,
        spread_bps=5.0,
        atr=price * 0.002,
        funding_rate=0.0,
        liquidity_score=0.9,
        ohlcv_1h=OHLCV(
            open=price * 0.99,
            high=price * 1.01,
            low=price * 0.98,
            close=price,
            volume=1000,
        ),
        ohlcv_4h=OHLCV(
            open=price * 0.98,
            high=price * 1.02,
            low=price * 0.97,
            close=price * 1.001,
            volume=5000,
        ),
    )


def _account(
    equity: float = 100000.0, positions: list[Position] | None = None, daily_pnl: float = 0.0
) -> AccountState:
    return AccountState(equity=equity, positions=positions or [], daily_pnl=daily_pnl)


def _plan(
    symbol: str, price: float = 20000.0, notional: float = 1000.0, leverage: float = 5.0
) -> TradePlan:
    return TradePlan(
        action=Action.OPEN,
        symbol=symbol,
        side=Side.LONG,
        leverage=leverage,
        notional=notional,
        order_type=OrderType.LIMIT,
        limit_price=price,
        tp_sl=TakeProfitStopLoss(stop_loss=price * 0.99),
    )


def test_rejects_non_whitelisted_symbol():
    gateway = RiskGateway(_constraints())
    decision = gateway.evaluate(_plan("XRP"), _snapshot("XRP"), _account())
    assert decision.decision == RiskDecisionType.REJECT
    assert "symbol_not_whitelisted" in decision.reasons


def test_leverage_capped_and_risk_budget_scaled():
    constraints = _constraints().model_copy(update={"single_trade_risk_fraction": 0.01})
    gateway = RiskGateway(constraints)
    plan = _plan("BTC", leverage=10.0, notional=1_000_000.0)
    decision = gateway.evaluate(
        plan, _snapshot("BTC", price=20_000), _account(equity=100_000)
    )
    assert decision.decision == RiskDecisionType.ALLOW
    assert decision.adjusted_plan is not None
    assert (
        decision.adjusted_plan.leverage
        <= gateway.constraints.max_leverage_for_symbol("BTC")
    )
    assert "leverage_capped" in decision.reasons
    assert "risk_budget_scaled" in decision.reasons


def test_daily_loss_circuit_breaker_blocks_open():
    gateway = RiskGateway(_constraints().model_copy(update={"daily_loss_limit_fraction": 0.1}))
    decision = gateway.evaluate(
        _plan("BTC"), _snapshot("BTC"), _account(daily_pnl=-15_000, equity=100_000)
    )
    assert decision.decision == RiskDecisionType.REJECT
    assert "daily_loss_circuit_breaker" in decision.reasons


def test_frequency_limit_rejects_repeated_open():
    constraints = _constraints().model_copy(
        update={"open_cooldown_seconds": {"majors": 10, "alts": 10}}
    )
    gateway = RiskGateway(constraints)
    plan = _plan("BTC")
    snapshot = _snapshot("BTC")
    account = _account()
    first = gateway.evaluate(plan, snapshot, account)
    assert first.decision == RiskDecisionType.ALLOW
    second = gateway.evaluate(plan, snapshot, account)
    assert second.decision == RiskDecisionType.REJECT
    assert "frequency_limit" in second.reasons


def test_spread_protection_rejects_market_order():
    gateway = RiskGateway(_constraints().model_copy(update={"max_spread_bps": 1.0}))
    snapshot = _snapshot("BTC")
    plan = _plan("BTC").model_copy(update={"order_type": OrderType.MARKET})
    decision = gateway.evaluate(plan, snapshot.model_copy(update={"spread_bps": 2.0}), _account())
    assert decision.decision == RiskDecisionType.REJECT
    assert "spread_too_high" in decision.reasons
