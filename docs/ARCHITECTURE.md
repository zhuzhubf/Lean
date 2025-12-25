# Architecture Overview (Phase 1 Bootstrap)

```
+-------------------+      +------------------+      +------------------+
| Decision Engine   | ---> | Risk Gateway     | ---> | Execution Layer  |
| (planned)         |      | (planned)        |      | (shadow only)    |
+-------------------+      +------------------+      +------------------+
         |                          |                          |
         v                          v                          v
   Market Snapshot           Audit & Metrics             Hyperliquid SDK
   Account State             (structured logs)      (submodule placeholder)
```

- **Decision Engine:** Reserved for future LLM adapters. Phase 1 only includes CLI utilities.
- **Risk Gateway:** To be added in later phases; live trading remains disabled via environment gates.
- **Execution Layer:** Uses Hyperliquid Python SDK via submodule (fork). Only read-only probes run today.

## Monorepo Layout

- `apps/trader`: Python package with `trader` CLI (health/read-only probes) and Dockerfile.
- `apps/tracker/upstream`: Placeholder for `nof1-tracker` fork submodule.
- `libs/hyperliquid/hyperliquid-python-sdk`: Placeholder for Hyperliquid SDK fork submodule.
- `vendor/nof1.ai-alpha-arena`: Placeholder for upstream strategy reference.
- `infra`: Docker Compose and deployment scripts.
- `docs`: Architecture notes and runbook.

## Security and Safety

- No secrets committed; use environment variables (`.env` for local, env vars in production).
- Live trading requires both `HL_LIVE_TRADING=true` **and** `HL_RISK_ACK=I_UNDERSTAND`; execution adapters remain stubbed.
- Upstream code is referenced via forks/submodules to preserve provenance and licenses.
