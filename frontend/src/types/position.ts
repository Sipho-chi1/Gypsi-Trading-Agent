/**
 * Positions types.
 *
 * Backend contract PENDING — these are the UI model only. The adapter in
 * `services/positionsService.ts` maps an eventual backend response into this
 * shape. NO invented backend fields; no fake data.
 */

export interface Position {
  symbol: string;
  quantity: number | null;
  side: "long" | "short" | null;
  avg_price: number | null;
  current_price: number | null;
  market_value: number | null;
  unrealized_pnl: number | null;
}
