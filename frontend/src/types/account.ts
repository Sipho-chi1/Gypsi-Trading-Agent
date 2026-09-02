/**
 * Account types.
 *
 * Backend contract PENDING — UI model only. Adapted by `services/accountService.ts`.
 */

export interface AccountSummary {
  balance: number | null;
  buying_power: number | null;
  portfolio_value: number | null;
  daily_pnl: number | null;
}
