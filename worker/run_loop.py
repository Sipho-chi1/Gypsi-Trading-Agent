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
from round_table.schemas import PortfolioState, RoundTableInput
from round_table.graph import build_round_table
from execution.executor import place_order
from execution.contract_selector import select_contract
from execution.alpaca_cli_client import get_account, list_positions, AlpacaCLIError
from journal_writer import log_trade, log_no_trade
from core.settings import settings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gypsi.worker")


def get_live_equity(fallback: float = 100_000.0) -> float:
    """
    Pulls real account equity from Alpaca before each cycle, via the CLI
    (get_account()["equity"] — verified real field, confirmed against the
    CLI's own response schema). Falls back to a fixed value only if the
    call fails, so a transient network hiccup can't crash the whole loop —
    but it's logged loudly, since silently trading on a stale/wrong
    balance for a whole cycle is a real risk worth knowing about.
    """
    try:
        account = get_account()
        return float(account["equity"])
    except (AlpacaCLIError, KeyError, ValueError) as e:
        log.warning(f"Could not fetch live equity, using fallback ${fallback:,.0f}: {e}")
        return fallback


def fetch_portfolio_state(direction: str | None = None) -> PortfolioState:
    """
    Real query via Alpaca CLI — pulls current open positions and computes
    exposure for the Round Table's portfolio_concentration check.

    HONEST LIMITATION, worth knowing before trusting this blindly: a
    single Gypsi spread trade (e.g. a bull put credit spread) creates TWO
    separate rows in Alpaca's position list — one per leg — each with its
    own `side` ("long"/"short"), since that's how Alpaca reports
    multi-leg positions at the broker level. That means filtering by raw
    position `side` is NOT a reliable way to determine a spread's overall
    directional bias (a bull put spread has one long leg AND one short
    leg simultaneously). What's implemented below is a best-effort proxy
    using each position's `symbol` (grouping by underlying) rather than
    `side` directly. The more accurate fix — tracking direction via our
    OWN trades table (journal_writer already logs `direction` per trade)
    instead of trying to infer it from Alpaca's raw leg-level position
    data — is a better follow-up if this proxy turns out to be too noisy
    in practice; flagging it here rather than presenting this as fully
    correct.

    total_risk_deployed_pct is similarly a proxy: it sums each position's
    |cost_basis| relative to account equity. For debit spreads that's a
    reasonable stand-in for capital at risk; for credit spreads cost_basis
    doesn't cleanly represent max risk the way our own trades table's
    `max_risk` field does — same caveat as above applies.
    """
    account = get_account()
    equity = float(account["equity"])

    try:
        positions = list_positions()
    except AlpacaCLIError as e:
        log.warning(f"Could not fetch positions, treating as flat: {e}")
        positions = []

    total_risk = sum(abs(float(p["cost_basis"])) for p in positions)
    total_risk_deployed_pct = (total_risk / equity * 100) if equity > 0 else 0.0

    # Proxy for "same direction as this proposal": underlying symbols with
    # a net-long position lean toward a bullish read, net-short toward
    # bearish. See the docstring caveat above — this is approximate.
    same_direction_symbols: list[str] = []
    if direction:
        target_side = "long" if direction == "bullish" else "short"
        by_symbol: dict[str, list[str]] = {}
        for p in positions:
            by_symbol.setdefault(p["symbol"], []).append(p["side"])
        for symbol, sides in by_symbol.items():
            long_count = sides.count("long")
            short_count = sides.count("short")
            net_side = "long" if long_count > short_count else "short"
            if net_side == target_side:
                same_direction_symbols.append(symbol)

    return PortfolioState(
        open_positions=[{"symbol": p["symbol"], "side": p["side"], "cost_basis": p["cost_basis"]} for p in positions],
        total_risk_deployed_pct=total_risk_deployed_pct,
        same_direction_symbols=same_direction_symbols,
    )


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

        # Portfolio state is fetched per-instrument, not once for the whole
        # watchlist pass, because same_direction_symbols genuinely depends
        # on THIS signal's direction (see fetch_portfolio_state's docstring).
        portfolio_state = fetch_portfolio_state(direction=signal.bias)

        # Stage 2 & 3 — The Round Table: independent read + risk-gate verdict.
        # The Independent Market Agent inside this graph receives ONLY the
        # symbol, never `signal` — isolation is enforced by the graph's input
        # schema, not by prompting.
        verdict = round_table.invoke(RoundTableInput(
            instrument=instrument,
            proposal=signal,
            portfolio_state=portfolio_state,
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
        account_balance = get_live_equity()
        try:
            run_iteration(round_table, watchlist, account_balance)
        except Exception:
            log.exception("iteration failed, continuing loop")
        time.sleep(settings.POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
