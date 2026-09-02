/**
 * Agent status types.
 *
 * Backend contract PENDING — the service maps an eventual raw backend value into
 * these display states. Backend values are NOT assumed to equal the display
 * strings, so a raw string like "analyzing" must be normalized by the adapter.
 */

export type AgentDisplayState =
  | "ONLINE"
  | "OFFLINE"
  | "ANALYZING"
  | "MONITORING"
  | "WAITING"
  | "TRADE IDENTIFIED"
  | "EXECUTING"
  | "ERROR";

/** Unknown is used when no backend value exists at all yet. */
export type AgentState = AgentDisplayState | "UNKNOWN";

export interface AgentStatus {
  state: AgentState;
  /** Raw backend value if present — never assumed. */
  raw: unknown;
  connected: boolean;
}

export const AGENT_STATES: AgentDisplayState[] = [
  "ONLINE",
  "OFFLINE",
  "ANALYZING",
  "MONITORING",
  "WAITING",
  "TRADE IDENTIFIED",
  "EXECUTING",
  "ERROR",
];
