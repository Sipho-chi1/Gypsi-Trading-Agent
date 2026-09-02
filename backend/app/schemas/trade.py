"""Pydantic response models — the fixed contract the frontend builds against."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Literal


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    direction: str | None = None
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    reasoning: str | None = None
    verdict_decision: str | None = None
    verdict_reason: str | None = None
    bias_flags: list[str] = []
    size_factor: float = 1.0
    status: str = "open"
    created_at: str | None = None
    pnl: float | None = None

    @field_validator("created_at", mode="before")
    @classmethod
    def serialize_created_at(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v) if v is not None else None

    @field_validator("bias_flags", mode="before")
    @classmethod
    def serialize_bias_flags(cls, v):
        if v is None:
            return []
        return list(v)


class RoundTableEntryOut(BaseModel):
    """One deliberation, for the live Round Table view — this endpoint is
    what the demo's best visual moment renders from."""
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    proposal_reasoning: str | None = None
    independent_reasoning: str | None = None
    decision: str | None = None
    bias_flags: list[str] = []

    @field_validator("bias_flags", mode="before")
    @classmethod
    def serialize_bias_flags(cls, v):
        if v is None:
            return []
        return list(v)
