/**
 * Markets / watchlist types.
 *
 * Backend contract PENDING. The default display (SPY, QQQ, AAPL, MSFT, NVDA)
 * is a clearly-marked FRONTEND FALLBACK, never presented as backend data.
 */

export interface MarketSymbol {
  symbol: string;
  name?: string | null;
}

export interface Watchlist {
  /** Always a marked fallback until a real backend endpoint exists. */
  isFallback: boolean;
  symbols: MarketSymbol[];
}

/** Frontend fallback watchlist — clearly marked, replaced when backend lands. */
export const FALLBACK_WATCHLIST: MarketSymbol[] = [
  { symbol: "SPY", name: "SPDR S&P 500 ETF" },
  { symbol: "QQQ", name: "Invesco QQQ Trust" },
  { symbol: "AAPL", name: "Apple Inc." },
  { symbol: "MSFT", name: "Microsoft Corp." },
  { symbol: "NVDA", name: "NVIDIA Corp." },
];
