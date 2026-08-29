"""
ML Model Scoring Stub / Fallback.
Provides win probability scoring for SMC signals when a trained model is present,
or graceful passthrough when operating purely on rule-based ICT confluence.
"""
from typing import Optional

WIN_PROB_THRESHOLD: float = 0.55

def score_smc_signal(signal: object) -> Optional[float]:
    """Score signal win probability using trained ML model if available."""
    # By default, return None so the rule-based ICT logic gates the trade
    return None
