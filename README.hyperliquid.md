# Hyperliquid Swing Bot Monorepo (Bootstrap)

> **Status:** Phase 1 scaffold. Read-only connectivity and health checks only; no live trading.

## Goals
- Provide a production-ready starting point for a Hyperliquid automated trader targeting 1–4h swing horizons across BTC/ETH plus an altcoin whitelist.
- Keep upstream provenance via forks/submodules (Hyperliquid SDK, strategy reference, tracker).
- Enforce safety by default: secrets stay out of git, live trading is gated, and binary releases are avoided.

## Repository Layout

```
/apps
  trader/        -> Python CLI: health, hl:readonly, live guard
  tracker/       -> Placeholder for replay/analytics submodule
/libs
  hyperliquid/   -> Slot for Hyperliquid SDK fork
/vendor
  nof1.ai-alpha-arena -> Strategy reference fork (read-only)
/docs            -> Architecture notes and runbook
/infra           -> Docker and deployment assets
```

Upstream references (fork under your GitHub account):

- `nof1-ai-alpha-arena/nof1.ai-alpha-arena`
- `hyperliquid-dex/hyperliquid-python-sdk`
- `Dixter999/nof1-tracker`

## Safety & Compliance
- **Shadow-first:** Live trading requires both `HL_LIVE_TRADING=true` and `HL_RISK_ACK=I_UNDERSTAND`, plus future execution adapters.
- **Least privilege:** Prefer Hyperliquid Agent/Wallet keys with minimal scopes; never commit secrets.
- **Source only:** Do not run upstream binary releases; consume source via submodules.

## Quickstart (local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r apps/trader/requirements.txt -r requirements-dev.txt
PYTHONPATH=apps/trader/src python -m trader health
PYTHONPATH=apps/trader/src python -m trader hl:readonly -s BTC -s ETH
```

## Docker Compose

`infra/docker-compose.yml` builds the trader image in read-only mode and optionally starts PostgreSQL for future tracker work. Supply environment variables via `.env`.

## CI

`.github/workflows/ci.yml` runs ruff, black, pytest, and a docker build against the trader app. Extend as submodules are added.
