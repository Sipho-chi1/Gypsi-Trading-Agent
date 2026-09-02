/**
 * Round Table types.
 *
 * Backend contract PENDING — the exact JSON contract is NOT invented here.
 * The UI supports a fixed set of perspectives rendered as designed panels;
 * a future adapter maps the real backend response into `RoundTablePerspective[]`.
 */

export type PerspectiveKey =
  | "market"
  | "technical"
  | "risk"
  | "sentiment"
  | "macro"
  | "execution"
  | "consensus";

export interface RoundTablePerspective {
  key: PerspectiveKey;
  title: string;
  /** Short summary line, or null while awaiting backend. */
  summary: string | null;
  /** Detailed body, or null while awaiting backend. */
  detail: string | null;
}

export const PERSPECTIVE_DEFS: Array<{
  key: PerspectiveKey;
  title: string;
}> = [
  { key: "market", title: "Market" },
  { key: "technical", title: "Technical" },
  { key: "risk", title: "Risk" },
  { key: "sentiment", title: "Sentiment" },
  { key: "macro", title: "Macro" },
  { key: "execution", title: "Execution" },
];
