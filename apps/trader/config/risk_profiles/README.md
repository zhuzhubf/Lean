# Risk profiles

Versioned risk profiles are YAML files named `<profile>_v<integer>.yaml` and must never be modified in-place once merged. Introduce new versions (e.g., `moderate_v2.yaml`) for any material risk changes and switch defaults explicitly so rollbacks can return to the previous version.

## Required fields
- `profile_name`: descriptive name (e.g., `moderate`).
- `version`: integer version.
- `defaults.decision_interval_sec`: schedule cadence in seconds.
- `defaults.timeframe`: descriptive trading horizon.
- `asset_classes.majors` and `.alts`: weights, leverage caps, per-symbol and class exposure caps, and cooldowns.
- `portfolio_limits.total_max_notional_pct`: overall portfolio exposure cap (0-1 fraction of equity).
- `portfolio_limits.per_symbol_max_notional_pct_override`: optional symbol overrides (fractions of equity).
- `risk_budget.per_trade_max_loss_pct`: per-trade loss budget (fraction of equity).
- `risk_budget.daily_loss_limit_pct_default`: default daily loss circuit breaker (fraction of equity).
- `risk_budget.daily_loss_limit_pct_cap`: maximum allowed override (fraction of equity).
- `market_protections.max_spread_bps`: maximum allowed spread for market orders.
- `market_protections.volatility_guard_atr_mult`: ATR multiple guardrail.
- `market_protections.forbid_market_orders_when_guarded`: whether to block market orders under guards.

## Change control
- New risk posture → add a new file with bumped version.
- Update defaults by adding a new version; do not edit older files.
- Document all version introductions in `docs/risk-profiles.md`.
- Default selection is controlled via environment/config and can be rolled back by pointing back to the prior version.
