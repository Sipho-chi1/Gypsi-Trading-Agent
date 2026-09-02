/**
 * Trade types — mirrors the confirmed `TradeOut` contract from the FastAPI backend.
 * See prd/overview.md "Confirmed contract (use directly)".
 */

export type TradeVerdictDecision = "approve" | "downsize" | "reject";

/** Status values the backend emits. Never assume only open/closed. */
export type TradeStatus =
  | "open"
  | "closed"
  | "skipped_zero_size"
  | "skipped";

/**
 * `TradeOut` — exact backend contract.
 *
 * `pnl` / `quantity` are optional here: the DB stores them and the backend may
 * expose them later. The type is structured so adding them is non-breaking.
 */
export interface Trade {
  id: number;
  symbol: string;
  direction: string | null;
  entry: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  reasoning: string | null;
  verdict_decision: TradeVerdictDecision;
  verdict_reason: string;
  bias_flags: string[];
  size_factor: number;
  status: string; // keep as string to tolerate future status values
  created_at: string; // ISO
  /** Optional — added non-breaking when the backend exposes it. */
  pnl?: number | null;
  /** Optional — added non-breaking when the backend exposes it. */
  quantity?: number | null;
}

/** Display-friendly verdict label. */
export const VERDICT_LABELS: Record<TradeVerdictDecision, string> = {
  approve: "APPROVE",
  downsize: "DOWNSIZE",
  reject: "REJECT",
};

/** Display-friendly status label. */
export const STATUS_LABELS: Record<TradeStatus, string> = {
  open: "OPEN",
  closed: "CLOSED",
  skipped_zero_size: "SKIPPED_ZERO_SIZE",
  skipped: "SKIPPED",
};

export function isKnownTradeStatus(value: string): value is TradeStatus {
  return value === "open" || value === "closed" || value === "skipped_zero_size" || value === "skipped";
}

export function tradeStatusLabel(value: string): string {
  return isKnownTradeStatus(value) ? STATUS_LABELS[value] : value.toUpperCase();
}
