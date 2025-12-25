# Versioned risk profiles

Risk settings are externalized into versioned YAML files under `apps/trader/config/risk_profiles/` and `apps/trader/config/universe/`. Files follow `<name>_v<integer>.yaml`. Never modify an existing version once merged; add a new version file and switch defaults explicitly to allow auditability and rollbacks. Canary live guardrails live in `apps/trader/config/canary/` with the same naming discipline.

## Governance
- Propose changes via PR that adds a new profile version (e.g., `moderate_v2.yaml`).
- Update defaults by changing `RISK_PROFILE`/`UNIVERSE_PROFILE` env or CLI flags; keep older versions intact for rollback.
- Document intent and risk of each new version in this file.
- To roll back, point `RISK_PROFILE` back to a previous version (e.g., `moderate_v1`).

## Fields
See `apps/trader/config/risk_profiles/README.md` and `apps/trader/config/universe/README.md` for field-level definitions. Key controls include leverage caps, per-symbol/class and total exposure limits, cooldowns, per-trade loss budgets, and spread/volatility guards. BTC/ETH reside in `majors`; all others should be listed under `alts` with lower weight and leverage limits.

## Activation checklist
1. Validate config locally with `pytest apps/trader/tests/test_config_loader.py`.
2. Run shadow mode at least 24–48h using the target profile: `PYTHONPATH=apps/trader/src python -m trader run --mode shadow --risk-profile moderate_v1 --universe universe_v2`.
3. Confirm `trader status` reports the intended profile/version and thresholds.
4. Keep live trading disabled unless multi-step approvals are satisfied.
5. Environment overrides must only tighten limits (never raise exposure or loss caps); attempts to increase risk fail-fast.
