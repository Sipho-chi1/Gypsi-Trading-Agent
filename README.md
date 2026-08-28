# Gypsi

**A jaeger needs two pilots for the drift. Gypsi needs two agents for a trade.**

Gypsi is an autonomous options-trading agent built for the Alpaca AI Trading Agents Hackathon.
It's built on top of an existing SMC/ICT signal-detection engine (originally a forex bot) — that
part already works and isn't being rebuilt. What Gypsi adds is **The Round Table**: every signal
the detector proposes has to survive an independent cross-examination before any capital moves,
with no human in the loop at any point.

## How it thinks

```
Signal Agent  →  The Round Table  →  Execution Agent
(proposes)       (deliberates)        (acts)
```

1. **Signal Agent** — the ported SMC detector scans the watchlist and proposes a trade:
   direction, entry, stop, target, and the reasoning behind it.
2. **The Round Table** — two agents inside a bounded LangGraph deliberation:
   - **Independent Market Agent** never sees the Signal Agent's proposal. It forms its own
     read of the same symbol from scratch.
   - **Risk-Gate Agent** compares both reads, looks for contradiction, cherry-picking, or
     overconfidence, and returns a verdict: `approve` / `downsize` / `reject`.
3. **Execution Agent** — consumes the verdict programmatically and, if approved, selects an
   options contract and places the order through Alpaca's MCP server. A reject is logged with
   its reason; nothing gets sent to Alpaca.

Every closed trade, along with the Round Table's original verdict and bias flags, is written
back to Postgres, so the adaptive learner can measure not just "did the setup work" but
**"was the gate's own call right"** — and tune itself accordingly.

## Repo layout

```
gypsi/
├── backend/        FastAPI — serves trade/verdict history to the dashboard
├── worker/         Always-on loop: signal_engine → round_table → execution
├── mcp/            Sidecar wrapping Alpaca's MCP server
├── frontend/        Next.js dashboard (live feed, Round Table view, performance)
├── infra/          docker-compose + Railway/Vercel config
└── docs/           Architecture notes, project scope PDF
```

## Hosting

| Component            | Host                                              |
|-----------------------|---------------------------------------------------|
| Frontend              | Vercel                                             |
| Backend API            | Railway                                            |
| Worker (trading loop)  | Railway (separate always-on service)               |
| MCP server              | Railway (sidecar, private network)                 |
| Database                | Railway Postgres                                   |

See `docs/ARCHITECTURE.md` and `docs/WesCodies_RoundTable_Scope.pdf` for the full write-up.

## Local development

```bash
cp .env.example .env      # fill in Alpaca + LLM provider keys
docker-compose up --build
```

This brings up `api`, `worker`, `mcp`, and `postgres` together, mirroring the Railway layout.
