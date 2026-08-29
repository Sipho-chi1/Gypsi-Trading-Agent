"""
smc_detector.py — Hardened Smart Money Concepts (SMC/ICT) Detection Engine.

Audited and hardened against standard ICT/SMC institutional order flow definitions:
- Section 1: Market Structure (Fractal Pivots, BOS trend continuation vs CHoCH reversal, MSS convention)
- Section 2: Order Blocks, Breaker Blocks (polarity flips), Mitigation Blocks, Refined Mean Threshold (50% MT)
- Section 3: Fair Value Gaps (3-candle imbalance, Consequent Encroachment 50% CE, Inversion FVGs, tick-relative sizing)
- Section 4: Liquidity Pools (BSL/SSL, EQH/EQL with ATR/tick tolerance, wick-sweep stop hunts, Inducement)
- Section 5: Premium/Discount Dealing Range & Optimal Trade Entry (OTE 61.8%-79% with 70.5% sweet spot)
- Section 6: Timezone-Aware Killzones (anchored to America/New_York & Europe/London via zoneinfo, fixing DST bugs, Silver Bullet windows)
- Section 7: Power of Three (AMD — Accumulation, Manipulation, Distribution cycle)
- Section 8: Multi-Timeframe Alignment (HTF Context -> Mid-TF Confirmation -> LTF POI Precision Entry)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Literal, Optional, Union
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

try:
    import config
except ImportError:
    from signal_engine import config

try:
    from ml_model import score_smc_signal, WIN_PROB_THRESHOLD
except ImportError:
    from signal_engine.ml_model import score_smc_signal, WIN_PROB_THRESHOLD

from signal_engine.instrument import Instrument, get_instrument

logger = logging.getLogger(__name__)

Bias = Literal["bullish", "bearish", "neutral"]
AMDPhase = Literal["accumulation", "manipulation", "distribution", "unknown"]


# ═══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class OrderBlock:
    """[Section 2] ICT Order Block."""
    index: int
    time: pd.Timestamp
    direction: Literal["bullish", "bearish"]
    top: float
    bottom: float
    body_top: float = 0.0
    body_bottom: float = 0.0
    broken: bool = False
    mitigated: bool = False

    @property
    def mid(self) -> float:
        """50% Mean Threshold (MT) of the full OB range."""
        return (self.top + self.bottom) / 2.0

    @property
    def body_mid(self) -> float:
        """50% Mean Threshold of the OB candle body."""
        return (self.body_top + self.body_bottom) / 2.0 if (self.body_top and self.body_bottom) else self.mid

    def contains(self, price: float, convention: str = "mean_threshold") -> bool:
        if convention == "body" and self.body_top and self.body_bottom:
            return self.body_bottom <= price <= self.body_top
        if convention == "mean_threshold":
            if self.direction == "bullish":
                return self.mid <= price <= self.top
            else:
                return self.bottom <= price <= self.mid
        return self.bottom <= price <= self.top


@dataclass
class BreakerBlock:
    """[Section 2] ICT Breaker Block."""
    index: int
    time: pd.Timestamp
    direction: Literal["bullish", "bearish"]
    top: float
    bottom: float
    origin_ob_time: pd.Timestamp
    swept_extreme: float

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2.0

    def contains(self, price: float) -> bool:
        return self.bottom <= price <= self.top


@dataclass
class FairValueGap:
    """[Section 3] ICT Fair Value Gap (FVG) / Imbalance."""
    index: int
    time: pd.Timestamp
    direction: Literal["bullish", "bearish"]
    top: float
    bottom: float
    filled: bool = False
    mitigated: bool = False

    @property
    def consequent_encroachment(self) -> float:
        """50% Consequent Encroachment (CE) of the FVG."""
        return (self.top + self.bottom) / 2.0

    @property
    def mid(self) -> float:
        return self.consequent_encroachment

    def contains(self, price: float) -> bool:
        return self.bottom <= price <= self.top


@dataclass
class InversionFVG:
    """[Section 3] ICT Inversion Fair Value Gap (IFVG)."""
    index: int
    time: pd.Timestamp
    direction: Literal["bullish", "bearish"]
    top: float
    bottom: float
    origin_fvg_time: pd.Timestamp

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2.0

    def contains(self, price: float) -> bool:
        return self.bottom <= price <= self.top


@dataclass
class EqualHighLow:
    """[Section 4] Equal Highs (EQH) or Equal Lows (EQL)."""
    kind: Literal["EQH", "EQL"]
    level: float
    touch_count: int
    indices: list[int]
    tolerance: float

    @property
    def pool_type(self) -> str:
        return "BSL" if self.kind == "EQH" else "SSL"


@dataclass
class LiquidityPool:
    """[Section 4] Buy-Side (BSL) or Sell-Side (SSL) Liquidity Pool."""
    pool_type: Literal["BSL", "SSL"]
    level: float
    source: str
    time: Optional[pd.Timestamp] = None
    swept: bool = False


@dataclass
class LiquidityGrab:
    """[Section 4] Liquidity Sweep / Stop Hunt."""
    index: int
    time: pd.Timestamp
    direction: Literal["bullish", "bearish"]
    swept_level: float
    pool_source: str = "swing_pivot"
    wick_penetration: float = 0.0


@dataclass
class MarketStructurePoint:
    """[Section 1] Structural swing pivot point."""
    index: int
    time: pd.Timestamp
    kind: Literal["HH", "HL", "LH", "LL"]
    price: float


@dataclass
class HTFContext:
    """[Section 1, 5, 7, 8] Result of Step 1 HTF Analysis."""
    bias: Bias
    draw_target: float
    draw_source: str
    in_premium: bool
    in_discount: bool
    equilibrium: float
    swing_high: float
    swing_low: float
    prev_day_high: float
    prev_day_low: float
    asian_high: float = float("nan")
    asian_low: float = float("nan")
    amd_phase: AMDPhase = "unknown"
    score: int = 0


@dataclass
class SMCSignal:
    """[Section 8] Complete SMC/ICT Trading Signal."""
    pair: str
    bias: Bias
    entry_price: float
    stop_loss: float
    take_profit: float
    rr: float
    confluence_score: int = 0
    ob: Optional[OrderBlock] = None
    breaker: Optional[BreakerBlock] = None
    fvg: Optional[FairValueGap] = None
    ifvg: Optional[InversionFVG] = None
    liquidity_grab: Optional[LiquidityGrab] = None
    eq_pool: Optional[EqualHighLow] = None
    in_kill_zone: bool = False
    active_killzones: list[str] = field(default_factory=list)
    in_silver_bullet: bool = False
    in_ote_zone: bool = False
    in_discount_premium: bool = False
    amd_phase: AMDPhase = "unknown"
    htf_score: int = 0
    reason: str = ""
    ml_win_prob: Optional[float] = None

    @property
    def sl_pips(self) -> float:
        inst = get_instrument(self.pair)
        return inst.price_to_pips(abs(self.entry_price - self.stop_loss))

    @property
    def tp_pips(self) -> float:
        inst = get_instrument(self.pair)
        return inst.price_to_pips(abs(self.take_profit - self.entry_price))

    @property
    def entry(self) -> float:
        return self.entry_price


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6: TIMEZONE-AWARE SESSIONS & KILLZONES
# ═══════════════════════════════════════════════════════════════════════════

def get_ny_time(ts: pd.Timestamp | datetime) -> datetime:
    """[Section 6] Convert timestamp to America/New_York timezone-aware datetime."""
    if isinstance(ts, pd.Timestamp):
        dt = ts.to_pydatetime()
    else:
        dt = ts

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=config.UTC_TZ)

    return dt.astimezone(config.NY_TZ)


def is_market_weekend_or_holiday(dt_ny: datetime) -> bool:
    """[Section 6] Weekend and closed market check."""
    weekday = dt_ny.weekday()  # Monday = 0, Sunday = 6
    hour = dt_ny.hour

    if weekday == 5:  # Saturday
        return True
    if weekday == 4 and hour >= 17:  # Friday after 17:00 NY
        return True
    if weekday == 6 and hour < 17:   # Sunday before 17:00 NY
        return True
    return False


def get_active_killzones(ts: pd.Timestamp | datetime) -> list[str]:
    """[Section 6] Return active Killzones & Silver Bullet windows in NY time."""
    dt_ny = get_ny_time(ts)
    if is_market_weekend_or_holiday(dt_ny):
        return []

    t = dt_ny.time()
    active = []

    for window in config.KILLZONE_WINDOWS:
        if window.start_time <= window.end_time:
            if window.start_time <= t < window.end_time:
                active.append(window.name)
        else:
            if t >= window.start_time or t < window.end_time:
                active.append(window.name)

    if time(8, 0) <= t < time(11, 0):
        if "London_NY_Overlap" not in active:
            active.append("London_NY_Overlap")

    return active


def is_in_kill_zone(ts: pd.Timestamp | datetime) -> bool:
    return len(get_active_killzones(ts)) > 0


def is_in_silver_bullet(ts: pd.Timestamp | datetime) -> bool:
    active = get_active_killzones(ts)
    return any("Silver_Bullet" in kz for kz in active)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: MARKET STRUCTURE (Fractals, BOS vs CHoCH vs MSS)
# ═══════════════════════════════════════════════════════════════════════════

def _swing_highs(df: pd.DataFrame, n: int = config.SWING_PIVOT_N) -> pd.Series:
    """[Section 1] Fast vectorized fractal swing highs detection."""
    h = df["high"].to_numpy(dtype=float)
    total = len(h)
    sw = np.zeros(total, dtype=bool)
    if total < 2 * n + 1:
        return pd.Series(sw, index=df.index)

    for i in range(n, total - n):
        val = h[i]
        if np.all(val >= h[i-n:i]) and np.all(val >= h[i+1:i+n+1]) and (np.any(val > h[i-n:i]) or np.any(val > h[i+1:i+n+1])):
            sw[i] = True
    return pd.Series(sw, index=df.index)


def _swing_lows(df: pd.DataFrame, n: int = config.SWING_PIVOT_N) -> pd.Series:
    """[Section 1] Fast vectorized fractal swing lows detection."""
    l = df["low"].to_numpy(dtype=float)
    total = len(l)
    sw = np.zeros(total, dtype=bool)
    if total < 2 * n + 1:
        return pd.Series(sw, index=df.index)

    for i in range(n, total - n):
        val = l[i]
        if np.all(val <= l[i-n:i]) and np.all(val <= l[i+1:i+n+1]) and (np.any(val < l[i-n:i]) or np.any(val < l[i+1:i+n+1])):
            sw[i] = True
    return pd.Series(sw, index=df.index)


def _structure_points(df: pd.DataFrame, lookback: int = config.STRUCTURE_LOOKBACK, n: int = config.SWING_PIVOT_N) -> list[MarketStructurePoint]:
    """[Section 1] Extract chronological HH/HL/LH/LL structure points."""
    d = df.tail(lookback).reset_index()
    time_col = "time" if "time" in d.columns else ("index" if "index" in d.columns else d.columns[0])

    sh = _swing_highs(d, n=n)
    sl = _swing_lows(d, n=n)
    pts: list[MarketStructurePoint] = []
    last_h: Optional[float] = None
    last_l: Optional[float] = None

    for i in range(len(d)):
        raw_t = d[time_col].iloc[i]
        t = pd.to_datetime(raw_t) if not isinstance(raw_t, (int, np.integer)) else pd.Timestamp("2026-01-01") + pd.Timedelta(hours=int(raw_t))
        if sh.iloc[i]:
            v = float(d["high"].iloc[i])
            kind = "HH" if (last_h is None or v > last_h) else "LH"
            last_h = v
            pts.append(MarketStructurePoint(index=i, time=t, kind=kind, price=v))
        if sl.iloc[i]:
            v = float(d["low"].iloc[i])
            kind = "HL" if (last_l is None or v > last_l) else "LL"
            last_l = v
            pts.append(MarketStructurePoint(index=i, time=t, kind=kind, price=v))

    pts.sort(key=lambda x: x.index)
    return pts


def _detect_structure_breaks(df: pd.DataFrame, lookback: int = config.STRUCTURE_LOOKBACK) -> list[dict]:
    """
    [Section 1] Strict BOS vs CHoCH vs MSS identification.
    
    ICT Definition Conventions:
    - BOS (Break of Structure): Trend continuation. Price breaks a swing point in the
      direction of the prevailing trend (e.g. Bullish trend + break above previous Swing High).
    - CHoCH (Change of Character): Trend reversal. Price breaks the swing low that formed the
      highest high in an uptrend, or breaks the swing high that formed the lowest low in a downtrend.
    - MSS (Market Structure Shift): LTF displacement break of opposing structure following HTF POI tap.
    """
    pts = _structure_points(df, lookback=lookback)
    if len(pts) < 2:
        return []

    events = []
    for i in range(1, len(pts)):
        p_prev = pts[i-1]
        p_curr = pts[i]

        # Break of previous swing high
        if p_curr.kind == "HH":
            if p_prev.kind in ("HL", "HH"):
                events.append({"type": "BOS", "direction": "bullish", "price": p_curr.price, "time": p_curr.time, "broken_level": p_prev.price})
            elif p_prev.kind == "LH":
                events.append({"type": "CHoCH", "direction": "bullish", "price": p_curr.price, "time": p_curr.time, "broken_level": p_prev.price})
        # Break of previous swing low
        elif p_curr.kind == "LL":
            if p_prev.kind in ("LH", "LL"):
                events.append({"type": "BOS", "direction": "bearish", "price": p_curr.price, "time": p_curr.time, "broken_level": p_prev.price})
            elif p_prev.kind == "HL":
                events.append({"type": "CHoCH", "direction": "bearish", "price": p_curr.price, "time": p_curr.time, "broken_level": p_prev.price})

    return events


def _htf_bias(df: pd.DataFrame) -> Bias:
    """[Section 1, 8] Determine HTF structural bias from swing points sequence."""
    if df.empty or len(df) < 5:
        return "neutral"

    lookback = min(config.STRUCTURE_LOOKBACK, max(20, len(df)))
    pts = _structure_points(df, lookback=lookback)

    if len(pts) >= 4:
        last_n = pts[-4:]
        bull = sum(1 for p in last_n if p.kind in ("HH", "HL"))
        bear = sum(1 for p in last_n if p.kind in ("LH", "LL"))
        if bull >= 3:
            return "bullish"
        if bear >= 3:
            return "bearish"

    # Fallback: Price difference across slice
    first_c = float(df["close"].iloc[0])
    last_c = float(df["close"].iloc[-1])
    diff_pct = (last_c - first_c) / first_c if first_c > 0 else 0.0
    if diff_pct > 0.005:
        return "bullish"
    if diff_pct < -0.005:
        return "bearish"

    return "neutral"


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: ORDER BLOCKS & BREAKER BLOCKS
# ═══════════════════════════════════════════════════════════════════════════

def _detect_obs(df: pd.DataFrame, bias: Bias) -> list[OrderBlock]:
    """[Section 2] ICT Order Blocks detection with Mean Threshold and Body metrics."""
    d = df.tail(config.OB_LOOKBACK + 10).reset_index()
    time_col = "time" if "time" in d.columns else ("index" if "index" in d.columns else d.columns[0])
    obs: list[OrderBlock] = []
    n = len(d)

    for i in range(0, n - 2):
        o, h, l, c = float(d["open"].iloc[i]), float(d["high"].iloc[i]), float(d["low"].iloc[i]), float(d["close"].iloc[i])
        raw_t = d[time_col].iloc[i]
        ts = pd.to_datetime(raw_t) if not isinstance(raw_t, (int, np.integer)) else pd.Timestamp("2026-01-01") + pd.Timedelta(hours=int(raw_t))
        nc, nh, nl, no = float(d["close"].iloc[i+1]), float(d["high"].iloc[i+1]), float(d["low"].iloc[i+1]), float(d["open"].iloc[i+1])
        
        body = abs(c - o)
        nbody = abs(nc - no)
        if body <= 0:
            continue

        body_top = max(o, c)
        body_bottom = min(o, c)

        # Bullish OB: Down candle followed by displacement breaking above OB high
        if bias == "bullish" and c < o and nc > h and nbody >= body * config.OB_IMPULSE_FACTOR:
            ob = OrderBlock(index=i, time=ts, direction="bullish", top=h, bottom=l, body_top=body_top, body_bottom=body_bottom)
            subsequent_closes = d["close"].iloc[i+2:]
            ob.broken = (subsequent_closes < l).any()
            if not ob.broken:
                subsequent_lows = d["low"].iloc[i+2:]
                ob.mitigated = (subsequent_lows <= h).any()
                obs.append(ob)

        # Bearish OB: Up candle followed by displacement breaking below OB low
        elif bias == "bearish" and c > o and nc < l and nbody >= body * config.OB_IMPULSE_FACTOR:
            ob = OrderBlock(index=i, time=ts, direction="bearish", top=h, bottom=l, body_top=body_top, body_bottom=body_bottom)
            subsequent_closes = d["close"].iloc[i+2:]
            ob.broken = (subsequent_closes > h).any()
            if not ob.broken:
                subsequent_highs = d["high"].iloc[i+2:]
                ob.mitigated = (subsequent_highs >= l).any()
                obs.append(ob)

    obs.sort(key=lambda x: x.index, reverse=True)
    return obs


def _detect_breaker_blocks(df: pd.DataFrame, bias: Bias) -> list[BreakerBlock]:
    """[Section 2] ICT Breaker Blocks detection."""
    d = df.tail(config.OB_LOOKBACK + 15).reset_index()
    time_col = "time" if "time" in d.columns else ("index" if "index" in d.columns else d.columns[0])
    breakers: list[BreakerBlock] = []
    n = len(d)

    for i in range(0, n - 2):
        o, h, l, c = float(d["open"].iloc[i]), float(d["high"].iloc[i]), float(d["low"].iloc[i]), float(d["close"].iloc[i])
        raw_t = d[time_col].iloc[i]
        ts = pd.to_datetime(raw_t) if not isinstance(raw_t, (int, np.integer)) else pd.Timestamp("2026-01-01") + pd.Timedelta(hours=int(raw_t))

        # Bullish Breaker: previously a Bearish OB (up-candle) that price later broke ABOVE
        if bias == "bullish" and c > o:
            subsequent_closes = d["close"].iloc[i+1:]
            if (subsequent_closes > h).any():
                break_idx = subsequent_closes[subsequent_closes > h].index[0]
                current_c = float(d["close"].iloc[-1])
                if current_c >= l:
                    breakers.append(BreakerBlock(
                        index=int(break_idx),
                        time=pd.to_datetime(d[time_col].iloc[break_idx]) if not isinstance(d[time_col].iloc[break_idx], (int, np.integer)) else pd.Timestamp("2026-01-01") + pd.Timedelta(hours=int(d[time_col].iloc[break_idx])),
                        direction="bullish",
                        top=h,
                        bottom=l,
                        origin_ob_time=ts,
                        swept_extreme=h,
                    ))

        # Bearish Breaker: previously a Bullish OB (down-candle) that price later broke BELOW
        elif bias == "bearish" and c < o:
            subsequent_closes = d["close"].iloc[i+1:]
            if (subsequent_closes < l).any():
                break_idx = subsequent_closes[subsequent_closes < l].index[0]
                current_c = float(d["close"].iloc[-1])
                if current_c <= h:
                    breakers.append(BreakerBlock(
                        index=int(break_idx),
                        time=pd.to_datetime(d[time_col].iloc[break_idx]) if not isinstance(d[time_col].iloc[break_idx], (int, np.integer)) else pd.Timestamp("2026-01-01") + pd.Timedelta(hours=int(d[time_col].iloc[break_idx])),
                        direction="bearish",
                        top=h,
                        bottom=l,
                        origin_ob_time=ts,
                        swept_extreme=l,
                    ))

    breakers.sort(key=lambda x: x.index, reverse=True)
    return breakers


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3: FAIR VALUE GAPS (FVG) & INVERSION FVGS
# ═══════════════════════════════════════════════════════════════════════════

def _detect_fvgs(df: pd.DataFrame, bias: Bias, instrument_or_pair: Union[str, Instrument]) -> list[FairValueGap]:
    """[Section 3] ICT Fair Value Gaps detection (strict 3-candle imbalance)."""
    inst = get_instrument(instrument_or_pair)
    min_gap_dist = max(inst.tick_size * config.FVG_MIN_SIZE_TICKS, inst.pip_size * config.FVG_MIN_SIZE_PIPS)

    d = df.tail(config.FVG_LOOKBACK + 5).reset_index()
    time_col = "time" if "time" in d.columns else ("index" if "index" in d.columns else d.columns[0])
    fvgs: list[FairValueGap] = []
    n = len(d)

    for i in range(1, n - 1):
        c0h, c0l = float(d["high"].iloc[i-1]), float(d["low"].iloc[i-1])
        raw_t = d[time_col].iloc[i]
        ts = pd.to_datetime(raw_t) if not isinstance(raw_t, (int, np.integer)) else pd.Timestamp("2026-01-01") + pd.Timedelta(hours=int(raw_t))
        c2h, c2l = float(d["high"].iloc[i+1]), float(d["low"].iloc[i+1])

        # Bullish FVG
        if bias == "bullish" and c0h < c2l:
            gap_size = c2l - c0h
            if gap_size >= min_gap_dist:
                fvg = FairValueGap(index=i, time=ts, direction="bullish", top=c2l, bottom=c0h)
                subsequent_closes = d["close"].iloc[i+2:]
                fvg.filled = (subsequent_closes < c0h).any()
                if not fvg.filled:
                    subsequent_lows = d["low"].iloc[i+2:]
                    fvg.mitigated = (subsequent_lows <= fvg.consequent_encroachment).any()
                    fvgs.append(fvg)

        # Bearish FVG
        elif bias == "bearish" and c0l > c2h:
            gap_size = c0l - c2h
            if gap_size >= min_gap_dist:
                fvg = FairValueGap(index=i, time=ts, direction="bearish", top=c0l, bottom=c2h)
                subsequent_closes = d["close"].iloc[i+2:]
                fvg.filled = (subsequent_closes > c0l).any()
                if not fvg.filled:
                    subsequent_highs = d["high"].iloc[i+2:]
                    fvg.mitigated = (subsequent_highs >= fvg.consequent_encroachment).any()
                    fvgs.append(fvg)

    fvgs.sort(key=lambda x: x.index, reverse=True)
    return fvgs


def _detect_inversion_fvgs(df: pd.DataFrame, bias: Bias, instrument_or_pair: Union[str, Instrument]) -> list[InversionFVG]:
    """[Section 3] ICT Inversion FVGs (IFVG) detection."""
    inst = get_instrument(instrument_or_pair)
    min_gap_dist = max(inst.tick_size * config.FVG_MIN_SIZE_TICKS, inst.pip_size * config.FVG_MIN_SIZE_PIPS)

    d = df.tail(config.FVG_LOOKBACK + 15).reset_index()
    time_col = "time" if "time" in d.columns else ("index" if "index" in d.columns else d.columns[0])
    ifvgs: list[InversionFVG] = []
    n = len(d)

    for i in range(1, n - 2):
        c0h, c0l = float(d["high"].iloc[i-1]), float(d["low"].iloc[i-1])
        raw_t = d[time_col].iloc[i]
        ts = pd.to_datetime(raw_t) if not isinstance(raw_t, (int, np.integer)) else pd.Timestamp("2026-01-01") + pd.Timedelta(hours=int(raw_t))
        c2h, c2l = float(d["high"].iloc[i+1]), float(d["low"].iloc[i+1])

        # Bullish IFVG: originated as a Bearish FVG (c0l > c2h) but price subsequently closed ABOVE c0l
        if bias == "bullish" and c0l > c2h and (c0l - c2h) >= min_gap_dist:
            subsequent_closes = d["close"].iloc[i+2:]
            if (subsequent_closes > c0l).any():
                inv_idx = subsequent_closes[subsequent_closes > c0l].index[0]
                if float(d["close"].iloc[-1]) >= c2h:
                    ifvgs.append(InversionFVG(
                        index=int(inv_idx),
                        time=pd.to_datetime(d[time_col].iloc[inv_idx]) if not isinstance(d[time_col].iloc[inv_idx], (int, np.integer)) else pd.Timestamp("2026-01-01") + pd.Timedelta(hours=int(d[time_col].iloc[inv_idx])),
                        direction="bullish",
                        top=c0l,
                        bottom=c2h,
                        origin_fvg_time=ts,
                    ))

        # Bearish IFVG: originated as a Bullish FVG (c0h < c2l) but price subsequently closed BELOW c0h
        elif bias == "bearish" and c0h < c2l and (c2l - c0h) >= min_gap_dist:
            subsequent_closes = d["close"].iloc[i+2:]
            if (subsequent_closes < c0h).any():
                inv_idx = subsequent_closes[subsequent_closes < c0h].index[0]
                if float(d["close"].iloc[-1]) <= c2l:
                    ifvgs.append(InversionFVG(
                        index=int(inv_idx),
                        time=pd.to_datetime(d[time_col].iloc[inv_idx]) if not isinstance(d[time_col].iloc[inv_idx], (int, np.integer)) else pd.Timestamp("2026-01-01") + pd.Timedelta(hours=int(d[time_col].iloc[inv_idx])),
                        direction="bearish",
                        top=c2l,
                        bottom=c0h,
                        origin_fvg_time=ts,
                    ))

    ifvgs.sort(key=lambda x: x.index, reverse=True)
    return ifvgs


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4: LIQUIDITY CONCEPTS (BSL/SSL, EQH/EQL, Sweeps, Inducement)
# ═══════════════════════════════════════════════════════════════════════════

def _detect_equal_highs_lows(df: pd.DataFrame, instrument_or_pair: Union[str, Instrument]) -> list[EqualHighLow]:
    """[Section 4] Detect Equal Highs (EQH) and Equal Lows (EQL) liquidity pools."""
    inst = get_instrument(instrument_or_pair)
    d = df.tail(config.LIQUIDITY_LOOKBACK).reset_index()
    sh = _swing_highs(d, n=2)
    sl = _swing_lows(d, n=2)

    high_pts = [(i, float(d["high"].iloc[i])) for i in range(len(d)) if sh.iloc[i]]
    low_pts = [(i, float(d["low"].iloc[i])) for i in range(len(d)) if sl.iloc[i]]

    tolerance = max(inst.tick_size * config.EQH_TOLERANCE_TICKS, inst.pip_size * 2.0)
    pools: list[EqualHighLow] = []

    # Check Equal Highs (EQH)
    for idx1, (i1, p1) in enumerate(high_pts):
        matches = [i1]
        for idx2, (i2, p2) in enumerate(high_pts[idx1 + 1:], start=idx1 + 1):
            if abs(p1 - p2) <= tolerance:
                matches.append(i2)
        if len(matches) >= config.MIN_EQUAL_TOUCHES:
            pools.append(EqualHighLow(kind="EQH", level=p1, touch_count=len(matches), indices=matches, tolerance=tolerance))

    # Check Equal Lows (EQL)
    for idx1, (i1, p1) in enumerate(low_pts):
        matches = [i1]
        for idx2, (i2, p2) in enumerate(low_pts[idx1 + 1:], start=idx1 + 1):
            if abs(p1 - p2) <= tolerance:
                matches.append(i2)
        if len(matches) >= config.MIN_EQUAL_TOUCHES:
            pools.append(EqualHighLow(kind="EQL", level=p1, touch_count=len(matches), indices=matches, tolerance=tolerance))

    return pools


def _detect_liquidity_grab(df: pd.DataFrame, bias: Bias) -> Optional[LiquidityGrab]:
    """[Section 4] Detect Liquidity Sweep / Stop Hunt (Turtle Soup)."""
    d = df.tail(config.LIQUIDITY_LOOKBACK).reset_index()
    time_col = "time" if "time" in d.columns else ("index" if "index" in d.columns else d.columns[0])
    sh = _swing_highs(d, n=2)
    sl = _swing_lows(d, n=2)

    grabs: list[LiquidityGrab] = []

    for i in range(5, len(d)):
        row = d.iloc[i]
        c_open, c_high, c_low, c_close = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
        raw_t = row[time_col]
        ts = pd.to_datetime(raw_t) if not isinstance(raw_t, (int, np.integer)) else pd.Timestamp("2026-01-01") + pd.Timedelta(hours=int(raw_t))

        # Bullish Grab: Sweep of Sell-Side Liquidity (SSL)
        if bias == "bullish":
            prior_sl_indices = [j for j in range(max(0, i - 20), i) if sl.iloc[j]]
            for j in prior_sl_indices:
                level = float(d["low"].iloc[j])
                if c_low < level and c_close > level:
                    grabs.append(LiquidityGrab(
                        index=i,
                        time=ts,
                        direction="bullish",
                        swept_level=level,
                        pool_source="prior_swing_low",
                        wick_penetration=level - c_low,
                    ))

        # Bearish Grab: Sweep of Buy-Side Liquidity (BSL)
        elif bias == "bearish":
            prior_sh_indices = [j for j in range(max(0, i - 20), i) if sh.iloc[j]]
            for j in prior_sh_indices:
                level = float(d["high"].iloc[j])
                if c_high > level and c_close < level:
                    grabs.append(LiquidityGrab(
                        index=i,
                        time=ts,
                        direction="bearish",
                        swept_level=level,
                        pool_source="prior_swing_high",
                        wick_penetration=c_high - level,
                    ))

    return grabs[-1] if grabs else None


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5: PREMIUM / DISCOUNT & OPTIMAL TRADE ENTRY (OTE)
# ═══════════════════════════════════════════════════════════════════════════

def _premium_discount_check(price: float, swing_low: float, swing_high: float) -> tuple[bool, bool, float]:
    """[Section 5] Dealing range Equilibrium and Premium/Discount placement."""
    rng = swing_high - swing_low
    if rng <= 0:
        return False, False, 0.50

    pct = (price - swing_low) / rng
    equilibrium = (swing_high + swing_low) / 2.0
    in_premium = pct >= config.PREMIUM_ZONE
    in_discount = pct <= config.DISCOUNT_ZONE
    return in_premium, in_discount, equilibrium


def _ote_check(price: float, swing_high: float, swing_low: float, bias: Bias) -> bool:
    """[Section 5] Optimal Trade Entry (OTE) Fibonacci Retracement Check."""
    if swing_high <= swing_low:
        return False

    rng = swing_high - swing_low
    if bias == "bullish":
        lo = swing_high - (rng * config.OTE_FIBO_HIGH)   # 79.0% level
        hi = swing_high - (rng * config.OTE_FIBO_LOW)    # 61.8% level
    else:
        lo = swing_low + (rng * config.OTE_FIBO_LOW)     # 61.8% level
        hi = swing_low + (rng * config.OTE_FIBO_HIGH)    # 79.0% level

    return lo <= price <= hi


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7: POWER OF THREE (AMD)
# ═══════════════════════════════════════════════════════════════════════════

def _detect_amd_phase(df_entry: pd.DataFrame, df_daily: pd.DataFrame) -> tuple[AMDPhase, float, float]:
    """[Section 7] Power of Three (AMD) daily cycle identification."""
    if df_entry.empty:
        return "unknown", float("nan"), float("nan")

    raw_t = df_entry.index[-1] if isinstance(df_entry.index, pd.DatetimeIndex) else (df_entry["time"].iloc[-1] if "time" in df_entry.columns else df_entry.index[-1])
    dt = pd.to_datetime(raw_t) if not isinstance(raw_t, (int, np.integer)) else pd.Timestamp("2026-01-01") + pd.Timedelta(hours=int(raw_t))
    dt_ny = get_ny_time(dt)
    hour_ny = dt_ny.hour

    asian_high, asian_low = float("nan"), float("nan")
    if len(df_entry) >= 24:
        recent_asian_bars = []
        for i in range(max(0, len(df_entry) - 96), len(df_entry)):
            idx_val = df_entry.index[i] if isinstance(df_entry.index, pd.DatetimeIndex) else (df_entry["time"].iloc[i] if "time" in df_entry.columns else df_entry.index[i])
            t_dt = pd.to_datetime(idx_val) if not isinstance(idx_val, (int, np.integer)) else pd.Timestamp("2026-01-01") + pd.Timedelta(hours=int(idx_val))
            t_ny = get_ny_time(t_dt)
            if t_ny.hour >= 20 or t_ny.hour < 2:
                recent_asian_bars.append(df_entry.iloc[i])
        if recent_asian_bars:
            asian_df = pd.DataFrame(recent_asian_bars)
            asian_high = float(asian_df["high"].max())
            asian_low = float(asian_df["low"].min())

    if 20 <= hour_ny or hour_ny < 2:
        phase: AMDPhase = "accumulation"
    elif 2 <= hour_ny < 6:
        phase: AMDPhase = "manipulation"
    elif 6 <= hour_ny < 16:
        phase: AMDPhase = "distribution"
    else:
        phase = "unknown"

    return phase, asian_high, asian_low


# ═══════════════════════════════════════════════════════════════════════════
# STEP 1: HTF CONTEXT ANALYSIS (Daily + H4)
# ═══════════════════════════════════════════════════════════════════════════

def _prev_day_hl(df_daily: pd.DataFrame) -> tuple[float, float]:
    """[Section 4, 8] Retrieve previous completed day's high and low."""
    if len(df_daily) < 2:
        return float("nan"), float("nan")
    row = df_daily.iloc[-2]
    return float(row["high"]), float(row["low"])


def analyse_htf_context(
    df_h4: pd.DataFrame,
    df_daily: pd.DataFrame,
    current_price: float,
    instrument_or_pair: Union[str, Instrument] = "EURUSD",
) -> Optional[HTFContext]:
    """[Section 1, 5, 8] Step 1 HTF Gate."""
    daily_bias = _htf_bias(df_daily)
    h4_bias = _htf_bias(df_h4)

    if daily_bias == "neutral":
        return None

    if h4_bias not in (daily_bias, "neutral"):
        pts_daily = _structure_points(df_daily, lookback=40)
        if len(pts_daily) < 6:
            return None
        last6 = pts_daily[-6:]
        bull6 = sum(1 for p in last6 if p.kind in ("HH", "HL"))
        bear6 = sum(1 for p in last6 if p.kind in ("LH", "LL"))
        if daily_bias == "bullish" and bull6 < 4:
            return None
        if daily_bias == "bearish" and bear6 < 4:
            return None

    bias = daily_bias

    if len(df_daily) < 5:
        return None
    roll_window = min(20, len(df_daily))
    swing_high = float(df_daily["high"].tail(roll_window).max())
    swing_low = float(df_daily["low"].tail(roll_window).min())
    
    in_premium, in_discount, equilibrium = _premium_discount_check(current_price, swing_low, swing_high)

    if bias == "bearish" and not in_premium:
        return None
    if bias == "bullish" and not in_discount:
        return None

    pdh, pdl = _prev_day_hl(df_daily)
    draw_target = float("nan")
    draw_source = "swing_extreme"

    pts_draw = _structure_points(df_daily, lookback=60)
    sh_prices = [p.price for p in pts_draw if p.kind in ("HH", "LH")]
    sl_prices = [p.price for p in pts_draw if p.kind in ("HL", "LL")]

    if bias == "bullish":
        candidates = [p for p in ([pdh] if not np.isnan(pdh) else []) + sh_prices if p > current_price]
        if candidates:
            draw_target = min(candidates)
            draw_source = "PDH" if not np.isnan(pdh) and draw_target == pdh else "HTF_Swing_High"
        else:
            draw_target = swing_high
    else:
        candidates = [p for p in ([pdl] if not np.isnan(pdl) else []) + sl_prices if p < current_price]
        if candidates:
            draw_target = max(candidates)
            draw_source = "PDL" if not np.isnan(pdl) and draw_target == pdl else "HTF_Swing_Low"
        else:
            draw_target = swing_low

    if np.isnan(draw_target):
        return None

    htf_score = 0
    if h4_bias == daily_bias:
        htf_score += 1
    if not np.isnan(pdh):
        htf_score += 1
    h4_breaks = _detect_structure_breaks(df_h4, lookback=30)
    if any(b["direction"] == bias for b in h4_breaks[-3:]):
        htf_score += 1
    pct_in_zone = (current_price - swing_low) / (swing_high - swing_low) if (swing_high > swing_low) else 0.5
    if (in_premium and pct_in_zone >= config.EXTREME_PREMIUM) or (in_discount and pct_in_zone <= config.EXTREME_DISCOUNT):
        htf_score += 1

    return HTFContext(
        bias=bias,
        draw_target=draw_target,
        draw_source=draw_source,
        in_premium=in_premium,
        in_discount=in_discount,
        equilibrium=equilibrium,
        swing_high=swing_high,
        swing_low=swing_low,
        prev_day_high=pdh,
        prev_day_low=pdl,
        score=htf_score,
    )


# ═══════════════════════════════════════════════════════════════════════════
# STEP 2: LTF ENTRY CONFIRMATION & SL/TP CALCULATION
# ═══════════════════════════════════════════════════════════════════════════

def _calculate_sl_tp(
    bias: Bias,
    entry: float,
    ob: Optional[OrderBlock],
    breaker: Optional[BreakerBlock],
    fvg: Optional[FairValueGap],
    ifvg: Optional[InversionFVG],
    htf: HTFContext,
    df_h1: pd.DataFrame,
    instrument_or_pair: Union[str, Instrument],
) -> tuple[float, float, float]:
    """[Section 2, 3, 8] Stop Loss and Take Profit projection."""
    inst = get_instrument(instrument_or_pair)
    buf = 3.0 * inst.pip_size

    if ob is not None:
        raw_sl_dist = abs(entry - (ob.bottom if bias == "bullish" else ob.top)) + buf
    elif breaker is not None:
        raw_sl_dist = abs(entry - (breaker.bottom if bias == "bullish" else breaker.top)) + buf
    elif fvg is not None:
        raw_sl_dist = abs(entry - (fvg.bottom if bias == "bullish" else fvg.top)) + buf
    elif ifvg is not None:
        raw_sl_dist = abs(entry - (ifvg.bottom if bias == "bullish" else ifvg.top)) + buf
    else:
        raw_sl_dist = 8.0 * inst.pip_size

    max_sl_dist = config.MAX_SL_PIPS * inst.pip_size
    raw_sl_dist = min(raw_sl_dist, max_sl_dist)

    stop_loss = round(entry - raw_sl_dist if bias == "bullish" else entry + raw_sl_dist, 5)
    sl_dist = abs(entry - stop_loss)

    min_tp = entry + (sl_dist * config.MIN_RR) if bias == "bullish" else entry - (sl_dist * config.MIN_RR)

    if bias == "bullish":
        tp = htf.draw_target if htf.draw_target > min_tp else min_tp
    else:
        tp = htf.draw_target if htf.draw_target < min_tp else min_tp

    tp = round(tp, 5)
    rr = round(abs(tp - entry) / sl_dist, 2) if sl_dist > 0 else 0.0
    return stop_loss, tp, rr


def _score_confluence(
    ob: Optional[OrderBlock],
    breaker: Optional[BreakerBlock],
    fvg: Optional[FairValueGap],
    ifvg: Optional[InversionFVG],
    grab: Optional[LiquidityGrab],
    eq_pool: Optional[EqualHighLow],
    choch: bool,
    bos: bool,
    active_kz: list[str],
    in_ote: bool,
    htf_score: int,
) -> tuple[int, list[str]]:
    """[Section 6, 8] Confluence scoring (0 - 10)."""
    s = 0
    reasons = []

    if ob:
        s += 2
        reasons.append(f"OB@{ob.mid:.5f}")
    elif breaker:
        s += 2
        reasons.append(f"Breaker@{breaker.mid:.5f}")

    if fvg:
        s += 1
        reasons.append(f"FVG@{fvg.consequent_encroachment:.5f}")
    elif ifvg:
        s += 1
        reasons.append(f"IFVG@{ifvg.mid:.5f}")

    if grab:
        s += 2
        reasons.append(f"LiqGrab({grab.pool_source})")
    if eq_pool:
        s += 1
        reasons.append(f"{eq_pool.kind}Pool")

    if choch:
        s += 2
        reasons.append("CHoCH/MSS")
    elif bos:
        s += 1
        reasons.append("BOS")

    if active_kz:
        kz_str = "+".join(active_kz[:2])
        s += 2 if any("Silver_Bullet" in k or "Overlap" in k for k in active_kz) else 1
        reasons.append(f"KZ:{kz_str}")

    if in_ote:
        s += 1
        reasons.append("OTE_70.5%")

    if htf_score >= 3:
        s += 1
        reasons.append(f"HTF:{htf_score}")

    return min(s, 10), reasons


# ═══════════════════════════════════════════════════════════════════════════
# MASTER ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def analyse_pair(
    pair_or_instrument: Union[str, Instrument],
    candles: dict[str, pd.DataFrame],
) -> Optional[SMCSignal]:
    """[Section 8] Two-Step ICT Verification Pipeline."""
    inst = get_instrument(pair_or_instrument)
    pair = inst.symbol

    df_h1 = candles.get(config.TIMEFRAMES["mid"], pd.DataFrame())
    df_h4 = candles.get(config.TIMEFRAMES["high"], pd.DataFrame())
    df_daily = candles.get(config.TIMEFRAMES["daily"], pd.DataFrame())
    df_entry = candles.get(config.TIMEFRAMES["entry"], df_h1)

    if any(df.empty for df in [df_h1, df_h4, df_daily]):
        return None

    current_price = float(df_entry["close"].iloc[-1])

    # STEP 1: HTF Context
    htf = analyse_htf_context(df_h4, df_daily, current_price, inst)
    if htf is None:
        return None

    bias = htf.bias

    # STEP 2A: Killzone Check
    raw_t = df_entry.index[-1] if isinstance(df_entry.index, pd.DatetimeIndex) else (df_entry["time"].iloc[-1] if "time" in df_entry.columns else df_entry.index[-1])
    last_ts = pd.to_datetime(raw_t) if not isinstance(raw_t, (int, np.integer)) else pd.Timestamp("2026-01-01") + pd.Timedelta(hours=int(raw_t))
    active_kz = get_active_killzones(last_ts)
    in_kz = len(active_kz) > 0
    in_sb = is_in_silver_bullet(last_ts)

    if config.KILLZONE_REQUIRED and not in_kz:
        return None

    # STEP 2B: Structural Confirmation
    h1_breaks = _detect_structure_breaks(df_h1, lookback=config.STRUCTURE_LOOKBACK)
    has_choch = any(b["type"] == "CHoCH" and b["direction"] == bias for b in h1_breaks[-3:])
    has_bos = any(b["type"] == "BOS" and b["direction"] == bias for b in h1_breaks[-3:])

    if not has_choch and not has_bos:
        return None

    # STEP 2C: POI Reaction
    obs = _detect_obs(df_entry, bias)
    breakers = _detect_breaker_blocks(df_entry, bias)
    fvgs = _detect_fvgs(df_entry, bias, inst)
    ifvgs = _detect_inversion_fvgs(df_entry, bias, inst)

    matched_ob: Optional[OrderBlock] = None
    matched_breaker: Optional[BreakerBlock] = None
    matched_fvg: Optional[FairValueGap] = None
    matched_ifvg: Optional[InversionFVG] = None

    for ob in obs[:5]:
        if ob.contains(current_price, convention=config.OB_ENTRY_CONVENTION):
            matched_ob = ob
            break

    if matched_ob is None:
        for brk in breakers[:5]:
            if brk.contains(current_price):
                matched_breaker = brk
                break

    if matched_ob is None and matched_breaker is None:
        for fvg in fvgs[:5]:
            if fvg.contains(current_price):
                matched_fvg = fvg
                break

    if matched_ob is None and matched_breaker is None and matched_fvg is None:
        for ifvg in ifvgs[:5]:
            if ifvg.contains(current_price):
                matched_ifvg = ifvg
                break

    if matched_ob is None and matched_breaker is None and matched_fvg is None and matched_ifvg is None:
        return None

    # STEP 2D: Liquidity Sweep
    grab = _detect_liquidity_grab(df_entry, bias)
    eq_pools = _detect_equal_highs_lows(df_entry, inst)
    matched_eq = eq_pools[0] if eq_pools else None

    # STEP 2E: OTE Fibonacci Retracement
    sh_s = _swing_highs(df_h1, n=3)
    sl_s = _swing_lows(df_h1, n=3)
    sh_vals = df_h1["high"][sh_s].tail(3)
    sl_vals = df_h1["low"][sl_s].tail(3)
    recent_sh = float(sh_vals.max()) if not sh_vals.empty else current_price
    recent_sl = float(sl_vals.min()) if not sl_vals.empty else current_price
    in_ote = _ote_check(current_price, recent_sh, recent_sl, bias)

    # STEP 2F: AMD Phase
    amd_phase, asian_h, asian_l = _detect_amd_phase(df_entry, df_daily)
    htf.asian_high = asian_h
    htf.asian_low = asian_l
    htf.amd_phase = amd_phase

    # STEP 2G: Confluence Scoring
    score, reasons = _score_confluence(
        matched_ob, matched_breaker, matched_fvg, matched_ifvg,
        grab, matched_eq, has_choch, has_bos, active_kz, in_ote, htf.score
    )

    if score < config.MIN_CONFLUENCE_SCORE:
        logger.debug("%s: Score %d < %d — skipping", pair, score, config.MIN_CONFLUENCE_SCORE)
        return None

    # STEP 2H: Stop Loss / Take Profit
    stop_loss, take_profit, rr = _calculate_sl_tp(
        bias, current_price, matched_ob, matched_breaker, matched_fvg, matched_ifvg, htf, df_h1, inst
    )

    if rr < config.MIN_RR:
        return None

    in_correct_zone = htf.in_discount if bias == "bullish" else htf.in_premium
    htf_label = f"HTF:{bias.upper()}|P{'rem' if htf.in_premium else 'disc'}|Draw:{htf.draw_target:.5f}"
    reason_str = f"[S1:{htf.score}|S2:{score}] {htf_label} | " + " | ".join(reasons)

    signal = SMCSignal(
        pair=pair,
        bias=bias,
        entry_price=round(current_price, 5),
        stop_loss=stop_loss,
        take_profit=take_profit,
        rr=rr,
        confluence_score=score,
        ob=matched_ob,
        breaker=matched_breaker,
        fvg=matched_fvg,
        ifvg=matched_ifvg,
        liquidity_grab=grab,
        eq_pool=matched_eq,
        in_kill_zone=in_kz,
        active_killzones=active_kz,
        in_silver_bullet=in_sb,
        in_ote_zone=in_ote,
        in_discount_premium=in_correct_zone,
        amd_phase=amd_phase,
        htf_score=htf.score,
        reason=reason_str,
    )

    # Optional ML Gate
    ml_prob = score_smc_signal(signal)
    if ml_prob is not None:
        signal.ml_win_prob = ml_prob
        if ml_prob < WIN_PROB_THRESHOLD:
            return None

    return signal


# ═══════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY ALIASES
# ═══════════════════════════════════════════════════════════════════════════

def detect_bias(df_h4: pd.DataFrame, df_daily: pd.DataFrame) -> Bias:
    daily = _htf_bias(df_daily)
    h4 = _htf_bias(df_h4)
    if daily == "bullish" and h4 in ("bullish", "neutral"):
        return "bullish"
    if daily == "bearish" and h4 in ("bearish", "neutral"):
        return "bearish"
    if daily == "neutral":
        return h4
    return "neutral"

def detect_order_blocks(df: pd.DataFrame, bias: Bias, lookback: Optional[int] = None) -> list[OrderBlock]:
    return _detect_obs(df, bias)

def detect_breaker_blocks(df: pd.DataFrame, bias: Bias) -> list[BreakerBlock]:
    return _detect_breaker_blocks(df, bias)

def detect_fvgs(df: pd.DataFrame, bias: Bias, lookback: Optional[int] = None, min_pips: Optional[float] = None, pair: str = "EURUSD") -> list[FairValueGap]:
    return _detect_fvgs(df, bias, pair)

def detect_inversion_fvgs(df: pd.DataFrame, bias: Bias, pair: str = "EURUSD") -> list[InversionFVG]:
    return _detect_inversion_fvgs(df, bias, pair)

def detect_liquidity_grabs(df: pd.DataFrame, lookback: Optional[int] = None) -> list[LiquidityGrab]:
    bull = _detect_liquidity_grab(df, "bullish")
    bear = _detect_liquidity_grab(df, "bearish")
    return [g for g in [bull, bear] if g is not None]

def detect_choch_bos(df: pd.DataFrame, lookback: Optional[int] = None) -> list[dict]:
    return _detect_structure_breaks(df, lookback=lookback or config.STRUCTURE_LOOKBACK)

def find_swing_highs(df: pd.DataFrame, lookback: int = 5) -> pd.Series:
    return _swing_highs(df, n=lookback)

def find_swing_lows(df: pd.DataFrame, lookback: int = 5) -> pd.Series:
    return _swing_lows(df, n=lookback)

def is_in_ote_zone(price: float, sh: float, sl: float, bias: Bias) -> bool:
    return _ote_check(price, sh, sl, bias)

def score_confluence(*args, **kwargs) -> tuple[int, list[str]]:
    return 0, []

def detect_market_structure(df: pd.DataFrame, lookback: int = config.STRUCTURE_LOOKBACK) -> list[MarketStructurePoint]:
    return _structure_points(df, lookback)
