"""Pydantic response models — the fixed contract the frontend builds against."""
from pydantic import BaseModel
from typing import Literal


class TradeOut(BaseModel):
    id: int
    symbol: str
    direction: str | None
    entry: float | None
    stop_loss: float | None
    take_profit: float | None
    reasoning: str | None
    verdict_decision: Literal["approve", "downsize", "reject"]
    verdict_reason: str
    bias_flags: list[str]
    size_factor: float
    status: str
    created_at: str


class RoundTableEntryOut(BaseModel):
    """One deliberation, for the live Round Table view — this endpoint is
    what the demo's best visual moment renders from."""
    symbol: str
    proposal_reasoning: str
    independent_reasoning: str
    decision: str
    bias_flags: list[str]
