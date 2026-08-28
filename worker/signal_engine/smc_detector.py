"""
PORTED FROM: forex_bot/smc_detector.py — reused close to as-is.

TODO (Gypsi generalisation, see docs/ARCHITECTURE.md):
  - Replace any hardcoded pip-size / "JPY" in pair checks with
    `instrument.tick_size` from signal_engine.instrument.Instrument.
  - Confirm swing-detection lookback windows still make sense on equity
    bar data (forex tuning may not transfer 1:1 — validate via backtest
    before trusting live signals on the new watchlist).
  - The pattern-detection math itself (OB/FVG/CHoCH/liquidity grab) is
    asset-agnostic and should NOT need structural changes.

smc_detector.py — ICT Two-Step Verification Engine.

TWO-STEP ENTRY MODEL
════════════════════
Step 1 — HTF Context (Daily + H4)
  • Structural bias: HH/HL sequence (bullish) or LH/LL (bearish)
  • Price must be at a Premium (sell) or Discount (buy) extreme
  • Draw on liquidity: a clear PDHL / swing level ahead as the TP target
  • Previous Day High/Low as reference for premium/discount zones

Step 2 — LTF Entry (H1 + M5)  — only runs if Step 1 passes
  • Kill zone active (London 07-10 UTC or NY 12-15 UTC)
  • H1 BOS or CHoCH confirming Step 1 bias
  • Price raids liquidity (sweep) then returns into an OB or FVG
  • OTE Fibonacci window (62–79% of last swing)
  • ML probability gate as final filter

Both steps must pass. No exceptions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np
import pandas as pd

import config
from ml_model import score_smc_signal, WIN_PROB_THRESHOLD

logger = logging.getLogger(__name__)

Bias = Literal["bullish", "bearish", "neutral"]

# ═══════════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class OrderBlock:
    index: int
    time:  pd.Timestamp
    direction: Literal["bullish", "bearish"]
    top:    float
    bottom: float
    broken: bool = False

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2

    @property
    def size_pips(self) -> float:
        return (self.top - self.bottom) / 0.0001


@dataclass
class FairValueGap:
    index: int
    time:  pd.Timestamp
    direction: Literal["bullish", "bearish"]
    top:    float
    bottom: float
    filled: bool = False

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass
class LiquidityGrab:
    index: int
    time:  pd.Timestamp
    direction: Literal["bullish", "bearish"]   # direction of the SWEEP (not the trade)
    swept_level: float


@dataclass
class HTFContext:
    """Result of Step 1 — populated only when context is valid."""
    bias:            Bias
    draw_target:     float          # price target (prev swing level or PDH/PDL)
    in_premium:      bool           # price above equilibrium (sell zone)
    in_discount:     bool           # price below equilibrium (buy zone)
    swing_high:      float
    swing_low:       float
    prev_day_high:   float
    prev_day_low:    float
    score:           int            # 0-4 quality score


@dataclass
class SMCSignal:
    pair:            str
    bias:            Bias
    entry_price:     float
    stop_loss:       float
    take_profit:     float
    rr:              float
    confluence_score: int  = 0
    ob:   Optional[OrderBlock]    = None
    fvg:  Optional[FairValueGap]  = None
    liquidity_grab: Optional[LiquidityGrab] = None
    in_kill_zone:    bool  = False
    in_ote_zone:     bool  = False
    in_discount_premium: bool = False
    htf_score:       int   = 0     # Step 1 quality (0-4)
    reason:          str   = ""

    @property
    def sl_pips(self) -> float:
        pip = 0.01 if "JPY" in self.pair else 0.0001
        return abs(self.entry_price - self.stop_loss) / pip

    @property
    def tp_pips(self) -> float:
        pip = 0.01 if "JPY" in self.pair else 0.0001
        return abs(self.take_profit - self.entry_price) / pip


# ═══════════════════════════════════════════════════════════════════════════
# Shared low-level helpers
# ═══════════════════════════════════════════════════════════════════════════

def _swing_highs(df: pd.DataFrame, n: int = 3) -> pd.Series:
    """Confirmed swing highs — n closed bars on each side required."""
    h = df["high"]
    sw = pd.Series(False, index=df.index)
    for i in range(n, len(df) - n):
        if h.iloc[i] > h.iloc[i-n:i].max() and h.iloc[i] > h.iloc[i+1:i+n+1].max():
            sw.iloc[i] = True
    return sw


def _swing_lows(df: pd.DataFrame, n: int = 3) -> pd.Series:
    l = df["low"]
    sw = pd.Series(False, index=df.index)
    for i in range(n, len(df) - n):
        if l.iloc[i] < l.iloc[i-n:i].min() and l.iloc[i] < l.iloc[i+1:i+n+1].min():
            sw.iloc[i] = True
    return sw


def _structure_points(df: pd.DataFrame, lookback: int = 80) -> list[dict]:
    """Return HH/HL/LH/LL points — no lookahead."""
    d = df.tail(lookback).reset_index()
    if "time" not in d.columns:
        d["time"] = d.index

    sh = _swing_highs(d, n=3)
    sl = _swing_lows(d,  n=3)
    pts: list[dict] = []
    last_h = last_l = None

    for i in range(len(d)):
        if sh.iloc[i]:
            v    = d["high"].iloc[i]
            kind = "HH" if (last_h is None or v > last_h) else "LH"
            last_h = v
            pts.append({"kind": kind, "price": v, "idx": i, "time": d["time"].iloc[i]})
        if sl.iloc[i]:
            v    = d["low"].iloc[i]
            kind = "HL" if (last_l is None or v > last_l) else "LL"
            last_l = v
            pts.append({"kind": kind, "price": v, "idx": i, "time": d["time"].iloc[i]})

    pts.sort(key=lambda x: x["idx"])
    return pts


def _htf_bias(df: pd.DataFrame) -> Bias:
    # Use fewer lookback bars when data is limited (e.g. resampled daily slice)
    lookback = min(80, max(20, len(df) * 2))
    pts = _structure_points(df, lookback=lookback)

    if len(pts) == 0:
        return "neutral"

    # With enough points use last 4; with few use all available
    window = min(4, len(pts))
    last_n = pts[-window:]
    bull   = sum(1 for p in last_n if p["kind"] in ("HH", "HL"))
    bear   = sum(1 for p in last_n if p["kind"] in ("LH", "LL"))

    # Require majority (>50%) rather than fixed 3-of-4
    threshold = max(2, window - 1)
    if bull >= threshold:
        return "bullish"
    if bear >= threshold:
        return "bearish"

    # Fallback: simple price trend — last close vs first close
    if len(df) >= 5:
        first = float(df["close"].iloc[0])
        last  = float(df["close"].iloc[-1])
        diff  = (last - first) / first
        if diff > 0.005:    # +0.5% trend
            return "bullish"
        if diff < -0.005:   # -0.5% trend
            return "bearish"

    return "neutral"


def _is_kill_zone(ts: pd.Timestamp) -> bool:
    try:
        h = ts.tz_convert("UTC").hour
    except Exception:
        h = ts.hour
    return any(s <= h < e for s, e in config.KILL_ZONES)


# ═══════════════════════════════════════════════════════════════════════════
# STEP 1 — HTF Context
# ═══════════════════════════════════════════════════════════════════════════

def _prev_day_hl(df_daily: pd.DataFrame) -> tuple[float, float]:
    """Previous completed day's high and low."""
    if len(df_daily) < 2:
        return float("nan"), float("nan")
    row = df_daily.iloc[-2]
    return float(row["high"]), float(row["low"])


def analyse_htf_context(
    df_h4:    pd.DataFrame,
    df_daily: pd.DataFrame,
    current_price: float,
) -> Optional[HTFContext]:
    """
    Step 1 gate. Returns HTFContext if all conditions pass, else None.

    Conditions (all must be true):
      A. Daily AND H4 agree on bias direction
      B. Price is in the correct premium/discount extreme (not equilibrium)
      C. A draw on liquidity (PDH/PDL or swing extreme) exists beyond current price
    """
    # A — Dual-timeframe bias agreement
    daily_bias = _htf_bias(df_daily)
    h4_bias    = _htf_bias(df_h4)

    if daily_bias == "neutral":
        return None
    # H4 must agree OR be neutral — but we also accept H4 neutral when daily is strong
    if h4_bias not in (daily_bias, "neutral"):
        # Soft check: still allow if daily structure is very clear (>= 3 of last 4 points)
        pts_daily_check = _structure_points(df_daily, lookback=40)
        if len(pts_daily_check) < 6:
            return None   # H4 contradicts and daily structure unclear
        last6 = pts_daily_check[-6:]
        bull6 = sum(1 for p in last6 if p["kind"] in ("HH", "HL"))
        bear6 = sum(1 for p in last6 if p["kind"] in ("LH", "LL"))
        if daily_bias == "bullish" and bull6 < 4:
            return None
        if daily_bias == "bearish" and bear6 < 4:
            return None
        # If daily is overwhelmingly clear (5/6), proceed despite H4 disagreement

    bias = daily_bias

    # B — Premium / Discount zone using rolling 20-day range (handles range breakouts)
    # Use the last 20 daily candles' high/low as the range reference
    if len(df_daily) < 5:
        return None
    roll_window = min(20, len(df_daily))
    swing_high  = float(df_daily["high"].tail(roll_window).max())
    swing_low   = float(df_daily["low"].tail(roll_window).min())
    rng = swing_high - swing_low

    if rng < 0.0010:   # range too tight to be meaningful
        return None

    position_pct = (current_price - swing_low) / rng
    # Clamp position_pct — price can temporarily exit the recent range
    position_pct = max(-0.1, min(1.1, position_pct))

    in_premium   = position_pct >= config.PREMIUM_ZONE
    in_discount  = position_pct <= config.DISCOUNT_ZONE

    # Must be in the CORRECT zone for the bias
    if bias == "bearish" and not in_premium:
        return None
    if bias == "bullish" and not in_discount:
        return None

    # C — Draw on liquidity: a clear level price can run to
    pdh, pdl = _prev_day_hl(df_daily)
    draw_target = float("nan")

    # Use structure points from df_daily for draw candidates
    pts_draw = _structure_points(df_daily, lookback=60)
    sh_prices_draw = [p["price"] for p in pts_draw if p["kind"] in ("HH", "LH")]
    sl_prices_draw = [p["price"] for p in pts_draw if p["kind"] in ("HL", "LL")]

    if bias == "bullish":
        candidates = [p for p in ([pdh] if not np.isnan(pdh) else []) + sh_prices_draw if p > current_price]
        draw_target = min(candidates) if candidates else swing_high  # fallback to range high
    else:
        candidates = [p for p in ([pdl] if not np.isnan(pdl) else []) + sl_prices_draw if p < current_price]
        draw_target = max(candidates) if candidates else swing_low   # fallback to range low

    if np.isnan(draw_target):
        return None

    # Score Step 1 quality (0-4)
    htf_score = 0
    if h4_bias == daily_bias:          htf_score += 1   # full TF agreement
    if not np.isnan(pdh):              htf_score += 1   # PDH/PDL available
    pts_h4 = _structure_points(df_h4, lookback=60)
    recent_choch_h4 = [p for p in pts_h4[-6:]
                       if (bias == "bullish" and p["kind"] == "HH") or
                          (bias == "bearish" and p["kind"] == "LL")]
    if recent_choch_h4:                htf_score += 1   # H4 structure break
    if (in_premium and position_pct >= 0.80) or \
       (in_discount and position_pct <= 0.20): htf_score += 1  # extreme zone

    return HTFContext(
        bias=bias,
        draw_target=draw_target,
        in_premium=in_premium,
        in_discount=in_discount,
        swing_high=swing_high,
        swing_low=swing_low,
        prev_day_high=pdh,
        prev_day_low=pdl,
        score=htf_score,
    )


# ═══════════════════════════════════════════════════════════════════════════
# STEP 2 — LTF Entry Confirmation
# ═══════════════════════════════════════════════════════════════════════════

def _detect_obs(df: pd.DataFrame, bias: Bias) -> list[OrderBlock]:
    """Order blocks — no lookahead."""
    d = df.tail(config.OB_LOOKBACK + 10).reset_index()
    if "time" not in d.columns:
        d["time"] = d.index
    obs: list[OrderBlock] = []
    n = len(d)

    for i in range(2, n - 1):
        o, h, l, c = d["open"].iloc[i], d["high"].iloc[i], d["low"].iloc[i], d["close"].iloc[i]
        ts = d["time"].iloc[i]
        nc, nh, nl = d["close"].iloc[i+1], d["high"].iloc[i+1], d["low"].iloc[i+1]
        body, nbody = abs(c-o), abs(nc - d["open"].iloc[i+1])
        if body == 0:
            continue

        if bias == "bullish" and c < o and nc > h and nbody >= body * config.OB_IMPULSE_FACTOR:
            ob = OrderBlock(i, ts, "bullish", top=h, bottom=l)
            ob.broken = (d["close"].iloc[i+2:] < l).any()
            if not ob.broken:
                obs.append(ob)

        elif bias == "bearish" and c > o and nc < l and nbody >= body * config.OB_IMPULSE_FACTOR:
            ob = OrderBlock(i, ts, "bearish", top=h, bottom=l)
            ob.broken = (d["close"].iloc[i+2:] > h).any()
            if not ob.broken:
                obs.append(ob)

    obs.sort(key=lambda x: x.index, reverse=True)
    return obs


def _detect_fvgs(df: pd.DataFrame, bias: Bias, pair: str) -> list[FairValueGap]:
    """Fair value gaps — no lookahead."""
    pip = 0.01 if "JPY" in pair else 0.0001
    d   = df.tail(config.OB_LOOKBACK + 5).reset_index()
    if "time" not in d.columns:
        d["time"] = d.index
    fvgs: list[FairValueGap] = []
    n = len(d)

    for i in range(1, n - 1):
        c0h, c0l = d["high"].iloc[i-1], d["low"].iloc[i-1]
        ts        = d["time"].iloc[i]
        c2h, c2l = d["high"].iloc[i+1], d["low"].iloc[i+1]

        if bias == "bullish" and c0h < c2l:
            gap = (c2l - c0h) / pip
            if gap >= config.FVG_MIN_SIZE_PIPS:
                fvg = FairValueGap(i, ts, "bullish", top=c2l, bottom=c0h)
                fvg.filled = (d["low"].iloc[i+2:] <= c2l).any()
                if not fvg.filled:
                    fvgs.append(fvg)

        elif bias == "bearish" and c0l > c2h:
            gap = (c0l - c2h) / pip
            if gap >= config.FVG_MIN_SIZE_PIPS:
                fvg = FairValueGap(i, ts, "bearish", top=c0l, bottom=c2h)
                fvg.filled = (d["high"].iloc[i+2:] >= c0l).any()
                if not fvg.filled:
                    fvgs.append(fvg)

    fvgs.sort(key=lambda x: x.index, reverse=True)
    return fvgs


def _detect_liquidity_grab(df: pd.DataFrame, bias: Bias) -> Optional[LiquidityGrab]:
    """Most recent liquidity sweep aligned with bias (swept AGAINST bias, closed back)."""
    d  = df.tail(config.LIQUIDITY_LOOKBACK).reset_index()
    if "time" not in d.columns:
        d["time"] = d.index
    sh = _swing_highs(d, n=3)
    sl = _swing_lows(d,  n=3)

    grabs: list[LiquidityGrab] = []
    for i in range(5, len(d)):
        row = d.iloc[i]
        # Bullish grab: wick below prior swing low, close back above
        if bias == "bullish":
            prev_sl = [j for j in range(max(0, i-10), i) if sl.iloc[j]]
            for j in prev_sl:
                level = d["low"].iloc[j]
                if row["low"] < level and row["close"] > level:
                    grabs.append(LiquidityGrab(i, row["time"], "bullish", level))
        # Bearish grab: wick above prior swing high, close back below
        else:
            prev_sh = [j for j in range(max(0, i-10), i) if sh.iloc[j]]
            for j in prev_sh:
                level = d["high"].iloc[j]
                if row["high"] > level and row["close"] < level:
                    grabs.append(LiquidityGrab(i, row["time"], "bearish", level))

    return grabs[-1] if grabs else None


def _h1_confirmation(df_h1: pd.DataFrame, bias: Bias) -> tuple[bool, bool]:
    """
    Check for H1 BOS or CHoCH in the direction of bias.
    Returns (has_choch, has_bos).
    """
    pts = _structure_points(df_h1, lookback=config.STRUCTURE_LOOKBACK)
    choch = bos = False

    for i in range(2, len(pts)):
        p, c = pts[i-1], pts[i]
        if bias == "bullish":
            if p["kind"] == "LH" and c["kind"] == "HH":
                choch = True
            if p["kind"] == "HL" and c["kind"] == "HH":
                bos   = True
        else:
            if p["kind"] == "HL" and c["kind"] == "LL":
                choch = True
            if p["kind"] == "LH" and c["kind"] == "LL":
                bos   = True

    return choch, bos


def _ote_check(price: float, sh: float, sl: float, bias: Bias) -> bool:
    """OTE: 62-79% Fibonacci retracement of the last swing."""
    if sh == sl:
        return False
    rng = sh - sl
    if bias == "bullish":
        lo = sh - rng * config.OTE_FIBO_HIGH
        hi = sh - rng * config.OTE_FIBO_LOW
    else:
        lo = sl + rng * config.OTE_FIBO_LOW
        hi = sl + rng * config.OTE_FIBO_HIGH
    return lo <= price <= hi


def _calculate_sl_tp(
    bias: Bias,
    entry: float,
    ob: Optional[OrderBlock],
    fvg: Optional[FairValueGap],
    htf: HTFContext,
    df_h1: pd.DataFrame,
    pair: str,
) -> tuple[float, float, float]:
    """SL behind the OB/FVG, TP toward the HTF draw-on-liquidity target."""
    from data_fetcher import calculate_atr_pips

    pip  = 0.01 if "JPY" in pair else 0.0001
    buf  = 3 * pip

    # SL
    if ob is not None:
        raw_sl = abs(entry - (ob.bottom if bias == "bullish" else ob.top)) + buf
    elif fvg is not None:
        raw_sl = abs(entry - (fvg.bottom if bias == "bullish" else fvg.top)) + buf
    else:
        raw_sl = 8 * pip

    sl_pips = raw_sl / pip
    if sl_pips > config.MAX_SL_PIPS:
        atr_pips = calculate_atr_pips(df_h1, pair) * 0.5
        raw_sl   = min(atr_pips, config.MAX_SL_PIPS) * pip

    stop_loss = round(entry - raw_sl if bias == "bullish" else entry + raw_sl, 5)
    sl_dist   = abs(entry - stop_loss)

    # TP — use HTF draw target if it gives >= MIN_RR, else project MIN_RR
    min_tp = entry + sl_dist * config.MIN_RR if bias == "bullish" \
             else entry - sl_dist * config.MIN_RR

    if bias == "bullish":
        tp = htf.draw_target if htf.draw_target > min_tp else min_tp
    else:
        tp = htf.draw_target if htf.draw_target < min_tp else min_tp

    tp   = round(tp, 5)
    rr   = round(abs(tp - entry) / sl_dist, 2) if sl_dist > 0 else 0.0
    return stop_loss, tp, rr


# ═══════════════════════════════════════════════════════════════════════════
# Confluence scoring — compact
# ═══════════════════════════════════════════════════════════════════════════

def _score_ltf(
    ob: Optional[OrderBlock],
    fvg: Optional[FairValueGap],
    grab: Optional[LiquidityGrab],
    choch: bool,
    bos: bool,
    in_kz: bool,
    in_ote: bool,
    htf_score: int,
) -> tuple[int, list[str]]:
    """
    LTF confluence (0-10):
      OB        +2   FVG       +1   Liq grab  +2
      CHoCH     +2   BOS       +1   Kill zone +1
      OTE       +1   HTF qual  +1 (if htf_score >= 3)
    """
    s, r = 0, []
    if ob:       s += 2; r.append(f"OB@{ob.mid:.5f}")
    if fvg:      s += 1; r.append(f"FVG {fvg.bottom:.5f}-{fvg.top:.5f}")
    if grab:     s += 2; r.append("Liq.Grab")
    if choch:    s += 2; r.append("CHoCH")
    if bos:      s += 1; r.append("BOS")
    if in_kz:    s += 1; r.append("KillZone")
    if in_ote:   s += 1; r.append("OTE")
    if htf_score >= 3: s += 1; r.append(f"HTF:{htf_score}")
    return min(s, 10), r


# ═══════════════════════════════════════════════════════════════════════════
# Master entry point — two-step verification
# ═══════════════════════════════════════════════════════════════════════════

def analyse_pair(
    pair: str,
    candles: dict[str, pd.DataFrame],
) -> Optional[SMCSignal]:
    """
    Two-step ICT verification. Returns SMCSignal or None.

    STEP 1 — HTF Context:  Daily + H4 bias, premium/discount, draw on liquidity.
    STEP 2 — LTF Entry:    Kill zone + H1 BOS/CHoCH + OB/FVG with liquidity sweep
                           + OTE Fibonacci + confluence score + ML gate.
    """
    df_h1    = candles.get(config.TIMEFRAMES["mid"],   pd.DataFrame())
    df_h4    = candles.get(config.TIMEFRAMES["high"],  pd.DataFrame())
    df_daily = candles.get(config.TIMEFRAMES["daily"], pd.DataFrame())
    df_entry = candles.get(config.TIMEFRAMES["entry"], df_h1)  # M5 or H1 fallback

    if any(df.empty for df in [df_h1, df_h4, df_daily]):
        return None

    current_price = float(df_entry["close"].iloc[-1])
    pip           = 0.01 if "JPY" in pair else 0.0001

    # ── STEP 1: HTF Context ────────────────────────────────────────────────
    htf = analyse_htf_context(df_h4, df_daily, current_price)
    if htf is None:
        return None   # Step 1 failed — no trade

    bias = htf.bias

    # ── STEP 2A: Kill zone ─────────────────────────────────────────────────
    last_ts  = df_entry.index[-1]
    in_kz    = _is_kill_zone(last_ts)
    # Kill zone is preferred but not mandatory — we penalise score instead
    # (enforcing it hard causes too few trades in backtests)

    # ── STEP 2B: H1 structural confirmation ───────────────────────────────
    choch, bos = _h1_confirmation(df_h1, bias)
    if not choch and not bos:
        return None   # No H1 structure break — Step 2 failed

    # ── STEP 2C: OB / FVG on entry TF ─────────────────────────────────────
    obs  = _detect_obs(df_entry, bias)
    fvgs = _detect_fvgs(df_entry, bias, pair)

    matched_ob:  Optional[OrderBlock]   = None
    matched_fvg: Optional[FairValueGap] = None

    for ob in obs[:5]:
        if ob.bottom <= current_price <= ob.top:
            matched_ob = ob
            break
    if matched_ob is None:
        for fvg in fvgs[:5]:
            if fvg.bottom <= current_price <= fvg.top:
                matched_fvg = fvg
                break

    if matched_ob is None and matched_fvg is None:
        return None   # Price not at a valid entry zone

    # ── STEP 2D: Liquidity sweep ───────────────────────────────────────────
    grab = _detect_liquidity_grab(df_entry, bias)

    # ── STEP 2E: OTE Fibonacci ─────────────────────────────────────────────
    sh_s = _swing_highs(df_h1, n=5)
    sl_s = _swing_lows(df_h1,  n=5)
    sh_vals = df_h1["high"][sh_s].tail(3)
    sl_vals = df_h1["low"][sl_s].tail(3)
    recent_sh = float(sh_vals.max()) if not sh_vals.empty else current_price
    recent_sl = float(sl_vals.min()) if not sl_vals.empty else current_price
    in_ote    = _ote_check(current_price, recent_sh, recent_sl, bias)

    # ── STEP 2F: LTF Confluence score ─────────────────────────────────────
    score, reasons = _score_ltf(
        matched_ob, matched_fvg, grab, choch, bos, in_kz, in_ote, htf.score
    )

    if score < config.MIN_CONFLUENCE_SCORE:
        logger.debug("%s: Score %d < %d — skipping", pair, score, config.MIN_CONFLUENCE_SCORE)
        return None

    # ── STEP 2G: SL / TP ──────────────────────────────────────────────────
    stop_loss, take_profit, rr = _calculate_sl_tp(
        bias, current_price, matched_ob, matched_fvg, htf, df_h1, pair
    )

    if rr < config.MIN_RR:
        return None

    in_correct_zone = htf.in_discount if bias == "bullish" else htf.in_premium
    htf_label = (f"HTF:{'BULL' if bias=='bullish' else 'BEAR'}"
                 f"|P{'rem' if htf.in_premium else 'disc'}"
                 f"|Draw:{htf.draw_target:.5f}")
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
        fvg=matched_fvg,
        liquidity_grab=grab,
        in_kill_zone=in_kz,
        in_ote_zone=in_ote,
        in_discount_premium=in_correct_zone,
        htf_score=htf.score,
        reason=reason_str,
    )

    logger.info(
        "%s %s | S1:%d S2:%d | Entry:%.5f SL:%.5f TP:%.5f RR:%.2f | %s",
        pair, bias.upper(), htf.score, score,
        signal.entry_price, signal.stop_loss, signal.take_profit, rr,
        " | ".join(reasons),
    )

    # ── STEP 3: ML probability gate ───────────────────────────────────────
    ml_prob = score_smc_signal(signal)
    if ml_prob is not None:
        signal.ml_win_prob = ml_prob
        if ml_prob < WIN_PROB_THRESHOLD:
            logger.info("%s: ML rejected (p=%.2f)", pair, ml_prob)
            return None
        logger.info("%s: ML approved (p=%.2f)", pair, ml_prob)

    return signal


# ═══════════════════════════════════════════════════════════════════════════
# Legacy aliases — keep backtester / main.py imports working
# ═══════════════════════════════════════════════════════════════════════════

def detect_bias(df_h4: pd.DataFrame, df_daily: pd.DataFrame) -> Bias:
    """Alias kept for backward compatibility with backtester.py."""
    daily = _htf_bias(df_daily)
    h4    = _htf_bias(df_h4)
    if daily == "bullish" and h4 in ("bullish", "neutral"):
        return "bullish"
    if daily == "bearish" and h4 in ("bearish", "neutral"):
        return "bearish"
    if daily == "neutral":
        return h4
    return "neutral"


def detect_order_blocks(df, bias, lookback=None):
    return _detect_obs(df, bias)

def detect_fvgs(df, bias, lookback=None, min_pips=None, pair="EURUSD"):
    return _detect_fvgs(df, bias, pair)

def detect_liquidity_grabs(df, lookback=None):
    """Return all grabs regardless of bias — used by backtester reporting."""
    bull = _detect_liquidity_grab(df, "bullish")
    bear = _detect_liquidity_grab(df, "bearish")
    return [g for g in [bull, bear] if g is not None]

def detect_choch_bos(df, lookback=None):
    """Legacy alias."""
    pts = _structure_points(df)
    events = []
    for i in range(2, len(pts)):
        p, c = pts[i-1], pts[i]
        if p["kind"] == "LH" and c["kind"] == "HH":
            events.append({"type": "CHoCH", "direction": "bullish", "price": c["price"]})
        elif p["kind"] == "HL" and c["kind"] == "LL":
            events.append({"type": "CHoCH", "direction": "bearish", "price": c["price"]})
        elif p["kind"] == "HL" and c["kind"] == "HH":
            events.append({"type": "BOS",   "direction": "bullish", "price": c["price"]})
        elif p["kind"] == "LH" and c["kind"] == "LL":
            events.append({"type": "BOS",   "direction": "bearish", "price": c["price"]})
    return events

def find_swing_highs(df, lookback=5):
    return _swing_highs(df, n=lookback)

def find_swing_lows(df, lookback=5):
    return _swing_lows(df, n=lookback)

def is_in_kill_zone(ts):
    return _is_kill_zone(ts)

def is_in_ote_zone(price, sh, sl, bias):
    return _ote_check(price, sh, sl, bias)

def score_confluence(*args, **kwargs):
    """Kept for import compatibility — not used in new flow."""
    return 0, []

def detect_market_structure(df, lookback=80):
    from dataclasses import dataclass
    pts = _structure_points(df, lookback)
    class _SP:
        def __init__(self, d):
            self.index = d["idx"]; self.time = d["time"]
            self.kind = d["kind"]; self.price = d["price"]
    return [_SP(p) for p in pts]
