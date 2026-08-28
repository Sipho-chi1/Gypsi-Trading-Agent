"""
Risk-Gate Agent.

Takes the Signal Agent's proposal AND the Independent Market Agent's read,
compares them, and returns the verdict that the Execution Agent will act on
mechanically. This is the "Round Table" step judges will scrutinise most —
spend the best free-tier model on this call.
"""
from round_table.schemas import RoundTableVerdict, IndependentRead

SYSTEM_PROMPT = """You are a skeptical trading reviewer sitting on a risk
gate. You receive two independent analyses of the same instrument: one from
a signal-generating trader, one from an independent market model that never
saw the trader's reasoning.

Find where the trader's reasoning ignores, downplays, or contradicts
evidence in the independent read. Look for:
  - Cherry-picking (only supporting evidence cited, contrary signals ignored)
  - Overconfidence not backed by the independent read
  - Outright directional disagreement between the two reads

Respond ONLY in JSON: {"decision": "approve|downsize|reject",
"reason": "...", "bias_flags": [...], "size_factor": 0-1}"""


def evaluate(proposal, independent_read: IndependentRead) -> RoundTableVerdict:
    # TODO: call_llm(SYSTEM_PROMPT, build_user_prompt(proposal, independent_read))
    # then json.loads(...) into a RoundTableVerdict.
    raise NotImplementedError("Wire up LLM call here (Day 3).")
