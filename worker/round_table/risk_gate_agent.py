"""
Risk-Gate Agent.

Takes the Signal Agent's proposal, the Independent Market Agent's read,
and the portfolio state, compares them, and returns the verdict that the
Execution Agent will act on mechanically.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional
import httpx

try:
    import config
except ImportError:
    from signal_engine import config

from core.settings import settings
from round_table.schemas import (
    BiasFlag,
    Decision,
    IndependentRead,
    PortfolioState,
    RoundTableVerdict,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a skeptical risk reviewer sitting on a trading desk's risk gate.
You receive: a trader's proposal (with engine-computed confluence/session
data), an independent analyst's read (which never saw the trader's
reasoning), and the account's current portfolio exposure.

Check for:
  - CHERRY_PICKING: trader's reasoning ignores confluence factors the
    independent analyst found that contradict the trader's direction.
  - OVERCONFIDENCE: high implied conviction relative to a low confluence_score.
  - CONTRADICTION: trader and independent analyst disagree on direction.
  - THIN_CONFIRMATION: confluence_score only marginally clears the engine's minimum.
  - HTF_CONFLICT: setup goes against independent_read.htf_bias or proposal.htf_score.
  - EVENT_RISK: independent_read.catalysts contains a real catalyst inside
    the position's expected holding window. Only flag this if catalysts is
    genuinely non-empty — do not infer a catalyst that wasn't provided.
  - OUTSIDE_KILLZONE: active_killzones is empty at signal time.
  - LOW_CONFLUENCE: confluence_score is low even though the engine allowed it.
  - PORTFOLIO_CONCENTRATION: total_risk_deployed_pct is already near the
    account ceiling, or 3+ same-direction positions are already open.

Decision rules (apply in order):
  1. CONTRADICTION or EVENT_RISK -> "reject".
  2. Direction agrees, one or more other flags fire -> "downsize".
  3. Direction agrees, no flags -> "approve".

Respond ONLY in JSON:
{"decision": "approve|downsize|reject", "reason": "<one specific sentence>",
 "bias_flags": [...], "size_factor": <0.25-1.0>}"""

# Global hook to allow mocking LLM responses in unit tests and deterministic simulations
_llm_caller: Optional[Callable[[str, str], str]] = None


def set_llm_caller(caller: Optional[Callable[[str, str], str]]) -> None:
    """Sets a custom LLM caller for testing or overrides."""
    global _llm_caller
    _llm_caller = caller


def _call_gemini_llm(system_prompt: str, user_message: str) -> str:
    """Call Gemini / Reasoning LLM with fallback."""
    if _llm_caller is not None:
        return _llm_caller(system_prompt, user_message)

    # Use Gemini API if configured, otherwise Groq or fallback
    api_key = settings.GEMINI_API_KEY or settings.GROQ_API_KEY
    if not api_key:
        logger.warning("No LLM key configured for Risk-Gate Agent — relying on deterministic rules")
        return json.dumps({
            "decision": "approve",
            "reason": "Rule-based evaluation fallback.",
            "bias_flags": [],
            "size_factor": 1.0,
        })

    # If GEMINI_API_KEY is available, call Gemini endpoint
    if settings.GEMINI_API_KEY:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_message}]}],
            "generationConfig": {"response_mime_type": "application/json"},
        }
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.error("Gemini API call failed: %s", e)

    # Fallback to Groq if Gemini fails or only GROQ_API_KEY is set
    if settings.GROQ_API_KEY:
        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error("Groq fallback call failed: %s", e)

    return json.dumps({
        "decision": "approve",
        "reason": "Deterministic fallback.",
        "bias_flags": [],
        "size_factor": 1.0,
    })


def _estimate_holding_window_days(proposal) -> int:
    """Estimates the position's expected holding window in days based on setup/timeframe."""
    # Intraday M5/M15 or Silver Bullet trades hold <= 1-2 days; swing setups hold ~3-5 days
    if getattr(proposal, "in_silver_bullet", False):
        return 1
    return 3


def _compute_deterministic_size_factor(flag_count: int) -> float:
    """
    Compute deterministic size_factor based on flag count:
    0 flags -> 1.0, 1 flag -> 0.6, 2+ flags -> 0.35, floor 0.25.
    Always clamped to [0.25, 1.0].
    """
    if flag_count == 0:
        raw_factor = 1.0
    elif flag_count == 1:
        raw_factor = 0.6
    else:
        raw_factor = 0.35

    return max(0.25, min(1.0, raw_factor))


def evaluate(
    proposal,
    independent_read: IndependentRead,
    portfolio_state: Optional[PortfolioState] = None,
) -> RoundTableVerdict:
    """
    Evaluate proposal against independent read and portfolio state.
    Applies strict deterministic decision rules and size clamping in code.
    """
    if portfolio_state is None:
        portfolio_state = PortfolioState()

    min_confluence = getattr(config, "MIN_CONFLUENCE_SCORE", 4)
    active_kz_str = ", ".join(proposal.active_killzones) if getattr(proposal, "active_killzones", None) else "NONE"

    user_message = f"""Trader's proposal:
  Direction: {proposal.bias}  Entry: {proposal.entry_price}  Stop: {proposal.stop_loss}
  Target: {proposal.take_profit}  R:R: {proposal.rr}
  Confluence score: {proposal.confluence_score} (engine minimum: {min_confluence})
  Active killzones: {active_kz_str}
  Silver Bullet: {proposal.in_silver_bullet}  OTE zone: {proposal.in_ote_zone}
  AMD phase: {proposal.amd_phase}  HTF score: {proposal.htf_score}
  ML win probability: {proposal.ml_win_prob}
  Stated reasoning: {proposal.reason}

Independent analyst's read:
  Direction: {independent_read.direction}  Confidence: {independent_read.confidence}
  Confluence factors: {independent_read.confluence_factors}
  Catalysts: {independent_read.catalysts}
  HTF bias: {independent_read.htf_bias}
  IV rank (if applicable): {independent_read.iv_rank}

Current portfolio state:
  Total risk deployed: {portfolio_state.total_risk_deployed_pct}%
  Same-direction open positions: {portfolio_state.same_direction_symbols}"""

    raw_response = _call_gemini_llm(SYSTEM_PROMPT, user_message)

    try:
        clean_text = raw_response.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        parsed = json.loads(clean_text.strip())
    except Exception as e:
        logger.error("Failed to parse Risk-Gate JSON: %s. Raw response: %s", e, raw_response)
        parsed = {}

    model_size_factor = parsed.get("size_factor")
    model_flags = [str(f).lower() for f in parsed.get("bias_flags", [])]
    reason = str(parsed.get("reason", "")).strip()

    # ── DETERMINISTIC CODE-LEVEL RULE VALIDATION ────────────────────────────
    flags: set[BiasFlag] = set()

    # Normalize existing model flags
    valid_flags: set[BiasFlag] = {
        "cherry_picking",
        "overconfidence",
        "contradiction",
        "thin_confirmation",
        "htf_conflict",
        "event_risk",
        "outside_killzone",
        "low_confluence",
        "portfolio_concentration",
    }
    for f in model_flags:
        if f in valid_flags:
            flags.add(f)  # type: ignore

    # 1. Contradiction Check (Direction Disagreement)
    prop_bias = str(proposal.bias).lower()
    read_dir = str(independent_read.direction).lower()
    is_bull = prop_bias in ("bullish", "long", "buy")
    is_bear = prop_bias in ("bearish", "short", "sell")

    if (is_bull and read_dir in ("short", "bearish")) or (is_bear and read_dir in ("long", "bullish")):
        flags.add("contradiction")

    # 2. Event Risk Check (Real near-term catalyst inside holding window)
    holding_window_days = _estimate_holding_window_days(proposal)
    if independent_read.catalysts:
        for c in independent_read.catalysts:
            days_until = c.get("days_until") if isinstance(c, dict) else getattr(c, "days_until", None)
            if days_until is not None and days_until <= holding_window_days:
                flags.add("event_risk")
                break

    # 3. Outside Killzone Check
    if not getattr(proposal, "active_killzones", None) and not getattr(proposal, "in_kill_zone", False):
        flags.add("outside_killzone")

    # 4. Portfolio Concentration Check
    # Ceiling at 6.0% equity or 3+ same-direction open positions
    if portfolio_state.total_risk_deployed_pct >= 6.0 or len(portfolio_state.same_direction_symbols) >= 3:
        flags.add("portfolio_concentration")

    # 5. Low Confluence / Thin Confirmation
    if proposal.confluence_score < min_confluence:
        flags.add("low_confluence")
    elif proposal.confluence_score == min_confluence:
        flags.add("thin_confirmation")

    # 6. HTF Conflict
    if independent_read.htf_bias:
        read_htf = independent_read.htf_bias.lower()
        if (is_bull and read_htf == "bearish") or (is_bear and read_htf == "bullish"):
            flags.add("htf_conflict")

    # ── DETERMINISTIC DECISION RULES ────────────────────────────────────────
    # Apply in order:
    # 1. CONTRADICTION or EVENT_RISK -> "reject"
    # 2. Direction agrees, one or more other flags fire -> "downsize"
    # 3. Direction agrees, no flags -> "approve"
    if "contradiction" in flags or "event_risk" in flags:
        decision: Decision = "reject"
        if not reason:
            if "contradiction" in flags:
                reason = "Proposal direction directly contradicts independent market read."
            else:
                reason = "Near-term catalyst event risk falls inside position holding window."
    elif len(flags) > 0:
        decision = "downsize"
        if not reason:
            reason = f"Confluence downsized due to identified risk flags: {', '.join(sorted(flags))}."
    else:
        decision = "approve"
        if not reason:
            reason = "Independent market analysis confirms trade thesis with zero risk flags."

    # ── DETERMINISTIC SIZE FACTOR & CLAMPING ─────────────────────────────────
    deterministic_size = _compute_deterministic_size_factor(len(flags))
    final_size_factor = max(0.25, min(1.0, deterministic_size))

    logger.info(
        "RoundTable Risk Gate evaluation: decision=%s, flags=%s, model_size=%s, deterministic_size=%s",
        decision,
        list(flags),
        model_size_factor,
        final_size_factor,
    )

    return RoundTableVerdict(
        decision=decision,
        reason=reason,
        bias_flags=sorted(list(flags)),  # type: ignore
        size_factor=final_size_factor,
        independent_read=independent_read,
    )

