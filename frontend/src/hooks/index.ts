/**
 * Query hooks — the single place components read server state.
 * All hooks go through the centralized services layer; polling via refetchInterval.
 */

export const POLL = {
  agent: 5_000,
  positions: 15_000,
  account: 15_000,
  trades: 15_000,
  performance: 30_000,
  health: 30_000,
} as const;

export { useAgentStatus } from "./useAgentStatus";
export { useHealth } from "./useHealth";
export { useTrades, useTradeById } from "./useTrades";
export { usePerformance } from "./usePerformance";
export { usePositions } from "./usePositions";
export { useAccount } from "./useAccount";
export { useWatchlist } from "./useWatchlist";
export { useRoundTable } from "./useRoundTable";
