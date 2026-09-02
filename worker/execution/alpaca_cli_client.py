"""
Thin wrapper around the Alpaca CLI. Replaces the earlier MCP-sidecar plan —
the CLI is fully documented, stable enough to build against this week, and
satisfies the hackathon's "MCP server OR CLI" requirement just as validly.
Every real order and every portfolio-state read routes through this file,
never a raw SDK call.

SAFETY — read before touching this file:
  The CLI has no confirmation prompts; every command executes immediately.
  `alpaca position close-all` and `alpaca order cancel-all` are one-shot
  and irreversible with no listing/preview first. Nothing in this file
  ever calls either of those. If a kill-switch is built later, it must be
  a deliberate, separately-guarded function — never reachable from the
  normal autonomous loop.

  This CLI is Alpha Preview — commands/flags can change without notice
  between releases. The Dockerfile pins an exact installed version; do not
  run `alpaca update` mid-build-week.

NOTE: this file targets the CURRENT (single-leg) ContractSelection shape
in execution/contract_selector.py — symbol/expiry/strike/option_type,
not a multi-leg spread. If contract_selector.py is later upgraded to the
IV-rank-driven multi-leg spread design, submit_option_order() below needs
a matching update to submit all legs as one multi-leg order instead of one
single-leg order — see docs/ARCHITECTURE.md's structure-selection policy
section for that design.
"""
import json
import subprocess
import uuid
from dataclasses import dataclass

from core.settings import settings


class AlpacaCLIError(RuntimeError):
    pass


def _run(*args: str, timeout: int = 30) -> dict | list:
    """
    Runs an `alpaca` CLI command and parses its JSON stdout. Credentials
    come from ALPACA_API_KEY / ALPACA_SECRET_KEY env vars (already in
    core/settings.py + .env.example) — never passed as CLI args, so they
    never show up in process listings or logs.
    """
    result = subprocess.run(
        ["alpaca", *args, "--quiet"],
        capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise AlpacaCLIError(result.stderr.strip() or f"exit code {result.returncode}")
    return json.loads(result.stdout)


def get_clock() -> dict:
    """Real market-open confirmation from Alpaca — a second, authoritative
    check alongside the SMC engine's own killzone/session logic (catches
    market holidays the killzone weekend-only check doesn't know about)."""
    return _run("clock")


def get_account() -> dict:
    return _run("account", "get")


def list_positions() -> list[dict]:
    """Feeds round_table's portfolio_state, if/when that's wired up — see
    docs/ARCHITECTURE.md. No dependency on any sidecar service to get this."""
    return _run("position", "list")


@dataclass
class OrderResult:
    raw: dict
    client_order_id: str


def find_option_contract(underlying_symbol: str, expiry: str, strike: float, option_type: str) -> dict:
    """
    Looks up the real Alpaca option contract (with its actual `symbol`
    field, e.g. "AAPL250620C00200000") rather than hand-constructing an
    OCC-format string — more robust, since Alpaca's own contract data is
    the source of truth for what's actually tradable at that
    strike/expiry.

    `expiry` is "YYYY-MM-DD". `option_type` is "call" or "put".
    Raises AlpacaCLIError if no matching contract is found.
    """
    result = _run(
        "option", "contracts",
        "--underlying-symbols", underlying_symbol,
        "--expiration-date", expiry,
        "--strike-price-gte", str(strike),
        "--strike-price-lte", str(strike),
        "--type", option_type,
    )
    contracts = result.get("option_contracts", []) if isinstance(result, dict) else []
    if not contracts:
        raise AlpacaCLIError(
            f"no option contract found for {underlying_symbol} {expiry} "
            f"{strike} {option_type}"
        )
    return contracts[0]


def submit_option_order(contract, quantity: int, side: str, dry_run: bool = False) -> OrderResult:
    """
    Matches THIS repo's current single-leg ContractSelection
    (symbol/expiry/strike/option_type/structure/premium_estimate).

    VERIFIED against the real installed CLI (`alpaca --help-all`,
    `alpaca order submit --schema`, and the CLI's own generated API types)
    — not a guess:

      - A single-leg option order does NOT need `--order-class mleg` or
        `--legs` — those are only for multi-leg spreads (see
        docs/ARCHITECTURE.md's note on the multi-leg upgrade path). For a
        single leg, `--symbol` + `--side` work exactly like an equity
        order — the only difference is `--symbol` must be the option
        contract's own OCC-format symbol, not the underlying's ticker.
      - That symbol is looked up via find_option_contract() above, since
        Alpaca's contract data is the real source of truth for the exact
        symbol string, not something to hand-construct.

    client_order_id is a fresh UUID per call so a retry after an ambiguous
    network failure (timeout with unknown fill status) can be replayed
    safely without risking a duplicate order — required for an unattended
    loop with no human watching for double-fills.
    """
    contract_info = find_option_contract(
        underlying_symbol=contract.symbol,
        expiry=contract.expiry,
        strike=contract.strike,
        option_type=contract.option_type,
    )

    client_order_id = str(uuid.uuid4())
    args = [
        "order", "submit",
        "--symbol", contract_info["symbol"],
        "--side", side,
        "--qty", str(quantity),
        "--type", "market",
        "--client-order-id", client_order_id,
    ]
    if dry_run:
        args.append("--dry-run")

    raw = _run(*args)
    return OrderResult(raw=raw, client_order_id=client_order_id)
