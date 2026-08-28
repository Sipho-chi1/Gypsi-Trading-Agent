"""
Gypsi worker entrypoint.

The always-on loop: poll the watchlist -> Signal Agent proposes -> The Round
Table deliberates -> Execution Agent acts. No human approval step anywhere
in this file — that's what makes the agent autonomous per the hackathon's
core requirements.

This is the ported/adapted equivalent of the original forex bot's main.py
run_iteration(), generalised from a single forex pair to a watchlist of
equities/ETFs and with the Round Table inserted between signal and execution.
"""
import time
import logging

from signal_engine.instrument import load_watchlist
from signal_engine.data_fetcher import fetch_multi_tf
from signal_engine.smc_detector import analyse_pair
from signal_engine.risk_manager import can_trade
from round_table.graph import build_round_table, RoundTableInput
from execution.executor import place_order
from execution.contract_selector import select_contract
from journal_writer import log_trade, log_no_trade
from core.settings import settings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gypsi.worker")


def run_iteration(round_table, watchlist, account_balance: float) -> None:
    for instrument in watchlist:
        candles = fetch_multi_tf(instrument)
        if candles is None:
            continue

        # Stage 1 — Signal Agent: propose a trade (or don't)
        signal = analyse_pair(instrument, candles)
        if signal is None:
            continue

        # Pre-gate sanity check (daily loss cap / kill switch), unchanged
        # in spirit from the original risk_manager.can_trade()
        allowed, reason = can_trade(account_balance)
        if not allowed:
            log.info(f"[{instrument.symbol}] blocked before Round Table: {reason}")
            continue

        # Stage 2 & 3 — The Round Table: independent read + risk-gate verdict.
        # The Independent Market Agent inside this graph receives ONLY the
        # symbol, never `signal` — isolation is enforced by the graph's input
        # schema, not by prompting.
        verdict = round_table.invoke(RoundTableInput(
            instrument=instrument,
            proposal=signal,
        ))

        if verdict.decision == "reject":
            log_no_trade(instrument, verdict.reason)
            log.info(f"[{instrument.symbol}] REJECTED by Round Table: {verdict.reason}")
            continue

        # Stage 4 — Execution Agent
        contract = select_contract(instrument, signal, verdict)
        position = place_order(instrument, signal, contract, verdict)
        log_trade(instrument, signal, verdict, contract, position)
        log.info(f"[{instrument.symbol}] {verdict.decision.upper()} -> order placed: {position}")


def main() -> None:
    round_table = build_round_table()
    watchlist = load_watchlist(settings.WATCHLIST)

    log.info(f"Gypsi worker starting — watchlist: {[i.symbol for i in watchlist]}")
    while True:
        account_balance = 100_000.0  # TODO: pull live equity from Alpaca before each cycle
        try:
            run_iteration(round_table, watchlist, account_balance)
        except Exception:
            log.exception("iteration failed, continuing loop")
        time.sleep(settings.POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
