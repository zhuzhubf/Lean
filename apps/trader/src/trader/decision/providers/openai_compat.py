"""OpenAI-compatible provider that enforces JSON-only responses."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Callable

from trader.decision.base import DecisionProvider, RateLimiter, safe_hold
from trader.schemas import (
    AccountState,
    MarketSnapshot,
    PortfolioConstraints,
    TraceContext,
    TradePlan,
    validate_trade_plan_payload,
)

LOGGER = logging.getLogger(__name__)

ChatCaller = Callable[[str], str]


class OpenAICompatProvider(DecisionProvider):
    """Minimal OpenAI-compatible provider with JSON schema enforcement."""

    def __init__(
        self,
        chat_caller: ChatCaller | None = None,
        rate_limiter: RateLimiter | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str = "gpt-5.2",
    ) -> None:
        self.chat_caller = chat_caller or self._http_chat_caller
        self.rate_limiter = rate_limiter
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.base_url = base_url or "https://api.openai.com/v1/chat/completions"
        self.api_key = api_key
        self.model = model

    def _build_prompt(
        self,
        snapshot: MarketSnapshot,
        account: AccountState,
        constraints: PortfolioConstraints,
        trace: TraceContext,
        draft_plan: TradePlan | None = None,
    ) -> str:
        schema = TradePlan.model_json_schema()
        prompt = {
            "instruction": "Return ONLY a JSON object matching the TradePlan schema.",
            "schema": schema,
            "context": {
                "symbol": snapshot.symbol,
                "price": snapshot.price,
                "equity": account.equity,
                "mode": constraints.mode.value,
                "trace_id": trace.trace_id,
            },
        }
        if draft_plan is not None:
            prompt["draft_plan"] = draft_plan.model_dump()
        return json.dumps(prompt)

    def propose_plan(
        self,
        snapshot: MarketSnapshot,
        account: AccountState,
        constraints: PortfolioConstraints,
        trace: TraceContext,
        draft_plan: TradePlan | None = None,
    ) -> TradePlan:
        if self.rate_limiter:
            self.rate_limiter()

        try:
            prompt = self._build_prompt(
                snapshot, account, constraints, trace, draft_plan=draft_plan
            )
            raw_response = self.chat_caller(prompt)
            parsed = json.loads(raw_response)
            plan = validate_trade_plan_payload(parsed)
            return plan
        except Exception as exc:  # pragma: no cover - exercised in integration
            LOGGER.warning(
                "OpenAICompatProvider failed, returning HOLD",
                extra={"error": str(exc), "symbol": snapshot.symbol},
            )
            if draft_plan is not None:
                rationale = f"fallback_draft_due_to_provider_error: {exc}"
                return draft_plan.model_copy(update={"rationale": rationale})
            return safe_hold(f"provider_error: {exc}", snapshot)

    # --- internals -------------------------------------------------------
    def _http_chat_caller(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")

        payload = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "Return JSON only"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
            }
        ).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        backoff = 1.0
        last_error: Exception | None = None
        for _ in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(self.base_url, data=payload, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    body = resp.read().decode("utf-8")
                    data = json.loads(body)
                    choices = data.get("choices") or []
                    if not choices:
                        raise RuntimeError("No choices in response")
                    content = choices[0]["message"]["content"]
                    return content
            except (
                urllib.error.URLError,
                urllib.error.HTTPError,
                json.JSONDecodeError,
                KeyError,
            ) as exc:
                last_error = exc
                LOGGER.warning("OpenAI call failed", extra={"error": str(exc)})
                time.sleep(backoff)
                backoff *= 2
        raise RuntimeError(f"OpenAI call failed after retries: {last_error}")
