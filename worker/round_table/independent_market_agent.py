"""
Independent Market Agent.

CRITICAL: this function's only input is `instrument` — never `proposal`.
That isolation is what makes this a genuine second opinion rather than a
rubber stamp. Enforce it here in code, not just via prompting: don't even
accept a `proposal` argument.
"""
from round_table.schemas import IndependentRead

SYSTEM_PROMPT = """You are an independent market analyst. You have not seen
any other trader's thesis. Analyse the given symbol using only the market
data provided and produce your own directional read.

Look for: trend/structure context, options chain IV/skew if provided, and
any near-term catalyst (earnings, macro prints, news).

Respond ONLY in JSON matching: {"direction": "long|short|neutral",
"confidence": 0-1, "reasoning": "...", "catalysts": ["..."]}"""


def analyse_independently(instrument, market_context: dict) -> IndependentRead:
    # TODO: call_llm(SYSTEM_PROMPT, build_user_prompt(instrument, market_context))
    # then json.loads(...) into an IndependentRead. Route through Groq or
    # Gemini per docs/ARCHITECTURE.md's provider split.
    raise NotImplementedError("Wire up LLM call here (Day 3).")
