"""Load and validate canary live trading constraints."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator


class CanaryProfile(BaseModel):
    profile_name: str
    version: int = Field(..., ge=1)
    allowed_symbols: Sequence[str]
    max_daily_orders: int = Field(..., ge=0)
    per_order_notional_cap_pct: float = Field(..., gt=0, lt=1)
    total_notional_cap_pct: float = Field(..., gt=0, lt=1)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _validate_caps(self) -> "CanaryProfile":
        if self.total_notional_cap_pct < self.per_order_notional_cap_pct:
            raise ValueError("total cap must be >= per-order cap")
        return self


def load_canary_profile(path: str) -> CanaryProfile:
    with open(path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    try:
        return CanaryProfile.model_validate(raw)
    except ValidationError as exc:  # pragma: no cover - delegated to tests
        raise ValueError(f"Invalid canary profile at {path}: {exc}") from exc


def canary_profile_path(config_root: Path, name: str) -> Path:
    return config_root / "canary" / f"{name}.yaml"
