# Hyperliquid Swing Bot Monorepo (Bootstrap)

Production-ready scaffold for a Hyperliquid swing trading system (1–4h cadence, BTC/ETH + configurable alt whitelist). Phase 2 introduces schema-first contracts, hard Risk Gateway, pluggable decision providers (LLM + rule-based), shadow execution, and structured audit logging while live trading remains disabled by default.

## Goals

- Monorepo layout with clear boundaries for trader, tracker, shared libraries, and infra.
- Upstream references via forks/submodules (Hyperliquid SDK, strategy research, tracker).
- Strict safety defaults: no secrets in git, live trading hard-gated, and provenance preserved.

## Architecture (planned)

See `docs/ARCHITECTURE.md` for the layered view. Current trader features:

- Schema-first `TradePlan`/`RiskDecision` contracts (Pydantic v2)
- Decision Engine with OpenAI-compatible, xAI-compatible, and rule-based providers
- Hard Risk Gateway enforcing whitelist, leverage caps, risk budget, exposure limits, spread guards, cooldowns, and daily loss circuit breaker
- Shadow execution loop with audit trail persisted to SQLite
- Structured JSON logging for decisions, risk outcomes, and executions
- Versioned risk/universe configs stored under `apps/trader/config/risk_profiles/` and `apps/trader/config/universe/` (default `moderate_v1` + `universe_v1`)

## Safety Principles

- **API Wallet & least privilege:** use read-only or paper credentials; never commit keys.
- **No binary releases:** consume upstream via source submodules only.
- **Live trading off by default:** requires both `HL_LIVE_TRADING=true` and `HL_RISK_ACK=I_UNDERSTAND` before any execution adapters are allowed.
- **Auditability:** keep submodules pointing to forks to retain LICENSE and history.

## Repository Layout

```
apps/
  trader/                # Python package with CLI: health, hl:readonly, run (shadow loop)
  tracker/upstream/      # Placeholder for nof1-tracker fork (submodule recommended)
libs/
  hyperliquid/           # Hyperliquid SDK fork submodule goes here
vendor/
  nof1.ai-alpha-arena/   # Strategy reference fork (read-only)
infra/                   # Docker Compose, deployment helpers
docs/                    # Architecture and runbook
```

## Quickstart (local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r apps/trader/requirements.txt -r requirements-dev.txt
PYTHONPATH=apps/trader/src python -m trader health
PYTHONPATH=apps/trader/src python -m trader hl:readonly -s BTC -s ETH
PYTHONPATH=apps/trader/src python -m trader run --mode shadow --symbols BTC,ETH --iterations 1 --interval 1
```

Select risk/universe versions via `RISK_PROFILE`/`UNIVERSE_PROFILE` (default: `moderate_v1`/`universe_v1`). Add new versions instead of editing existing YAMLs to keep audit trails and enable rollbacks.

### LLM providers

- Default: OpenAI-compatible GPT-5.2 (`LLM_PROVIDER=openai`, `OPENAI_MODEL=gpt-5.2`).
- Required env for default path: `OPENAI_API_KEY`, optional `OPENAI_BASE_URL`, `OPENAI_TIMEOUT_SEC`, `OPENAI_MAX_RETRIES`.
- Optional fallback provider: set `LLM_PROVIDER=xai` with `XAI_API_KEY`/`XAI_BASE_URL` or omit keys to automatically fall back to the built-in rule-based provider.

## Docker

```bash
docker compose -f infra/docker-compose.yml up --build
# tail logs
docker compose -f infra/docker-compose.yml logs -f trader
```

## Submodules (forks)

Add forks under your GitHub account before running CI:

```bash
git submodule add https://github.com/<GITHUB_OWNER>/hyperliquid-python-sdk-fork.git libs/hyperliquid/hyperliquid-python-sdk
git submodule add https://github.com/<GITHUB_OWNER>/nof1.ai-alpha-arena-upstream.git vendor/nof1.ai-alpha-arena
git submodule add https://github.com/<GITHUB_OWNER>/nof1-tracker-fork.git apps/tracker/upstream
```

## CI

`.github/workflows/ci.yml` runs ruff, black, and pytest against the trader package. Ensure submodules are present for full coverage. CI does not enable live trading.

## Contributing

See `CONTRIBUTING.hyperliquid.md` for branching, commit, and safety guidelines specific to this bootstrap.
