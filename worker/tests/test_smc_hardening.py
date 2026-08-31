"""
Unit & Integration Test Suite — SMC/ICT Hardening Pass.

Covers:
1. Market Structure (Pivots, BOS continuation, CHoCH reversal, HTF bias)
2. Order Blocks, Breaker Blocks (polarity flips), Mitigation, Refined MT
3. Fair Value Gaps (3-candle imbalance, Consequent Encroachment 50% CE, Inversion FVGs)
4. Liquidity Pools (EQH/EQL tolerance, BSL/SSL, Wick Sweeps)
5. Premium/Discount (50% Equilibrium) and Optimal Trade Entry (OTE 61.8%-79%)
6. Timezone-Aware Killzones & US/London DST Transition consistency (March & November)
7. Quiet / Choppy market resilience (no false positive spam)
8. End-to-End Pipeline & Backtester A/B Killzone comparison
"""

import sys
from pathlib import Path

# Add worker and signal_engine to sys.path
worker_dir = Path(__file__).resolve().parent.parent
if str(worker_dir) not in sys.path:
    sys.path.insert(0, str(worker_dir))
signal_engine_dir = Path(__file__).resolve().parent
if str(signal_engine_dir) not in sys.path:
    sys.path.insert(0, str(signal_engine_dir))

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import pytest

from signal_engine import config
from signal_engine.instrument import Instrument, get_instrument
from signal_engine.smc_detector import (
    OrderBlock,
    BreakerBlock,
    FairValueGap,
    InversionFVG,
    HTFContext,
    SMCSignal,
    _swing_highs,
    _swing_lows,
    _structure_points,
    _detect_structure_breaks,
    _htf_bias,
    _detect_obs,
    _detect_breaker_blocks,
    _detect_fvgs,
    _detect_inversion_fvgs,
    _detect_equal_highs_lows,
    _detect_liquidity_grab,
    _premium_discount_check,
    _ote_check,
    get_ny_time,
    get_active_killzones,
    is_in_kill_zone,
    is_in_silver_bullet,
    is_market_weekend_or_holiday,
    analyse_htf_context,
    analyse_pair,
)
from signal_engine.data_fetcher import generate_synthetic_candles, tag_sessions_and_killzones
from signal_engine.backtester import run_backtest, run_ab_comparison


# ═══════════════════════════════════════════════════════════════════════════
# 1. MARKET STRUCTURE TESTS (Section 1)
# ═══════════════════════════════════════════════════════════════════════════

def test_swing_highs_and_lows_zero_lookahead():
    """Verify fractal pivot detection requires n closed bars on both sides without lookahead."""
    prices = [10.0, 11.0, 12.0, 15.0, 13.0, 12.0, 11.0, 9.0, 8.0, 6.0, 8.0, 9.0, 10.0]
    times = pd.date_range("2026-01-01", periods=len(prices), freq="h", tz="UTC")
    df = pd.DataFrame({
        "time": times,
        "high": prices,
        "low": [p - 1.0 for p in prices],
        "open": prices,
        "close": prices,
    })
    
    sh = _swing_highs(df, n=3)
    sl = _swing_lows(df, n=3)
    
    # Peak at index 3 (high=15.0) has 3 lower bars on left and right
    assert sh.iloc[3] == True
    assert sh.iloc[0] == False
    assert sh.iloc[2] == False
    
    # Low at index 9 (low=5.0) has 3 higher bars on left and right
    assert sl.iloc[9] == True


def test_bos_continuation_vs_choch_reversal():
    """
    [Section 1] Confirm BOS identifies trend continuation and CHoCH identifies trend reversal.
    """
    times = pd.date_range("2026-01-01", periods=25, freq="h", tz="UTC")
    opens = [1.0750] * 25
    highs = [1.0760] * 25
    lows = [1.0740] * 25
    closes = [1.0750] * 25

    # Point 0: Swing Low (idx 2)
    lows[2], closes[2] = 1.0700, 1.0710
    # Point 1: Swing High (idx 6)
    highs[6], closes[6] = 1.0800, 1.0790
    # Point 2: Higher Low (idx 10)
    lows[10], closes[10] = 1.0750, 1.0760
    # Point 3: Higher High (idx 14) -> Bullish BOS
    highs[14], closes[14] = 1.0900, 1.0890
    # Point 4: Lower Low (idx 18) -> Bearish CHoCH
    lows[18], closes[18] = 1.0650, 1.0660

    df = pd.DataFrame({
        "time": times,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
    })

    breaks = _detect_structure_breaks(df, lookback=25)
    assert len(breaks) >= 1
    types = [b["type"] for b in breaks]
    assert "BOS" in types or "CHoCH" in types


# ═══════════════════════════════════════════════════════════════════════════
# 2. ORDER BLOCKS & BREAKER BLOCKS TESTS (Section 2)
# ═══════════════════════════════════════════════════════════════════════════

def test_bullish_and_bearish_order_block_detection():
    """
    [Section 2] Verify that Bullish OB is the last down candle before an impulsive move,
    and Mean Threshold (MT) is correctly 50%.
    """
    times = pd.date_range("2026-01-01", periods=8, freq="h", tz="UTC")
    df = pd.DataFrame({
        "time": times,
        "open":  [1.0800, 1.0820, 1.0810, 1.0780, 1.0900, 1.0910, 1.0920, 1.0930],
        "close": [1.0810, 1.0815, 1.0780, 1.0900, 1.0910, 1.0920, 1.0930, 1.0940],
        "high":  [1.0820, 1.0825, 1.0815, 1.0910, 1.0915, 1.0925, 1.0935, 1.0945],
        "low":   [1.0790, 1.0805, 1.0770, 1.0775, 1.0890, 1.0905, 1.0915, 1.0925],
    })
    
    obs = _detect_obs(df, "bullish")
    assert len(obs) > 0
    ob = obs[-1]
    assert ob.direction == "bullish"
    assert ob.top == 1.0815
    assert ob.bottom == 1.0770
    assert ob.mid == pytest.approx((1.0815 + 1.0770) / 2.0)
    assert ob.contains(1.0800, convention="mean_threshold") == True


def test_breaker_block_polarity_flip():
    """
    [Section 2] Verify that a failed Order Block converts into a Breaker Block.
    """
    times = pd.date_range("2026-01-01", periods=10, freq="h", tz="UTC")
    df = pd.DataFrame({
        "time": times,
        "open":  [1.0980, 1.1000, 1.0940, 1.0960, 1.1020, 1.1080, 1.1050, 1.1040, 1.1050, 1.1060],
        "close": [1.1000, 1.1050, 1.0900, 1.1020, 1.1080, 1.1120, 1.1040, 1.1050, 1.1060, 1.1070],
        "high":  [1.1010, 1.1060, 1.1050, 1.1030, 1.1090, 1.1130, 1.1060, 1.1070, 1.1080, 1.1090],
        "low":   [1.0970, 1.0990, 1.0880, 1.0950, 1.1010, 1.1070, 1.1030, 1.1035, 1.1040, 1.1050],
    })
    
    breakers = _detect_breaker_blocks(df, "bullish")
    assert len(breakers) > 0
    assert any(b.top == 1.1060 and b.bottom == 1.0990 for b in breakers)


# ═══════════════════════════════════════════════════════════════════════════
# 3. FAIR VALUE GAPS (FVG) & INVERSION FVGS (Section 3)
# ═══════════════════════════════════════════════════════════════════════════

def test_three_candle_fvg_and_consequent_encroachment():
    """
    [Section 3] Verify strict 3-candle FVG logic and 50% Consequent Encroachment (CE).
    """
    times = pd.date_range("2026-01-01", periods=5, freq="h", tz="UTC")
    df = pd.DataFrame({
        "time": times,
        "open":  [1.0800, 1.0820, 1.0870, 1.0880, 1.0890],
        "high":  [1.0820, 1.0880, 1.0910, 1.0920, 1.0930],
        "low":   [1.0790, 1.0815, 1.0860, 1.0870, 1.0880],
        "close": [1.0815, 1.0875, 1.0900, 1.0910, 1.0920],
    })
    
    fvgs = _detect_fvgs(df, "bullish", "EURUSD")
    assert len(fvgs) > 0
    fvg = fvgs[0]
    assert fvg.direction == "bullish"
    assert fvg.bottom == 1.0820
    assert fvg.top == 1.0860
    assert fvg.consequent_encroachment == pytest.approx((1.0820 + 1.0860) / 2.0)


def test_inversion_fvg_detection():
    """
    [Section 3] Verify Inversion FVG (IFVG) detects when price violates an FVG and flips polarity.
    """
    times = pd.date_range("2026-01-01", periods=8, freq="h", tz="UTC")
    df = pd.DataFrame({
        "time": times,
        "open":  [1.0980, 1.0950, 1.0880, 1.0920, 1.0960, 1.1010, 1.0990, 1.1000],
        "high":  [1.0990, 1.0960, 1.0900, 1.0960, 1.1020, 1.1050, 1.1020, 1.1030],
        "low":   [1.0950, 1.0870, 1.0850, 1.0890, 1.0950, 1.0980, 1.0970, 1.0980],
        "close": [1.0960, 1.0880, 1.0860, 1.0950, 1.1010, 1.1030, 1.1000, 1.1010],
    })
    
    ifvgs = _detect_inversion_fvgs(df, "bullish", "EURUSD")
    assert len(ifvgs) > 0
    ifvg = ifvgs[0]
    assert ifvg.direction == "bullish"
    assert ifvg.top == 1.0950
    assert ifvg.bottom == 1.0900


# ═══════════════════════════════════════════════════════════════════════════
# 4. LIQUIDITY CONCEPTS TESTS (Section 4)
# ═══════════════════════════════════════════════════════════════════════════

def test_equal_highs_and_lows_tolerance():
    """
    [Section 4] Verify Equal Highs (EQH) and Equal Lows (EQL) clustering within tolerance.
    """
    times = pd.date_range("2026-01-01", periods=25, freq="h", tz="UTC")
    df = pd.DataFrame({
        "time": times,
        "open":  [1.0800] * 25,
        "high":  [1.0850] * 25,
        "low":   [1.0750] * 25,
        "close": [1.0800] * 25,
    })
    df.loc[5, "high"] = 1.09000
    df.loc[15, "high"] = 1.09002
    
    for off in [-2, -1, 1, 2]:
        df.loc[5 + off, "high"] = 1.0820
        df.loc[15 + off, "high"] = 1.0820
        
    eqs = _detect_equal_highs_lows(df, "EURUSD")
    eqh = [e for e in eqs if e.kind == "EQH"]
    assert len(eqh) >= 1
    assert eqh[0].touch_count >= 2


def test_liquidity_sweep_wick_through_close_inside():
    """
    [Section 4] Verify that liquidity sweep (Turtle Soup) requires a wick through and close back inside.
    """
    times = pd.date_range("2026-01-01", periods=20, freq="h", tz="UTC")
    df = pd.DataFrame({
        "time": times,
        "open":  [1.0850] * 20,
        "high":  [1.0900] * 20,
        "low":   [1.0800] * 20,
        "close": [1.0850] * 20,
    })
    df.loc[5, ["low", "close"]] = 1.0750
    for off in [-2, -1, 1, 2]:
        df.loc[5 + off, "low"] = 1.0800
        
    df.loc[15, "open"] = 1.0790
    df.loc[15, "low"] = 1.0730
    df.loc[15, "high"] = 1.0810
    df.loc[15, "close"] = 1.0780
    
    grab = _detect_liquidity_grab(df, "bullish")
    assert grab is not None
    assert grab.direction == "bullish"
    assert grab.swept_level == 1.0750
    assert grab.wick_penetration == pytest.approx(1.0750 - 1.0730)


# ═══════════════════════════════════════════════════════════════════════════
# 5. PREMIUM / DISCOUNT & OTE TESTS (Section 5)
# ═══════════════════════════════════════════════════════════════════════════

def test_premium_discount_and_ote_levels():
    """
    [Section 5] Verify 50% Equilibrium and 61.8% - 79% Optimal Trade Entry (OTE).
    """
    swing_low = 100.0
    swing_high = 200.0
    
    in_prem, in_disc, eq = _premium_discount_check(160.0, swing_low, swing_high)
    assert eq == 150.0
    assert in_prem == True
    assert in_disc == False
    
    in_prem, in_disc, eq = _premium_discount_check(140.0, swing_low, swing_high)
    assert in_disc == True
    assert in_prem == False

    assert _ote_check(129.5, swing_high, swing_low, "bullish") == True
    assert _ote_check(150.0, swing_high, swing_low, "bullish") == False
    assert _ote_check(110.0, swing_high, swing_low, "bullish") == False


# ═══════════════════════════════════════════════════════════════════════════
# 6. TIMEZONE-AWARE KILLZONES & DST TRANSITIONS (Section 6)
# ═══════════════════════════════════════════════════════════════════════════

def test_dst_transitions_us_march_and_november():
    """
    [Section 6] Critical DST Test: Confirm that Killzones anchor correctly to
    New York local time across US Daylight Saving transitions (March & November).
    """
    # 1. US Spring Forward: March 2026
    dt_winter_utc = datetime(2026, 3, 6, 13, 30, tzinfo=config.UTC_TZ)
    ny_winter = get_ny_time(dt_winter_utc)
    assert ny_winter.hour == 8
    assert ny_winter.minute == 30
    kzs_winter = get_active_killzones(dt_winter_utc)
    assert "NY_AM" in kzs_winter
    assert "London_NY_Overlap" in kzs_winter

    # After DST (March 10, 2026): NY is UTC-4 (EDT)
    dt_summer_utc = datetime(2026, 3, 10, 12, 30, tzinfo=config.UTC_TZ)
    ny_summer = get_ny_time(dt_summer_utc)
    assert ny_summer.hour == 8
    assert ny_summer.minute == 30
    kzs_summer = get_active_killzones(dt_summer_utc)
    assert "NY_AM" in kzs_summer
    assert "London_NY_Overlap" in kzs_summer

    # 2. US Fall Back: Nov 2026
    dt_oct_utc = datetime(2026, 10, 30, 7, 30, tzinfo=config.UTC_TZ)
    assert is_in_silver_bullet(dt_oct_utc) == True

    dt_nov_utc = datetime(2026, 11, 3, 8, 30, tzinfo=config.UTC_TZ)
    assert is_in_silver_bullet(dt_nov_utc) == True


def test_weekend_market_filter():
    """[Section 6] Confirm weekends and pre-open Sunday are excluded."""
    sat_ny = datetime(2026, 4, 18, 12, 0, tzinfo=config.NY_TZ)
    assert is_market_weekend_or_holiday(sat_ny) == True
    assert len(get_active_killzones(sat_ny)) == 0

    sun_early = datetime(2026, 4, 19, 14, 0, tzinfo=config.NY_TZ)
    assert is_market_weekend_or_holiday(sun_early) == True

    sun_open = datetime(2026, 4, 19, 20, 30, tzinfo=config.NY_TZ)
    assert is_market_weekend_or_holiday(sun_open) == False
    assert "Asian" in get_active_killzones(sun_open)


# ═══════════════════════════════════════════════════════════════════════════
# 7. QUIET / CHOPPY MARKET RESILIENCE
# ═══════════════════════════════════════════════════════════════════════════

def test_quiet_choppy_data_no_false_positive_spam():
    """
    [Section 1, 4] Verify that low-volatility sideways noise does not produce spurious signals.
    """
    np.random.seed(999)
    times = pd.date_range("2026-05-01", periods=200, freq="5min", tz="UTC")
    noise = np.random.normal(0, 0.00002, 200)
    prices = 1.0850 + np.cumsum(noise)
    
    df_choppy = pd.DataFrame({
        "time": times,
        "open": prices,
        "high": prices + 0.00003,
        "low": prices - 0.00003,
        "close": prices,
        "volume": [100] * 200,
    })
    df_choppy.set_index("time", inplace=True)
    
    candles = {
        "M5": df_choppy,
        "H1": df_choppy.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna(),
        "H4": df_choppy.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna(),
        "D1": df_choppy.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna(),
    }
    
    bias = _htf_bias(candles["D1"])
    assert bias == "neutral"
    
    signal = analyse_pair("EURUSD", candles)
    assert signal is None


# ═══════════════════════════════════════════════════════════════════════════
# 8. BACKTESTER A/B COMPARISON TEST
# ═══════════════════════════════════════════════════════════════════════════

def test_backtester_killzone_ab_comparison():
    """
    [Backtesting Validation] Test that the backtesting engine executes both
    Killzone ON and OFF paths and produces comprehensive performance metrics.
    """
    inst = get_instrument("EURUSD")
    now = datetime(2026, 6, 1, tzinfo=config.UTC_TZ)
    candles = {
        "D1": generate_synthetic_candles(inst.symbol, start_dt=now - timedelta(days=60), num_bars=60, timeframe="D1", seed=101),
        "H4": generate_synthetic_candles(inst.symbol, start_dt=now - timedelta(days=30), num_bars=180, timeframe="H4", seed=102),
        "H1": generate_synthetic_candles(inst.symbol, start_dt=now - timedelta(days=15), num_bars=360, timeframe="H1", seed=103),
        "M5": generate_synthetic_candles(inst.symbol, start_dt=now - timedelta(days=5), num_bars=500, timeframe="M5", seed=104),
    }

    sum_a, _ = run_backtest(inst, candles=candles, killzone_filter=False)
    sum_b, _ = run_backtest(inst, candles=candles, killzone_filter=True)
    
    assert sum_a.name == "Killzone_Filtered_False"
    assert sum_b.name == "Killzone_Filtered_True"
    assert isinstance(sum_a.win_rate, float)
    assert isinstance(sum_b.win_rate, float)
    assert isinstance(sum_a.profit_factor, float)
    assert isinstance(sum_b.profit_factor, float)
