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
| `adaptive_learner.py` core loop | Round-table-aware insight categories & trigger fix |
| — | `round_table/` package |
| — | `execution/` package |
| — | Postgres-backed `journal_writer.py` (was local JSON) |
| — | Alpaca-backed `data_fetcher.py` (was Twelve Data) |
| — | Dollar-based `risk_manager.py` (was pip/lot-based) |

## Pipeline Status & Implemented Integrations

1. `data_fetcher.py` — Multi-timeframe bar retrieval and session/killzone tagging.
2. `independent_market_agent.py` / `risk_gate_agent.py` — Multi-model LLM calls wired with deterministic risk gating.
3. `contract_selector.py` — Options contract strike/expiry selection and defined-risk structure sizing.
4. `mcp/` & `execution/mcp_client.py` — Alpaca MCP sidecar server & JSON-RPC client.
5. `adaptive_learner.py` — 14 insight categories (including Round Table accuracy and bias-flag predictiveness) + modulo adaptation trigger fixed.
6. `market_context.py` — Real live catalyst and news query via Alpaca API.
7. `executor.py` — Dynamic equity retrieval via Alpaca CLI.
8. `backend/app/main.py` — Configurable CORS environment settings.
