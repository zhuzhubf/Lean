import pytest

from trader.config.loader import build_constraints, load_profiles


def test_load_profiles_defaults():
    risk, universe, canary = load_profiles({})
    assert risk.profile_name == "moderate"
    assert universe.version == 2
    assert canary.version == 1
    assert "BTC" in universe.whitelist and "ETH" in universe.whitelist


def test_build_constraints_respects_caps():
    risk, universe, _ = load_profiles({})
    constraints = build_constraints(risk, universe, {"DAILY_LOSS_LIMIT_PCT": "0.10"})
    assert constraints.max_leverage_for_symbol("BTC") == pytest.approx(5)
    assert constraints.max_leverage_for_symbol("SOL") == pytest.approx(3)
    assert constraints.total_exposure_fraction == pytest.approx(0.80)


def test_override_cap_enforced():
    risk, universe, _ = load_profiles({})
    with pytest.raises(RuntimeError):
        build_constraints(risk, universe, {"DAILY_LOSS_LIMIT_PCT": "0.50"})


def test_overrides_cannot_raise_exposure():
    risk, universe, _ = load_profiles({})
    with pytest.raises(RuntimeError):
        build_constraints(risk, universe, {"TOTAL_MAX_NOTIONAL_PCT": "0.90"})
