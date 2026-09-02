/**
 * Performance types.
 *
 * IMPORTANT: `GET /trades/performance` response shape is STILL being finalized.
 * This type must tolerate shape evolution — every field is optional and the
 * service layer defensively parses. Do NOT invent fields (e.g. an R-multiple is
 * not stored in the DB and must never be fabricated).
 */

export interface PerformanceSummary {
  total_trades?: number | null;
  closed_trades?: number | null;
  winning_trades?: number | null;
  losing_trades?: number | null;
  win_rate?: number | null;
  total_pnl?: number | null;
  average_pnl?: number | null;
  /** Verdict breakdown: e.g. { approve: 4, downsize: 1, reject: 2 }. */
  verdict_breakdown?: Record<string, number> | null;
  /** Equity-curve points, if the backend ever provides them. */
  equity_curve?: EquityPoint[] | null;
  /** Allow unknown keys so shape changes don't break consumers. */
  [key: string]: unknown;
}

export interface EquityPoint {
  /** ISO timestamp or epoch ms — normalized by the service layer. */
  time: number;
  value: number;
}

/** Tolerate an unknown payload and extract only confirmed, typed fields. */
export function normalizePerformance(raw: unknown): PerformanceSummary {
  if (!raw || typeof raw !== "object") return {};
  const r = raw as Record<string, unknown>;
  const num = (v: unknown): number | null | undefined =>
    typeof v === "number" ? v : typeof v === "string" && v !== "" && !Number.isNaN(Number(v)) ? Number(v) : v === null ? null : undefined;

  const out: PerformanceSummary = {
    total_trades: num(r.total_trades),
    closed_trades: num(r.closed_trades),
    winning_trades: num(r.winning_trades),
    losing_trades: num(r.losing_trades),
    win_rate: num(r.win_rate),
    total_pnl: num(r.total_pnl),
    average_pnl: num(r.average_pnl),
  };

  if (r.verdict_breakdown && typeof r.verdict_breakdown === "object") {
    const vd = r.verdict_breakdown as Record<string, unknown>;
    const breakdown: Record<string, number> = {};
    for (const [k, v] of Object.entries(vd)) {
      if (typeof v === "number") breakdown[k] = v;
    }
    out.verdict_breakdown = breakdown;
  }

  if (Array.isArray(r.equity_curve)) {
    const points: EquityPoint[] = [];
    for (const p of r.equity_curve) {
      if (p && typeof p === "object") {
        const obj = p as Record<string, unknown>;
        const time = typeof obj.time === "number" ? obj.time : typeof obj.time === "string" ? new Date(obj.time).getTime() : Number.NaN;
        const value = typeof obj.value === "number" ? obj.value : typeof obj.value === "string" ? Number(obj.value) : Number.NaN;
        if (!Number.isNaN(time) && !Number.isNaN(value)) points.push({ time, value });
      }
    }
    if (points.length > 0) out.equity_curve = points;
  }

  return out;
}
