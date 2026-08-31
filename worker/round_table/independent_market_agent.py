"""
Independent Market Agent.

CRITICAL: this function's only inputs are `instrument` and `market_context` — never `proposal` or `portfolio_state`.
That isolation is what makes this a genuine second opinion rather than a
rubber stamp. Enforce it here in code, not just via prompting: don't even
accept a `proposal` argument.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional
import httpx

from core.settings import settings
from round_table.schemas import IndependentRead

logger = logging.getLogger(__name__)

# Global hook to allow mocking LLM responses in unit tests and deterministic simulations
_llm_caller: Optional[Callable[[str, str], str]] = None


def set_llm_caller(caller: Optional[Callable[[str, str], str]]) -> None:
    """Sets a custom LLM caller for testing or overrides."""
    global _llm_caller
    _llm_caller = caller


def build_system_prompt(instrument) -> str:
    """Builds the dynamic system prompt tailored to the instrument's asset class and options capability."""
    symbol = getattr(instrument, "symbol", str(instrument))
    asset_class = getattr(instrument, "asset_class", "equity")
    options_enabled = bool(getattr(instrument, "options_enabled", False))

    prompt = (
        "You are an independent market analyst. You have not seen any other\n"
        "trader's thesis, proposal, or reasoning for this instrument — form your own\n"
        "view from the market data provided only.\n\n"
        f"Analyse {symbol} ({asset_class}) using the market data given. Determine:\n"
        "  1. Your own directional bias (long/short/neutral) and confidence (0-1).\n"
        "  2. The specific confluence factors that support your view (name them\n"
        "     precisely — e.g. \"bullish order block on H4\", \"equal lows swept on\n"
        "     M15\" — not vague justifications).\n"
        "  3. Whether the higher-timeframe (Daily/H4) bias agrees with your\n"
        "     lower-timeframe read, and state that HTF bias explicitly.\n"
        "  4. Any near-term catalyst provided in the market data below — do not\n"
        "     invent one from memory; if none is provided, report none.\n"
    )

    if options_enabled:
        prompt += (
            "  5. Note the provided IV rank and whether current options pricing looks rich or cheap relative to it.\n"
        )

    prompt += "\nMarket data provided:\n{market_context}\n\nRespond ONLY in JSON:\n"

    if options_enabled:
        prompt += (
            '{"direction": "long|short|neutral", "confidence": <0-1>, "reasoning": "<2-3 sentences>", '
            '"confluence_factors": ["..."], "catalysts": [], "htf_bias": "bullish|bearish|neutral", "iv_rank": <0-100>}'
        )
    else:
        prompt += (
            '{"direction": "long|short|neutral", "confidence": <0-1>, "reasoning": "<2-3 sentences>", '
            '"confluence_factors": ["..."], "catalysts": [], "htf_bias": "bullish|bearish|neutral"}'
        )

    return prompt


def _call_groq_llm(system_prompt: str, user_message: str) -> str:
    """Call Groq LLM (fast tier) with fallback."""
    if _llm_caller is not None:
        return _llm_caller(system_prompt, user_message)

    if not settings.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set — returning fallback neutral independent read")
        return json.dumps({
            "direction": "neutral",
            "confidence": 0.5,
            "reasoning": "Market data analysis pending LLM key configuration.",
            "confluence_factors": [],
            "catalysts": [],
            "htf_bias": "neutral",
        })

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
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error("Groq API call failed: %s", e)
        return json.dumps({
            "direction": "neutral",
            "confidence": 0.5,
            "reasoning": f"LLM error: {e}",
            "confluence_factors": [],
            "catalysts": [],
            "htf_bias": "neutral",
        })


def analyse_independently(instrument, market_context: dict) -> IndependentRead:
    """
    Produce an independent market analysis for the given instrument using only
    the freshly-fetched market context.
    
    ISOLATION GUARANTEE: Never receives proposal, signal, or portfolio_state.
    """
    system_prompt = build_system_prompt(instrument)
    user_prompt = f"Market data provided:\n{json.dumps(market_context, indent=2, default=str)}"

    raw_response = _call_groq_llm(system_prompt, user_prompt)

    try:
        # Strip potential markdown formatting if returned
        clean_text = raw_response.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        parsed = json.loads(clean_text.strip())
    except Exception as e:
        logger.error("Failed to parse IndependentRead JSON: %s. Response was: %s", e, raw_response)
        parsed = {}

    # Extract catalysts safely from the market context if not populated by LLM
    context_catalysts = market_context.get("catalysts", [])
    catalysts = parsed.get("catalysts", context_catalysts)

    direction = parsed.get("direction", "neutral")
    if direction not in ("long", "short", "neutral"):
        direction = "neutral"

    htf_bias = parsed.get("htf_bias")
    if htf_bias not in ("bullish", "bearish", "neutral"):
        htf_bias = None

    iv_rank = parsed.get("iv_rank")
    if iv_rank is not None:
        try:
            iv_rank = float(iv_rank)
        except (ValueError, TypeError):
            iv_rank = None

    return IndependentRead(
        direction=direction,
        confidence=float(parsed.get("confidence", 0.5)),
        reasoning=str(parsed.get("reasoning", "")),
        confluence_factors=list(parsed.get("confluence_factors", [])),
        catalysts=list(catalysts),
        htf_bias=htf_bias,
        iv_rank=iv_rank,
    )

