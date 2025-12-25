# Runbook (Shadow / Phase 2)

## Start and Stop

1. Copy `.env.example` to `.env` and fill in Hyperliquid base URL and wallet (read-only). Do **not** enable live flags unless ready and approved.
2. For local execution: `python -m trader health`, `python -m trader hl:readonly`, or run a shadow loop: `python -m trader run --mode shadow --symbols BTC,ETH --iterations 1 --interval 60` (from `apps/trader/src` on `PYTHONPATH`).
3. For containers: `docker compose -f infra/docker-compose.yml up --build` to start the trader shadow loop (and optional Postgres). Default mode remains shadow/paper.
4. To stop containers: `docker compose -f infra/docker-compose.yml down`.

## Logs

- CLI commands print structured JSON payloads for read-only probes and shadow execution events.
- Docker users can view logs with `docker compose -f infra/docker-compose.yml logs -f trader`.
- All logs are JSON-formatted for downstream collection.

## Read-only Connectivity Check

- Ensure `HL_HYPERLIQUID_BASE_URL` is reachable from your network (default `https://api.hyperliquid.xyz`).
- Run `python -m trader hl:readonly -s BTC -s ETH` to fetch public endpoints; status `ok` indicates at least one payload responded.
- Shadow mode: `python -m trader run --mode shadow --symbols BTC,ETH --iterations 1 --risk-profile moderate_v1 --universe universe_v1` writes audit rows to the SQLite DB configured by `HL_DB_PATH`.
- No trading-side effects are triggered; live trading remains guarded behind `HL_LIVE_TRADING=true`, `LIVE_TRADING=true`, `HL_RISK_ACK=I_UNDERSTAND_LIVE_TRADING`, `HL_API_WALLET_CONFIGURED=true`, a `LIVE_ENABLE_TOKEN` (optionally validated against `LIVE_ENABLE_TOKEN_PATH`), and `LIVE_CANARY=true` using the versioned canary profile.

## Submodules

If submodules are missing, add them with your GitHub owner name:

```bash
git submodule add https://github.com/<GITHUB_OWNER>/hyperliquid-python-sdk-fork.git libs/hyperliquid/hyperliquid-python-sdk
git submodule add https://github.com/<GITHUB_OWNER>/nof1.ai-alpha-arena-upstream.git vendor/nof1.ai-alpha-arena
git submodule add https://github.com/<GITHUB_OWNER>/nof1-tracker-fork.git apps/tracker/upstream
```
