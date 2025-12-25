# Universe configuration

Universe files enumerate tradable symbols and their classifications. Filenames follow the `<name>_v<integer>.yaml` pattern. Do not change existing versions in-place; add new versions for any material edits so rollbacks can re-point to the prior file.

## Required fields
- `version`: integer version of this universe file.
- `majors`: list of major symbols (must include BTC and ETH).
- `alts`: list of alt symbols (can be empty but must be present).
- `whitelist`: combined list of allowed symbols (should match majors + alts).
- `symbol_metadata`: optional map for future per-symbol settings (e.g., tick size).

## Change control
- Add new versions for whitelist/risk-weight changes.
- Keep prior versions intact for audit/rollback.
- Document version intent and activation in `docs/risk-profiles.md`.
