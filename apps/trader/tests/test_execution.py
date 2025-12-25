from trader.execution.executor import ExecutionMode, Executor
from trader.schemas import OHLCV, Action, MarketSnapshot, RiskDecision, RiskDecisionType, TradePlan


def _plan() -> TradePlan:
    return TradePlan(
        action=Action.OPEN,
        symbol="BTC",
        side="LONG",
        leverage=3.0,
        notional=1000.0,
        order_type="LIMIT",
        limit_price=10_000,
        tp_sl={"stop_loss": 9_800},
    )


def _snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="BTC",
        timestamp=1,
        price=10_000,
        spread_bps=5.0,
        atr=20,
        ohlcv_1h=OHLCV(open=9_900, high=10_100, low=9_800, close=10_000, volume=1000),
        ohlcv_4h=OHLCV(open=9_800, high=10_200, low=9_700, close=10_050, volume=4000),
    )


def test_shadow_execution_records_fill():
    executor = Executor()
    decision = RiskDecision(decision=RiskDecisionType.ALLOW, reasons=[])
    result = executor.execute(_plan(), decision, _snapshot(), ExecutionMode.SHADOW)
    assert result.mode == ExecutionMode.SHADOW
    assert result.status == "filled"
    assert result.price == 10_000
