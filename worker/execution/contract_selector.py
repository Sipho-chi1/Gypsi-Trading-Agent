"""
Options contract selection — the one piece with no analog in the original
forex bot (forex has no options). Maps the Round Table's verdict/conviction
level to a concrete, defined-risk options structure.
"""
from dataclasses import dataclass


@dataclass
class ContractSelection:
    symbol: str
    expiry: str            # e.g. "2026-09-19"
    strike: float
    option_type: str       # "call" | "put"
    structure: str          # "single_leg" | "vertical_spread"
    premium_estimate: float


def select_contract(instrument, signal, verdict) -> ContractSelection:
    """
    Rough policy:
      - full consensus (size_factor == 1.0)  -> single-leg call/put,
        ~30-delta, 2-4 weeks out.
      - downsize (0 < size_factor < 1.0)      -> defined-risk vertical
        spread instead of a naked leg, to cap worst case.
    TODO: pull the live options chain via Alpaca's Market Data API and pick
    real strikes/expiries instead of hardcoding.
    """
    raise NotImplementedError("Wire up options chain lookup here (Day 4).")
