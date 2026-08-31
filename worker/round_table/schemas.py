"""
Shared data contracts for the Round Table — this is the fixed interface
the two agent implementations and the graph wiring all build against.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, Union

Decision = Literal["approve", "downsize", "reject"]

BiasFlag = Literal[
    "cherry_picking",       # proposal cites only confirming evidence; independent
                             # read surfaced contradicting evidence in the same data
    "overconfidence",        # high implied conviction relative to a low confluence_score
    "contradiction",          # proposal and independent read disagree on direction outright
    "thin_confirmation",      # confluence_score only marginally clears the engine's own minimum
    "htf_conflict",            # proposal conflicts with independent_read.htf_bias OR proposal.htf_score
    "event_risk",               # a REAL near-term catalyst (see Step 3) falls inside the holding window
    "outside_killzone",          # proposal.active_killzones is empty at signal time
    "low_confluence",             # confluence_score low even though the engine let it through
    "portfolio_concentration",     # NEW — approving this would push correlated/same-direction
                                    # exposure past the account's concentration limit (Step 4)
]


@dataclass
class PortfolioState:
    open_positions: list[dict] = field(default_factory=list)      # [{"symbol", "direction", "notional_risk"}, ...]
    total_risk_deployed_pct: float = 0.0   # current % of account equity at risk across all opens
    same_direction_symbols: list[str] = field(default_factory=list)  # symbols currently open in the SAME direction as
                                                                     # this proposal (correlated exposure check)


@dataclass
class RoundTableInput:
    instrument: object       # signal_engine.instrument.Instrument
    proposal: object          # the real SMCSignal from smc_detector.analyse_pair()
    portfolio_state: PortfolioState = field(default_factory=PortfolioState)    # current open positions/exposure snapshot


@dataclass
class IndependentRead:
    """Output of the Independent Market Agent. Built from the instrument
    symbol and market context ONLY — must never be constructed from `proposal` fields."""
    direction: Literal["long", "short", "neutral"]
    confidence: float
    reasoning: str
    confluence_factors: list[str] = field(default_factory=list)
    catalysts: list[dict] = field(default_factory=list)   # [{"type": "earnings", "date": "...",
                                                             #   "days_until": int, "source": "..."}]
    htf_bias: Literal["bullish", "bearish", "neutral"] | None = None
    iv_rank: float | None = None    # only populated when instrument.options_enabled


@dataclass
class RoundTableVerdict:
    decision: Decision
    reason: str
    bias_flags: list[BiasFlag] = field(default_factory=list)
    size_factor: float = 1.0
    independent_read: IndependentRead | None = None

