from trader.config.loader import build_constraints, load_profiles
from trader.schemas import OHLCV, AccountState, Action, MarketSnapshot, TraceContext
from trader.strategy.engine import StrategyContext, StrategyEngine
from trader.strategy.signals import SignalEngine


def sample_snapshot(symbol: str = "BTC") -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        timestamp=0,
        price=30000.0,
        spread_bps=8.0,
        atr=90.0,
        funding_rate=0.0,
        liquidity_score=0.8,
        ohlcv_1h=OHLCV(open=29500, high=30500, low=29400, close=30200, volume=10000),
        ohlcv_4h=OHLCV(open=29000, high=30800, low=28900, close=30400, volume=40000),
    )


def test_signal_engine_agreement_direction():
    engine = SignalEngine()
    features = engine.compute(sample_snapshot())
    assert engine.classify(features) == "bullish"
    assert features.agreement > 0


def test_strategy_engine_builds_plan_with_tp_sl():
    risk_profile, universe, _ = load_profiles({"UNIVERSE_PROFILE": "universe_v2"})
    constraints = build_constraints(risk_profile, universe, {})
    engine = StrategyEngine()
    snapshot = sample_snapshot("ETH")
    account = AccountState(equity=100000, positions=[], daily_pnl=0.0)
    trace = TraceContext(trace_id="test", run_id="run", provider_id=None, model_id=None)
    context = StrategyContext(
        snapshot=snapshot, account=account, constraints=constraints, trace=trace
    )
    plan = engine.draft_plan(context)
    assert plan.action in {Action.HOLD, Action.OPEN}
    if plan.action == Action.OPEN:
        assert plan.tp_sl is not None
        assert plan.tp_sl.stop_loss is not None
        assert plan.tp_sl.take_profit is not None
