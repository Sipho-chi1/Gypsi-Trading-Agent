"""
SMC/ICT Configuration Module — Centralised parameters and Timezone-Aware Sessions.

Audited against ICT/SMC methodology specifications:
- Section 5: Premium/Discount & OTE Fibonacci levels
- Section 6: Timezone-aware Killzones anchored to America/New_York (and Europe/London)
             eliminating UTC fixed-offset daylight saving bugs.
- Section 3: Fair Value Gap thresholds
- Section 2 & 4: Order Blocks, Breakers, Liquidity and Market Structure lookbacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Literal
from zoneinfo import ZoneInfo

# ═══════════════════════════════════════════════════════════════════════════
# 1. TIMEZONES & KILLZONES (Section 6)
# ═══════════════════════════════════════════════════════════════════════════
# Timezones used for session anchoring (ICT standard is New York local time)
NY_TZ = ZoneInfo("America/New_York")
LON_TZ = ZoneInfo("Europe/London")
UTC_TZ = ZoneInfo("UTC")

@dataclass(frozen=True)
class SessionWindow:
    """Represents a trading session or killzone window in local time."""
    name: str
    start_time: time
    end_time: time
    tz: ZoneInfo = NY_TZ
    is_silver_bullet: bool = False
    weight: float = 1.0  # Confluence weighting multiplier


# ICT Standard Killzones defined strictly in New York Local Time (America/New_York)
# Section 6 of specification:
# - Asian Killzone: ~20:00 - 00:00 NY (Range accumulation)
# - London Killzone: ~02:00 - 05:00 NY (07:00 - 10:00 London)
# - New York AM Killzone: ~07:00 - 10:00 NY (Pre-market + open expansion)
#   (Configurable to 08:30 - 11:00 NY for NYSE Cash Open alignment)
# - London Close Killzone: ~10:00 - 12:00 NY (15:00 - 17:00 London)
# - Silver Bullet Windows:
#   * London Silver Bullet: 03:00 - 04:00 NY
#   * NY AM Silver Bullet: 10:00 - 11:00 NY
#   * NY PM Silver Bullet: 14:00 - 15:00 NY
KILLZONE_WINDOWS: list[SessionWindow] = [
    SessionWindow(name="Asian", start_time=time(20, 0), end_time=time(23, 59, 59), tz=NY_TZ, weight=0.8),
    SessionWindow(name="London", start_time=time(2, 0), end_time=time(5, 0), tz=NY_TZ, weight=1.2),
    SessionWindow(name="NY_AM", start_time=time(7, 0), end_time=time(10, 0), tz=NY_TZ, weight=1.3),
    SessionWindow(name="London_Close", start_time=time(10, 0), end_time=time(12, 0), tz=NY_TZ, weight=1.0),
    # Silver Bullet High-Probability sub-windows
    SessionWindow(name="Silver_Bullet_London", start_time=time(3, 0), end_time=time(4, 0), tz=NY_TZ, is_silver_bullet=True, weight=1.5),
    SessionWindow(name="Silver_Bullet_NY_AM", start_time=time(10, 0), end_time=time(11, 0), tz=NY_TZ, is_silver_bullet=True, weight=1.5),
    SessionWindow(name="Silver_Bullet_NY_PM", start_time=time(14, 0), end_time=time(15, 0), tz=NY_TZ, is_silver_bullet=True, weight=1.4),
]

# Legacy tuple format for backward compatibility, mapped to NY hour equivalents
KILL_ZONES = [
    (2, 5),    # London (02:00 - 05:00 NY)
    (7, 10),   # NY AM (07:00 - 10:00 NY)
    (10, 12),  # London Close (10:00 - 12:00 NY)
    (20, 24),  # Asian (20:00 - 24:00 NY)
]

# ═══════════════════════════════════════════════════════════════════════════
# 2. MARKET STRUCTURE & SWING DETECTION (Section 1)
# ═══════════════════════════════════════════════════════════════════════════
SWING_PIVOT_N: int = 3           # Required closed bars on each side for fractal pivot
STRUCTURE_LOOKBACK: int = 80     # Total bars scanned for swing structure points
HTF_MIN_SWING_POINTS: int = 4    # Minimum points required for clear HTF bias

# ═══════════════════════════════════════════════════════════════════════════
# 3. ORDER BLOCKS & BREAKER BLOCKS (Section 2)
# ═══════════════════════════════════════════════════════════════════════════
OB_LOOKBACK: int = 40            # Max lookback bars for valid Order Blocks
OB_IMPULSE_FACTOR: float = 1.2   # Displacement multiplier for subsequent candle body vs OB body
OB_MAX_MITIGATION_PCT: float = 1.0  # 100% penetration invalidates OB (becomes breaker candidate)
OB_ENTRY_CONVENTION: Literal["full", "body", "mean_threshold"] = "mean_threshold"

# ═══════════════════════════════════════════════════════════════════════════
# 4. FAIR VALUE GAPS (FVG) & INVERSION FVGS (Section 3)
# ═══════════════════════════════════════════════════════════════════════════
FVG_MIN_SIZE_PIPS: float = 2.0   # Default pip minimum for forex (fallback)
FVG_MIN_SIZE_TICKS: int = 4      # Asset-agnostic minimum gap size in ticks
FVG_MIN_ATR_PCT: float = 0.10    # Minimum FVG size as 10% of 14-period ATR
FVG_LOOKBACK: int = 40           # Max lookback bars for valid active FVGs

# ═══════════════════════════════════════════════════════════════════════════
# 5. LIQUIDITY & EQUAL HIGHS/LOWS (Section 4)
# ═══════════════════════════════════════════════════════════════════════════
LIQUIDITY_LOOKBACK: int = 60     # Bars scanned for resting liquidity pools
EQH_TOLERANCE_TICKS: int = 3     # Tolerance in ticks for classifying Equal Highs / Lows
EQH_TOLERANCE_ATR_PCT: float = 0.08  # 8% of ATR tolerance for EQH/EQL
MIN_EQUAL_TOUCHES: int = 2       # Minimum swing points required for EQH/EQL pool

# ═══════════════════════════════════════════════════════════════════════════
# 6. PREMIUM / DISCOUNT & OTE (Section 5)
# ═══════════════════════════════════════════════════════════════════════════
EQUILIBRIUM: float = 0.50        # Midpoint of dealing range
PREMIUM_ZONE: float = 0.50       # Upper half (favor sells / shorts)
DISCOUNT_ZONE: float = 0.50      # Lower half (favor buys / longs)
EXTREME_PREMIUM: float = 0.75    # High-conviction premium threshold
EXTREME_DISCOUNT: float = 0.25   # High-conviction discount threshold

# Optimal Trade Entry (OTE) Fibonacci Retracement Levels
OTE_FIBO_LOW: float = 0.618      # 61.8% golden ratio
OTE_FIBO_SWEET_SPOT: float = 0.705  # 70.5% ICT optimal sweet spot
OTE_FIBO_HIGH: float = 0.790     # 79.0% deep retracement boundary

# ═══════════════════════════════════════════════════════════════════════════
# 7. RISK & CONFLUENCE GATES
# ═══════════════════════════════════════════════════════════════════════════
MIN_RR: float = 2.0              # Minimum Risk:Reward ratio required
MAX_SL_PIPS: float = 35.0        # Max allowable Stop Loss distance in pips
MIN_CONFLUENCE_SCORE: int = 4    # Minimum confluence required to produce a valid signal
KILLZONE_REQUIRED: bool = False  # If True, signals outside killzones are rejected

TIMEFRAMES = {
    "daily": "D1",
    "high":  "H4",
    "mid":   "H1",
    "entry": "M5",
}
