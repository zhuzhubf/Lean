"""Command-line interface for the trader bootstrap."""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Sequence

from .config import AppConfig, load_config
from .execution.executor import ExecutionMode
from .execution.order_manager import CanaryConstraints
from .health import perform_health_check
from .orchestrator import run_loop
from .readonly import enforce_live_trading_enabled, perform_readonly_check

LOGGER = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hyperliquid trader bootstrap CLI")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("health", help="Run basic health checks")

    readonly_parser = subparsers.add_parser(
        "hl:readonly", help="Probe Hyperliquid read-only endpoints for connectivity"
    )
    readonly_parser.add_argument(
        "--symbol",
        "-s",
        action="append",
        dest="symbols",
        help="Symbol to include in the connectivity check (repeatable)",
    )

    subparsers.add_parser("live:guard", help="Demonstrate live trading guardrails")
    subparsers.add_parser("status", help="Summarize recent decisions/executions")
    run_parser = subparsers.add_parser("run", help="Execute decision -> risk -> shadow loop")
    run_parser.add_argument(
        "--mode", default="shadow", choices=["shadow", "live"], help="Execution mode"
    )
    run_parser.add_argument(
        "--symbols",
        default=None,
        help="Comma separated symbols (defaults to config whitelist)",
    )
    run_parser.add_argument(
        "--risk-profile",
        default=None,
        help="Risk profile version (e.g., moderate_v1)",
    )
    run_parser.add_argument(
        "--universe",
        default=None,
        help="Universe version (e.g., universe_v1)",
    )
    run_parser.add_argument(
        "--canary-profile",
        default=None,
        help="Canary profile version (e.g., canary_v1)",
    )
    run_parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Number of iterations to run (defaults to config)",
    )
    run_parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Interval seconds between iterations (defaults to config)",
    )
    return parser


def _render_json(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)

    env_overrides = dict(os.environ)
    if getattr(args, "risk_profile", None):
        env_overrides["RISK_PROFILE"] = args.risk_profile
    if getattr(args, "universe", None):
        env_overrides["UNIVERSE_PROFILE"] = args.universe
    if getattr(args, "canary_profile", None):
        env_overrides["CANARY_PROFILE"] = args.canary_profile
    config: AppConfig = load_config(env_overrides)

    if args.command == "health":
        ok = perform_health_check()
        print("OK" if ok else "FAIL")
        return 0 if ok else 1

    if args.command == "hl:readonly":
        symbols: Sequence[str] | None = args.symbols
        payload = perform_readonly_check(config, symbols=symbols)
        print(_render_json(payload))
        return 0 if payload.get("status") == "ok" else 1

    if args.command == "live:guard":
        try:
            enforce_live_trading_enabled(config)
        except RuntimeError as exc:
            LOGGER.info("Live trading remains disabled", extra={"error": str(exc)})
            print(str(exc))
            return 1
        LOGGER.warning("Live trading preconditions satisfied. Execution adapters still stubbed.")
        return 0

    if args.command == "status":
        from trader.storage.db import TraderStorage

        storage = TraderStorage(Path(config.db_path))
        class_membership = config.constraints.class_membership
        payload = {
            "profiles": {
                "risk": config.risk_profile,
                "universe": config.universe_profile,
                "canary": config.canary.profile,
                "counts": {
                    "majors": sum(1 for cls in class_membership.values() if cls == "majors"),
                    "alts": sum(1 for cls in class_membership.values() if cls == "alts"),
                },
            },
            "constraints": {
                "max_leverage": config.constraints.leverage_limit,
                "total_cap_pct": config.constraints.total_exposure_fraction,
                "daily_loss_limit_pct": config.constraints.daily_loss_limit_fraction,
                "cooldowns": {
                    "open": config.constraints.open_cooldown_seconds,
                    "add": config.constraints.add_cooldown_seconds,
                },
            },
            "canary": {
                "allowed_symbols": config.canary.allowed_symbols,
                "max_daily_orders": config.canary.max_daily_orders,
                "per_order_notional_cap_pct": config.canary.per_order_notional_cap_pct,
                "total_notional_cap_pct": config.canary.total_notional_cap_pct,
            },
            "status": storage.status(),
        }
        print(_render_json(payload))
        return 0

    if args.command == "run":
        symbols = (
            tuple(symbol.strip().upper() for symbol in args.symbols.split(","))
            if args.symbols
            else tuple(config.constraints.whitelist)
        )
        iterations = args.iterations or config.run_iterations
        interval = args.interval or config.run_interval_seconds
        mode = ExecutionMode(args.mode)
        canary = CanaryConstraints(
            enabled=os.getenv("LIVE_CANARY", "false").lower() == "true",
            allowed_symbols=config.canary.allowed_symbols,
            max_daily_orders=config.canary.max_daily_orders,
            per_order_notional_cap_pct=config.canary.per_order_notional_cap_pct,
            total_notional_cap_pct=config.canary.total_notional_cap_pct,
        )
        run_loop(
            symbols,
            config.constraints,
            config.provider,
            mode,
            Path(config.db_path),
            iterations=iterations,
            interval_seconds=interval,
            openai_kwargs=(
                {
                    "api_key": config.llm.openai_api_key,
                    "base_url": config.llm.openai_base_url,
                    "model": config.llm.openai_model,
                    "timeout_seconds": config.llm.openai_timeout,
                    "max_retries": config.llm.openai_max_retries,
                }
                if config.llm.openai_api_key
                else None
            ),
            xai_kwargs=(
                {
                    "api_key": config.llm.xai_api_key,
                    "base_url": config.llm.xai_base_url,
                    "model": config.llm.xai_model,
                    "timeout_seconds": config.llm.xai_timeout,
                    "max_retries": config.llm.xai_max_retries,
                }
                if config.llm.xai_api_key
                else None
            ),
            canary=canary,
        )
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
