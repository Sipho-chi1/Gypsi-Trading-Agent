"""Shared data contracts for the Round Table — this is the fixed interface
the two agent implementations and the graph wiring all build against."""
from dataclasses import dataclass, field
from typing import Literal

Decision = Literal["approve", "downsize", "reject"]


@dataclass
class RoundTableInput:
    instrument: object          # signal_engine.instrument.Instrument
    proposal: object            # SMCSignal from smc_detector.analyse_pair()


@dataclass
class IndependentRead:
    """Output of the Independent Market Agent. Built from the instrument
    symbol ONLY — must never be constructed from `proposal` fields."""
    direction: Literal["long", "short", "neutral"]
    confidence: float
    reasoning: str
    catalysts: list[str] = field(default_factory=list)   # earnings, news, IV skew notes


@dataclass
class RoundTableVerdict:
    decision: Decision
    reason: str
    bias_flags: list[str] = field(default_factory=list)   # e.g. ["cherry_picking"]
    size_factor: float = 1.0        # 1.0 = full size, <1.0 for "downsize"
    independent_read: IndependentRead | None = None
