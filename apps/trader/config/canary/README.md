# Canary profiles

Versioned constraints for live canary rollouts. Files follow `<name>_vN.yaml` naming and must never be overwritten in place—add new versions for riskier changes.

Fields:
- `allowed_symbols`: whitelist for canary live trades.
- `max_daily_orders`: budget of orders per 24h window.
- `per_order_notional_cap_pct`: cap per order as a fraction of equity.
- `total_notional_cap_pct`: total open/counted notional cap over the same window.

Default profile: `canary_v1` (majors-only, small budgets).
