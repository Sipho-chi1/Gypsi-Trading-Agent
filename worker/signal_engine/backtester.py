"""
Backtesting Engine for SMC/ICT Strategy — with Killzone A/B Testing.

Enables quantitative validation of the hardened SMC engine:
- A/B comparison of Killzone-restricted signals vs unrestricted signals.
- Multi-timeframe rolling simulation (Daily/H4 context + H1 structure + M5 entry).
- Performance metrics: Win rate, Profit factor, Net R-multiple, Max drawdown.
- Breakdown by Killzone (Asian, London, NY AM, London Close, Silver Bullet) and Setup POI.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Union
from zoneinfo import ZoneInfo

# Ensure worker directory is on sys.path
worker_dir = Path(__file__).resolve().parent.parent
if str(worker_dir) not in sys.path:
    sys.path.insert(0, str(worker_dir))

import numpy as np
import pandas as pd

from signal_engine import config
from signal_engine.instrument import Instrument, get_instrument
from signal_engine.smc_detector import analyse_pair, SMCSignal
from signal_engine.data_fetcher import generate_synthetic_candles


@dataclass
class BacktestTrade:
    pair: str
    entry_time: pd.Timestamp
    exit_time: Optional[pd.Timestamp]
    bias: str
    entry_price: float
    stop_loss: float
    take_profit: float
    rr_target: float
    result: str                 # "WIN", "LOSS", "OPEN"
    pnl_r: float                # PnL in R multiples (+RR on win, -1.0 on loss)
    confluence_score: int
    active_killzones: list[str]
    in_kill_zone: bool
    setup_type: str             # "OB", "Breaker", "FVG", "IFVG", "LiquidityGrab"
    amd_phase: str


@dataclass
class BacktestSummary:
    name: str
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_r: float
    profit_factor: float
    avg_r: float
    max_drawdown_r: float
    trades_by_killzone: dict[str, int] = field(default_factory=dict)
    winrate_by_killzone: dict[str, float] = field(default_factory=dict)
    trades_by_setup: dict[str, int] = field(default_factory=dict)


def run_backtest(
    instrument_or_pair: Union[str, Instrument] = "EURUSD",
    candles: Optional[dict[str, pd.DataFrame]] = None,
    killzone_filter: bool = False,
    min_confluence: int = 4,
    start_bar: int = 60,
) -> tuple[BacktestSummary, list[BacktestTrade]]:
    """
    Run backtest on multi-timeframe candles.
    If killzone_filter=True, trades are only executed when within an active ICT killzone.
    """
    inst = get_instrument(instrument_or_pair)
    
    if candles is None:
        # Generate synthetic test candles across Daily, H4, H1, M5
        now = datetime(2026, 6, 1, tzinfo=config.UTC_TZ)
        candles = {
            "D1": generate_synthetic_candles(inst.symbol, start_dt=now - timedelta(days=120), num_bars=120, timeframe="D1", seed=42),
            "H4": generate_synthetic_candles(inst.symbol, start_dt=now - timedelta(days=60), num_bars=360, timeframe="H4", seed=43),
            "H1": generate_synthetic_candles(inst.symbol, start_dt=now - timedelta(days=30), num_bars=720, timeframe="H1", seed=44),
            "M5": generate_synthetic_candles(inst.symbol, start_dt=now - timedelta(days=10), num_bars=2880, timeframe="M5", seed=45),
        }

    df_entry = candles.get("M5", candles.get("H1"))
    df_h1 = candles.get("H1")
    df_h4 = candles.get("H4")
    df_daily = candles.get("D1")

    trades: list[BacktestTrade] = []
    active_trade: Optional[BacktestTrade] = None

    # Step through entry timeframe bars
    total_bars = len(df_entry)
    step = 5  # Check every 5 bars (every 25m on M5)

    for i in range(start_bar, total_bars - 20, step):
        current_m5 = df_entry.iloc[:i]
        current_time = current_m5.index[-1] if isinstance(current_m5.index, pd.DatetimeIndex) else pd.to_datetime(current_m5["time"].iloc[-1])

        # Slice HTF candles up to current_time to strictly avoid lookahead bias
        slice_h1 = df_h1[df_h1.index <= current_time] if isinstance(df_h1.index, pd.DatetimeIndex) else df_h1
        slice_h4 = df_h4[df_h4.index <= current_time] if isinstance(df_h4.index, pd.DatetimeIndex) else df_h4
        slice_d1 = df_daily[df_daily.index <= current_time] if isinstance(df_daily.index, pd.DatetimeIndex) else df_daily

        if len(slice_h1) < 20 or len(slice_h4) < 10 or len(slice_d1) < 5:
            continue

        sim_candles = {
            "M5": current_m5.tail(120),
            "H1": slice_h1.tail(80),
            "H4": slice_h4.tail(60),
            "D1": slice_d1.tail(30),
        }

        # If a trade is currently open, simulate exit on subsequent bars
        if active_trade is not None:
            bar = df_entry.iloc[i]
            b_high, b_low = float(bar["high"]), float(bar["low"])

            if active_trade.bias == "bullish":
                if b_low <= active_trade.stop_loss:
                    active_trade.result = "LOSS"
                    active_trade.pnl_r = -1.0
                    active_trade.exit_time = current_time
                    trades.append(active_trade)
                    active_trade = None
                elif b_high >= active_trade.take_profit:
                    active_trade.result = "WIN"
                    active_trade.pnl_r = active_trade.rr_target
                    active_trade.exit_time = current_time
                    trades.append(active_trade)
                    active_trade = None
            else:
                if b_high >= active_trade.stop_loss:
                    active_trade.result = "LOSS"
                    active_trade.pnl_r = -1.0
                    active_trade.exit_time = current_time
                    trades.append(active_trade)
                    active_trade = None
                elif b_low <= active_trade.take_profit:
                    active_trade.result = "WIN"
                    active_trade.pnl_r = active_trade.rr_target
                    active_trade.exit_time = current_time
                    trades.append(active_trade)
                    active_trade = None
            continue

        # Temporarily override killzone gating in config if requested
        orig_kz_req = config.KILLZONE_REQUIRED
        config.KILLZONE_REQUIRED = killzone_filter
        try:
            signal: Optional[SMCSignal] = analyse_pair(inst, sim_candles)
        finally:
            config.KILLZONE_REQUIRED = orig_kz_req

        if signal is None:
            continue

        if signal.confluence_score < min_confluence:
            continue

        # Determine setup type label
        if signal.ob:
            setup = "OB"
        elif signal.breaker:
            setup = "Breaker"
        elif signal.fvg:
            setup = "FVG"
        elif signal.ifvg:
            setup = "IFVG"
        elif signal.liquidity_grab:
            setup = "LiquidityGrab"
        else:
            setup = "Structure"

        active_trade = BacktestTrade(
            pair=inst.symbol,
            entry_time=current_time,
            exit_time=None,
            bias=signal.bias,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            rr_target=signal.rr,
            result="OPEN",
            pnl_r=0.0,
            confluence_score=signal.confluence_score,
            active_killzones=signal.active_killzones,
            in_kill_zone=signal.in_kill_zone,
            setup_type=setup,
            amd_phase=signal.amd_phase,
        )

    # Compute summary metrics
    wins = [t for t in trades if t.result == "WIN"]
    losses = [t for t in trades if t.result == "LOSS"]
    total = len(wins) + len(losses)
    win_rate = (len(wins) / total * 100.0) if total > 0 else 0.0

    total_win_r = sum(t.pnl_r for t in wins)
    total_loss_r = abs(sum(t.pnl_r for t in losses))
    profit_factor = (total_win_r / total_loss_r) if total_loss_r > 0 else (total_win_r if total_win_r > 0 else 0.0)
    net_r = total_win_r - total_loss_r
    avg_r = (net_r / total) if total > 0 else 0.0

    # Max Drawdown in R
    cum_r = 0.0
    peak_r = 0.0
    max_dd = 0.0
    for t in trades:
        cum_r += t.pnl_r
        if cum_r > peak_r:
            peak_r = cum_r
        dd = peak_r - cum_r
        if dd > max_dd:
            max_dd = dd

    # Breakdown by Killzone
    kz_counts: dict[str, int] = {}
    kz_wins: dict[str, int] = {}
    for t in trades:
        kzs = t.active_killzones if t.active_killzones else ["None_Off_Session"]
        for kz in kzs:
            kz_counts[kz] = kz_counts.get(kz, 0) + 1
            if t.result == "WIN":
                kz_wins[kz] = kz_wins.get(kz, 0) + 1

    kz_winrates = {kz: (kz_wins.get(kz, 0) / count * 100.0) for kz, count in kz_counts.items()}

    # Breakdown by Setup
    setup_counts: dict[str, int] = {}
    for t in trades:
        setup_counts[t.setup_type] = setup_counts.get(t.setup_type, 0) + 1

    summary = BacktestSummary(
        name=f"Killzone_Filtered_{killzone_filter}",
        total_trades=total,
        wins=len(wins),
        losses=len(losses),
        win_rate=win_rate,
        total_r=net_r,
        profit_factor=profit_factor,
        avg_r=avg_r,
        max_drawdown_r=max_dd,
        trades_by_killzone=kz_counts,
        winrate_by_killzone=kz_winrates,
        trades_by_setup=setup_counts,
    )
    return summary, trades


def run_ab_comparison(symbol: str = "EURUSD") -> tuple[BacktestSummary, BacktestSummary]:
    """
    Run side-by-side A/B test comparing:
    - Plan A: Unrestricted (Killzone filtering OFF)
    - Plan B: Precision (Killzone filtering ON)
    """
    inst = get_instrument(symbol)
    now = datetime(2026, 6, 1, tzinfo=config.UTC_TZ)
    candles = {
        "D1": generate_synthetic_candles(inst.symbol, start_dt=now - timedelta(days=120), num_bars=120, timeframe="D1", seed=101),
        "H4": generate_synthetic_candles(inst.symbol, start_dt=now - timedelta(days=60), num_bars=360, timeframe="H4", seed=102),
        "H1": generate_synthetic_candles(inst.symbol, start_dt=now - timedelta(days=30), num_bars=720, timeframe="H1", seed=103),
        "M5": generate_synthetic_candles(inst.symbol, start_dt=now - timedelta(days=10), num_bars=2880, timeframe="M5", seed=104),
    }

    summary_unrestricted, _ = run_backtest(inst, candles=candles, killzone_filter=False)
    summary_restricted, _ = run_backtest(inst, candles=candles, killzone_filter=True)

    return summary_unrestricted, summary_restricted


def print_ab_report(summary_a: BacktestSummary, summary_b: BacktestSummary) -> None:
    """Print markdown formatted A/B test report."""
    print("\n" + "=" * 70)
    print("         SMC/ICT KILLZONE A/B BACKTEST PERFORMANCE REPORT")
    print("=" * 70)
    print(f"{'Metric':<25} | {'A: Killzone OFF':<18} | {'B: Killzone ON':<18}")
    print("-" * 70)
    print(f"{'Total Closed Trades':<25} | {summary_a.total_trades:<18} | {summary_b.total_trades:<18}")
    print(f"{'Win Rate (%)':<25} | {summary_a.win_rate:<18.2f}% | {summary_b.win_rate:<18.2f}%")
    print(f"{'Profit Factor':<25} | {summary_a.profit_factor:<18.2f} | {summary_b.profit_factor:<18.2f}")
    print(f"{'Total Net PnL (R)':<25} | {summary_a.total_r:<18.2f}R | {summary_b.total_r:<18.2f}R")
    print(f"{'Expectancy (Avg R)':<25} | {summary_a.avg_r:<18.2f}R | {summary_b.avg_r:<18.2f}R")
    print(f"{'Max Drawdown (R)':<25} | {summary_a.max_drawdown_r:<18.2f}R | {summary_b.max_drawdown_r:<18.2f}R")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SMC/ICT Backtester")
    parser.add_argument("--pair", type=str, default="EURUSD", help="Instrument / Forex pair")
    parser.add_argument("--ab-test", action="store_true", help="Run Killzone ON vs OFF A/B comparison")
    args = parser.parse_args()

    if args.ab_test:
        sum_a, sum_b = run_ab_comparison(args.pair)
        print_ab_report(sum_a, sum_b)
    else:
        summary, trades = run_backtest(args.pair, killzone_filter=True)
        print(f"\nBacktest Results for {args.pair} (Killzone ON):")
        print(f"Trades: {summary.total_trades}, Win Rate: {summary.win_rate:.1f}%, Net R: {summary.total_r:.2f}R, PF: {summary.profit_factor:.2f}")
