# Gypsi — Architecture Notes

See `WesCodies_RoundTable_Scope.pdf` in this folder for the full narrative
write-up (overview, hackathon-requirement mapping, hosting rationale,
day-by-day plan). This file is the terse, code-adjacent version for quick
reference while building.

## Pipeline

```
Signal Agent  →  The Round Table  →  Execution Agent
```

- **Signal Agent** — `worker/signal_engine/smc_detector.py` (ported from
  the original forex bot almost unchanged) + `worker/signal_engine/instrument.py`
  (new — replaces pip/lot/session assumptions with per-instrument config).
- **The Round Table** — `worker/round_table/`. Two isolated agent calls:
  `independent_market_agent.py` (symbol only, never the proposal) and
  `risk_gate_agent.py` (compares both reads, returns a verdict).
- **Execution Agent** — `worker/execution/`. Options contract selection +
  order placement via the Alpaca MCP sidecar (`mcp/`), never a raw SDK call.

## Isolation is a code-level guarantee, not a prompting convention

`independent_market_agent.analyse_independently(instrument, market_context)`
does not accept a `proposal` argument. That's deliberate — there should be
no way to accidentally leak the Signal Agent's reasoning into the
Independent Market Agent's context, even by mistake in a later refactor.

## What's ported vs. new

| Ported (mostly unchanged) | New for Gypsi |
|---|---|
| `smc_detector.py` pattern math | `instrument.py` |
| `adaptive_learner.py` core loop | Round-table-aware insight categories (TODO) |
| — | `round_table/` package |
| — | `execution/` package |
| — | Postgres-backed `journal_writer.py` (was local JSON) |
| — | Alpaca-backed `data_fetcher.py` (was Twelve Data) |
| — | Dollar-based `risk_manager.py` (was pip/lot-based) |

## Known gaps to close first (see TODOs in each file)

1. `data_fetcher.py` — no real Alpaca Market Data client wired up yet.
2. `independent_market_agent.py` / `risk_gate_agent.py` — LLM calls not wired up.
3. `contract_selector.py` — no real options chain lookup yet.
4. `mcp/Dockerfile` — placeholder; needs the real Alpaca MCP server install.
5. `adaptive_learner.py` — round_table_accuracy / bias_flag_predictiveness
   insight categories not yet added; modulo-trigger bug not yet fixed.
