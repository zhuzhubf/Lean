"""Universe configuration models."""

from __future__ import annotations

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator


class UniverseConfig(BaseModel):
    version: int = Field(..., ge=1)
    majors: list[str]
    alts: list[str]
    whitelist: list[str]
    symbol_metadata: dict[str, dict] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _validate_lists(self) -> "UniverseConfig":
        if not {sym.upper() for sym in self.majors} >= {"BTC", "ETH"}:
            raise ValueError("majors must include BTC and ETH")
        whitelist_set = {sym.upper() for sym in self.whitelist}
        if whitelist_set != {sym.upper() for sym in self.majors + self.alts}:
            raise ValueError("whitelist must match majors + alts")
        return self


def load_universe(path: str) -> UniverseConfig:
    with open(path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    try:
        return UniverseConfig.model_validate(raw)
    except ValidationError as exc:  # pragma: no cover - delegated to tests
        raise ValueError(f"Invalid universe config at {path}: {exc}") from exc
