import json

from trader.decision.providers.openai_compat import OpenAICompatProvider
from trader.decision.providers.rule_based import RuleBasedProvider
from trader.decision.router import ProviderRouter
from trader.schemas import (
    OHLCV,
    AccountState,
    Action,
    MarketSnapshot,
    PortfolioConstraints,
    TraceContext,
    TradePlan,
)


def _snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="BTC",
        timestamp=1,
        price=10_000,
        spread_bps=5.0,
        atr=25,
        ohlcv_1h=OHLCV(open=9_900, high=10_050, low=9_850, close=10_000, volume=1000),
        ohlcv_4h=OHLCV(open=9_800, high=10_100, low=9_750, close=10_020, volume=4000),
    )


def _account() -> AccountState:
    return AccountState(equity=100_000.0, positions=[], daily_pnl=0.0)


def test_rule_based_returns_trade_plan():
    provider = RuleBasedProvider()
    plan = provider.propose_plan(
        _snapshot(), _account(), PortfolioConstraints(), TraceContext(trace_id="t")
    )
    assert isinstance(plan, TradePlan)
    assert plan.action in {Action.OPEN, Action.HOLD}


def test_openai_provider_validates_json_schema():
    def fake_chat(prompt: str) -> str:
        payload = json.loads(prompt)
        return json.dumps(
            {
                "action": "OPEN",
                "symbol": payload["context"]["symbol"],
                "side": "LONG",
                "order_type": "LIMIT",
                "limit_price": 10_000,
                "notional": 1_000,
                "tp_sl": {"stop_loss": 9_800},
            }
        )

    provider = OpenAICompatProvider(chat_caller=fake_chat)
    plan = provider.propose_plan(
        _snapshot(), _account(), PortfolioConstraints(), TraceContext(trace_id="t2")
    )
    assert plan.action == Action.OPEN
    assert plan.symbol == "BTC"


def test_provider_router_falls_back_on_error():
    def broken_chat(_: str) -> str:
        raise RuntimeError("boom")

    router = ProviderRouter(
        provider_name="openai",
        openai_factory=lambda: OpenAICompatProvider(chat_caller=broken_chat),
    )
    plan = router.propose_plan(
        _snapshot(), _account(), PortfolioConstraints(), TraceContext(trace_id="trace")
    )
    assert plan.action == Action.HOLD
