"""
LangGraph wiring for the Round Table.

Orchestrates the deliberation gate:
State: instrument, proposal, portfolio_state, independent_read, verdict
Nodes: "independent_analysis" -> "risk_gate"
Edges: START -> independent_analysis -> risk_gate -> END

Single-pass for this MVP. Structured so a bounded 2-round debate is an edge addition later.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, TypedDict, Union

try:
    from langgraph.graph import StateGraph, START, END
    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False

from round_table.schemas import (
    IndependentRead,
    PortfolioState,
    RoundTableInput,
    RoundTableVerdict,
)
from round_table.market_context import build_market_context
from round_table.independent_market_agent import analyse_independently
from round_table.risk_gate_agent import evaluate

logger = logging.getLogger(__name__)


class RoundTableState(TypedDict, total=False):
    instrument: Any
    proposal: Any
    portfolio_state: PortfolioState
    market_context: dict
    independent_read: Optional[IndependentRead]
    verdict: Optional[RoundTableVerdict]


def independent_analysis_node(state: RoundTableState) -> dict:
    """Node 1: Independent Market Agent execution (strictly isolated)."""
    instrument = state["instrument"]
    market_context = state.get("market_context") or build_market_context(instrument)
    # ISOLATION: Passes instrument and market_context ONLY
    independent_read = analyse_independently(instrument, market_context)
    return {
        "market_context": market_context,
        "independent_read": independent_read,
    }


def risk_gate_node(state: RoundTableState) -> dict:
    """Node 2: Risk-Gate Agent evaluation comparing proposal, independent read, and portfolio exposure."""
    proposal = state["proposal"]
    independent_read = state["independent_read"]
    portfolio_state = state.get("portfolio_state") or PortfolioState()

    verdict = evaluate(proposal, independent_read, portfolio_state)
    return {
        "verdict": verdict,
    }


class RoundTableRunner:
    """Invokable wrapper around the Round Table graph."""

    def __init__(self, app=None):
        self._app = app

    def invoke(self, rt_input: Union[RoundTableInput, dict]) -> RoundTableVerdict:
        if isinstance(rt_input, RoundTableInput):
            initial_state: RoundTableState = {
                "instrument": rt_input.instrument,
                "proposal": rt_input.proposal,
                "portfolio_state": rt_input.portfolio_state or PortfolioState(),
            }
        else:
            initial_state = {
                "instrument": rt_input["instrument"],
                "proposal": rt_input["proposal"],
                "portfolio_state": rt_input.get("portfolio_state", PortfolioState()),
            }

        if self._app is not None:
            final_state = self._app.invoke(initial_state)
            return final_state["verdict"]

        # Deterministic sequential fallback if langgraph runtime is not loaded
        state1 = independent_analysis_node(initial_state)
        merged = {**initial_state, **state1}
        state2 = risk_gate_node(merged)
        return state2["verdict"]


def build_round_table() -> RoundTableRunner:
    """Constructs and compiles the Round Table StateGraph."""
    if _LANGGRAPH_AVAILABLE:
        workflow = StateGraph(RoundTableState)
        workflow.add_node("independent_analysis", independent_analysis_node)
        workflow.add_node("risk_gate", risk_gate_node)

        workflow.add_edge(START, "independent_analysis")
        workflow.add_edge("independent_analysis", "risk_gate")
        workflow.add_edge("risk_gate", END)

        app = workflow.compile()
        return RoundTableRunner(app=app)

    logger.warning("LangGraph not available, using direct RoundTableRunner fallback.")
    return RoundTableRunner(app=None)

