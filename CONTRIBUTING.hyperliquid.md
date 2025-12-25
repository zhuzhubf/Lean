# Contributing (Hyperliquid Bootstrap)

## Branching and Commits
- Default branch: `main`.
- Prefer feature branches (`feature/<short-description>`) and small PRs.
- Use conventional commit-style messages when possible (e.g., `chore: add ci`).

## Safety and Compliance
- Never commit secrets; use `.env` locally and environment variables in CI/production.
- Hyperliquid live trading must remain off unless both `HL_LIVE_TRADING=true` and `HL_RISK_ACK=I_UNDERSTAND` are set.
- Do not run or vendor binary releases; pull source via forks/submodules and keep upstream LICENSE files intact.

## Submodules
- Fork required upstreams into your GitHub account, then add as submodules:
  - `libs/hyperliquid/hyperliquid-python-sdk`
  - `vendor/nof1.ai-alpha-arena`
  - `apps/tracker/upstream`
- Run `git submodule update --init --recursive` after cloning.

## Tooling
- Python 3.11+.
- Lint/format: `ruff check apps/trader` and `black apps/trader`.
- Tests: `PYTHONPATH=apps/trader/src pytest`.

## Code Style
- Follow PEP8 and include type annotations for new functions.
- Keep new modules small and focused; prefer dependency injection for networked components.
