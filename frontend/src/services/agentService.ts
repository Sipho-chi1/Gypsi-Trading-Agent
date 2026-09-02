/**
 * Agent status — PENDING backend contract.
 *
 * Typed adapter pattern. Until the backend exposes agent state, we derive a
 * connectivity-only status from the CONFIRMED `/health` endpoint: reachable →
 * ONLINE, unreachable → OFFLINE. This never fabricates an agent state.
 *
 * ── INTEGRATION POINT ──────────────────────────────────────────────────
 * When the backend exposes a real agent-status endpoint, extend `getStatus()`
 * to read it and normalize the raw value via `normalizeAgentState()` below.
 * Backend values are NOT assumed to equal display strings.
 * ───────────────────────────────────────────────────────────────────────
 */

import { healthService } from "./healthService";
import type { AgentState, AgentStatus } from "../types/agent";

/** Display states (PRD). */
const DISPLAY_STATES: AgentState[] = [
  "ONLINE",
  "OFFLINE",
  "ANALYZING",
  "MONITORING",
  "WAITING",
  "TRADE IDENTIFIED",
  "EXECUTING",
  "ERROR",
];

/** INTEGRATION POINT: normalize a raw backend value into a display state. */
function normalizeAgentState(raw: unknown): AgentState {
  if (typeof raw !== "string") return "UNKNOWN";
  const upper = raw.trim().toUpperCase();
  // Match known display states and common snake/camel variants.
  if (DISPLAY_STATES.includes(upper as AgentState)) return upper as AgentState;
  const compact = upper.replace(/[^A-Z]/g, "");
  switch (compact) {
    case "ANALYZING":
    case "ANALYSIS":
    case "SCANNING":
      return "ANALYZING";
    case "TRADEIDENTIFIED":
    case "SIGNAL":
    case "OPPORTUNITY":
      return "TRADE IDENTIFIED";
    case "EXECUTING":
    case "EXECUTION":
    case "ORDER":
      return "EXECUTING";
    case "MONITORING":
    case "WATCHING":
      return "MONITORING";
    case "WAITING":
    case "IDLE":
    case "STANDBY":
      return "WAITING";
    case "ERROR":
    case "FAILED":
    case "OFFLINE":
      return "OFFLINE";
    case "ONLINE":
    case "READY":
    case "RUNNING":
      return "ONLINE";
    default:
      return "UNKNOWN";
  }
}

export const agentService = {
  /**
   * Fetch agent status.
   * Until a real endpoint exists, this reflects backend connectivity only.
   */
  async getStatus(): Promise<AgentStatus> {
    try {
      await healthService.check();
      return { state: "ONLINE", raw: null, connected: true };
    } catch {
      return { state: "OFFLINE", raw: null, connected: false };
    }
  },

  /** Exposed for the future adapter. */
  normalizeAgentState,
};
