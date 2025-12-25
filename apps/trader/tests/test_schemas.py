import pytest

from trader.schemas import Action, OrderType, PortfolioConstraints, TradePlan


def test_trade_plan_requires_side_for_open():
    with pytest.raises(ValueError):
        TradePlan(
            action=Action.OPEN,
            symbol="BTC",
            order_type=OrderType.LIMIT,
            limit_price=1.0,
            notional=100,
        )


def test_trade_plan_requires_notional_or_size():
    with pytest.raises(ValueError):
        TradePlan(
            action=Action.REDUCE,
            symbol="ETH",
            side="LONG",
            order_type=OrderType.LIMIT,
            limit_price=1.0,
        )


def test_trade_plan_market_disallows_limit_price():
    with pytest.raises(ValueError):
        TradePlan(
            action=Action.OPEN,
            symbol="ETH",
            side="LONG",
            order_type=OrderType.MARKET,
            limit_price=10,
            notional=50,
        )


def test_constraints_leverage_caps():
    constraints = PortfolioConstraints(
        class_membership={"BTC": "majors", "ALT": "alts"},
        leverage_limit={"majors": 5, "alts": 3},
        per_symbol_exposure_fraction_default={"majors": 0.3, "alts": 0.15},
        class_exposure_fraction={"majors": 0.6, "alts": 0.3},
    )
    assert constraints.max_leverage_for_symbol("BTC") == 5
    assert constraints.max_leverage_for_symbol("ALT") == 3
