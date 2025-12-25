"""Provider routing with fallback semantics."""

from __future__ import annotations

import logging
from typing import Callable

from trader.decision.base import DecisionProvider, safe_hold
from trader.decision.providers.rule_based import RuleBasedProvider
from trader.schemas import (
    AccountState,
    MarketSnapshot,
    PortfolioConstraints,
    TraceContext,
    TradePlan,
)

LOGGER = logging.getLogger(__name__)


class ProviderRouter:
    """Select and invoke decision providers with graceful degradation."""

    def __init__(
        self,
        provider_name: str,
        openai_factory: Callable[[], DecisionProvider] | None = None,
        xai_factory: Callable[[], DecisionProvider] | None = None,
        fallback_provider: DecisionProvider | None = None,
    ) -> None:
        self.provider_name = provider_name.lower()
        self._fallback = fallback_provider or RuleBasedProvider()
        self._openai_factory = openai_factory
        self._xai_factory = xai_factory

    def _build_provider(self) -> DecisionProvider:
        if self.provider_name in {"openai", "gpt", "gpt-5.2"}:
            if self._openai_factory:
                return self._openai_factory()
            LOGGER.warning("OpenAI factory not configured; falling back to rule-based")
            return self._fallback
        if self.provider_name in {"xai", "grok"}:
            if self._xai_factory:
                return self._xai_factory()
            LOGGER.warning("xAI provider requested but not configured; using fallback")
            return self._fallback
        LOGGER.info(
            "Unknown provider requested; using fallback",
            extra={"provider": self.provider_name},
        )
        return self._fallback

    def propose_plan(
        self,
        snapshot: MarketSnapshot,
        account: AccountState,
        constraints: PortfolioConstraints,
        trace: TraceContext,
        draft_plan: TradePlan | None = None,
    ) -> TradePlan:
        provider = self._build_provider()
        trace.provider_id = provider.__class__.__name__
        try:
            return provider.propose_plan(snapshot, account, constraints, trace, draft_plan)
        except Exception as exc:  # pragma: no cover - fallback path tested via router
            LOGGER.warning(
                "Primary provider failed; falling back to rule-based",
                extra={"error": str(exc), "trace_id": trace.trace_id},
            )
            if draft_plan is not None:
                return draft_plan.model_copy(update={"rationale": f"provider_failure: {exc}"})
            return safe_hold(f"provider_failure: {exc}", snapshot)


__all__ = ["ProviderRouter"]
