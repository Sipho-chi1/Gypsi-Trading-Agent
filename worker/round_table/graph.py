"""
LangGraph wiring for the Round Table.

Kept deliberately simple for the MVP: a single pass, no debate rounds.
(The original scope doc's "2-round debate" is a stretch goal — cut it
first if the schedule slips; a single-pass gate still tells the whole
story: independent read -> compare -> verdict.)
"""
from round_table.schemas import RoundTableInput, RoundTableVerdict
from round_table.independent_market_agent import analyse_independently
from round_table.risk_gate_agent import evaluate


def build_round_table():
    """
    Returns an object exposing .invoke(RoundTableInput) -> RoundTableVerdict.

    TODO: replace this plain-Python stand-in with an actual LangGraph
    StateGraph once the two agent functions above are implemented — the
    graph mainly earns its keep if/when the 2-round debate stretch goal
    gets built. Until then this linear version is simpler to debug.
    """
    class RoundTable:
        def invoke(self, rt_input: RoundTableInput) -> RoundTableVerdict:
            independent_read = analyse_independently(
                rt_input.instrument, market_context={}
            )
            return evaluate(rt_input.proposal, independent_read)

    return RoundTable()
