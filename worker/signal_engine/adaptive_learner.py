"""
PORTED FROM: forex_bot/adaptive_learner.py — reused as-is, extension pending.

TODO (Gypsi extension, see docs/ARCHITECTURE.md):
  - Fix the `len(history) % 20 == 0` trigger in record_and_adapt() — it can
    skip the check entirely when multiple trades close in one iteration.
    Track the count at last adaptation and use a `>=` threshold instead.
  - Extend LearnedTrade with Round Table context: verdict, bias_flags,
    market_agent_agreed, gate_size_factor.
  - Add two new insight categories in analyse_mistakes():
      * round_table_accuracy — do downsized/partial-consensus trades
        actually underperform full-consensus trades?
      * bias_flag_predictiveness — per flag type, does it actually
        predict a loss? This is what lets adapt_config() tune the
        Round Table's own thresholds, not just SMC parameters.
  - NEW SMC/KILLZONE INSIGHT CATEGORIES UNLOCKED (Flagged for implementation):
      * session_win_rates: Track separate performance for London, NY_AM,
        London_Close, Asian, and Silver Bullet sub-windows.
      * breaker_vs_ob_performance: Compare edge of Breaker Blocks vs standard OBs.
      * ifvg_vs_fvg_performance: Compare Inversion FVGs vs standard 3-candle FVGs.
      * amd_phase_accuracy: Evaluate win rate when entries align with the daily
        Distribution phase vs entering during Asian Accumulation or Manipulation.
      * killzone_overlap_edge: Quantify extra expectancy during London/NY overlap.

adaptive_learner.py — Adaptive learning system for the SMC Forex Bot.

How it works:
  1. After each backtest or live session, call `record_session(trades, pair)` to
     persist trade outcomes to `learning_data/trade_history.json`.
  2. `analyse_mistakes()` mines the history for loss patterns across:
       - Confluence score buckets (low-score trades losing more)
       - Time-of-day (UTC hour) performance
       - Pair-specific win rates
       - SL size buckets (oversized/undersized stops)
       - Kill zone vs non-kill-zone performance
       - OB vs FVG entry type performance
       - Consecutive loss streaks
  3. `adapt_config()` writes recommended parameter changes back to a
     `learning_data/adapted_config.json` overlay file.  `get_adaptive_config()`
     merges the overlay on top of the live config so the bot always uses the
     learned values without overwriting your .env or config.py.
  4. `generate_learning_report()` produces a human-readable markdown report.

Integration points (one line each in the files that already exist):
  backtester.py  → call `record_session(result.trades, result.pair)` at the end of run_backtest()
  main.py        → call `record_session(closed_trades, pair)` inside run_iteration()
  config.py      → nothing to change; the overlay is applied at bot startup via apply_adaptive_config()

Usage:
  python adaptive_learner.py --report        # view current learning report
  python adaptive_learner.py --reset         # wipe history and start fresh
  python adaptive_learner.py --apply         # print what would change in config
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

LEARNING_DIR  = Path("learning_data")
HISTORY_FILE  = LEARNING_DIR / "trade_history.json"
ADAPTED_FILE  = LEARNING_DIR / "adapted_config.json"
REPORT_FILE   = LEARNING_DIR / "learning_report.md"

# Minimum trades before we trust a pattern enough to adapt
MIN_TRADES_TO_LEARN = 20
MIN_TRADES_PER_BUCKET = 5


# ---------------------------------------------------------------------------
# Stored trade record (serialisable to JSON)
# ---------------------------------------------------------------------------

@dataclass
class LearnedTrade:
    trade_id:         str
    pair:             str
    bias:             str
    result:           str           # WIN / LOSS
    confluence_score: int
    sl_pips:          float
    rr_target:        float
    rr_achieved:      float
    pnl_usd:          float
    entry_hour_utc:   int           # 0-23
    in_kill_zone:     bool
    setup_type:       str           # "OB" | "FVG" | "OB+FVG"
    session_date:     str           # YYYY-MM-DD
    session_id:       str           # unique per backtest/paper run


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _load_history() -> list[dict]:
    LEARNING_DIR.mkdir(exist_ok=True)
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Could not load trade history: %s", e)
        return []


def _save_history(records: list[dict]) -> None:
    LEARNING_DIR.mkdir(exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(records, indent=2), encoding="utf-8")


def _load_adapted() -> dict:
    if not ADAPTED_FILE.exists():
        return {}
    try:
        return json.loads(ADAPTED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_adapted(cfg: dict) -> None:
    LEARNING_DIR.mkdir(exist_ok=True)
    ADAPTED_FILE.write_text(json.dumps(cfg, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
# Record a session
# ---------------------------------------------------------------------------

def record_session(trades: list, pair: str, session_id: Optional[str] = None) -> int:
    """
    Persist a list of completed trades from a backtest or live session.

    `trades` can be either BacktestTrade dataclasses or the closed-trade dicts
    that executor.check_paper_exits() returns — the function handles both.

    Returns the number of new records written.
    """
    if not trades:
        return 0

    session_id = session_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    today_str  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing   = _load_history()

    new_records: list[dict] = []
    for i, t in enumerate(trades):
        # Normalise — accept both dataclass and dict
        if hasattr(t, "__dataclass_fields__"):
            d = asdict(t)
        elif isinstance(t, dict):
            d = t
        else:
            continue

        result = str(d.get("result", "")).upper()
        if result not in ("WIN", "LOSS"):
            continue  # skip OPEN or unknown

        # Determine setup type from reason string if available
        reason = str(d.get("reason", ""))
        if "OB" in reason and "FVG" in reason:
            setup_type = "OB+FVG"
        elif "OB" in reason:
            setup_type = "OB"
        elif "FVG" in reason:
            setup_type = "FVG"
        else:
            setup_type = "OB"  # default

        # Entry hour — prefer real UTC hour stored by backtester, fall back to proxies
        entry_hour = 0
        if "entry_hour_utc" in d and d["entry_hour_utc"] is not None:
            entry_hour = int(d["entry_hour_utc"])   # real hour from backtester/live
        elif "opened_at" in d and d["opened_at"] is not None:
            ts = d["opened_at"]
            if isinstance(ts, datetime):
                entry_hour = ts.hour
            elif isinstance(ts, str):
                try:
                    entry_hour = datetime.fromisoformat(ts).hour
                except Exception:
                    pass
        elif "entry_bar" in d:
            # Last resort proxy — avoid if possible
            entry_hour = int(d.get("entry_bar", 0)) % 24

        rec = LearnedTrade(
            trade_id         = f"{session_id}_{i:04d}",
            pair             = str(d.get("pair", pair)),
            bias             = str(d.get("bias", "")),
            result           = result,
            confluence_score = int(d.get("confluence_score", d.get("score", 0))),
            sl_pips          = float(d.get("sl_pips", 0.0)),
            rr_target        = float(d.get("rr_achieved", d.get("rr", 0.0)) or 0.0),
            rr_achieved      = float(d.get("rr_achieved", 0.0) or 0.0),
            pnl_usd          = float(d.get("pnl_usd", 0.0) or 0.0),
            entry_hour_utc   = entry_hour,
            in_kill_zone     = bool(d.get("in_kill_zone", False)),
            setup_type       = setup_type,
            session_date     = today_str,
            session_id       = session_id,
        )
        new_records.append(asdict(rec))

    existing.extend(new_records)
    _save_history(existing)
    logger.info("AdaptiveLearner: saved %d new trade records (total: %d)",
                len(new_records), len(existing))
    return len(new_records)


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def _win_rate(trades: list[dict]) -> float:
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t["result"] == "WIN")
    return wins / len(trades) * 100


def _profit_factor(trades: list[dict]) -> float:
    gross_win  = sum(t["pnl_usd"] for t in trades if t["pnl_usd"] > 0)
    gross_loss = abs(sum(t["pnl_usd"] for t in trades if t["pnl_usd"] < 0))
    if gross_loss == 0:
        return float("inf") if gross_win > 0 else 0.0
    return round(gross_win / gross_loss, 2)


@dataclass
class LearningInsight:
    """A single discovered pattern with an optional recommended action."""
    category:       str
    description:    str
    sample_size:    int
    win_rate:       float
    profit_factor:  float
    severity:       str   # "critical" | "warning" | "info"
    recommendation: str
    param_changes:  dict[str, Any] = field(default_factory=dict)  # suggested config tweaks


def analyse_mistakes(min_total: int = MIN_TRADES_TO_LEARN) -> list[LearningInsight]:
    """
    Mine the full trade history for loss patterns.
    Returns a list of LearningInsight objects sorted by severity.
    """
    history = _load_history()
    if len(history) < min_total:
        logger.info("Not enough data to analyse (%d < %d)", len(history), min_total)
        return []

    insights: list[LearningInsight] = []
    overall_wr = _win_rate(history)

    # ── 1. Confluence score buckets ────────────────────────────────────────
    score_buckets: dict[int, list[dict]] = defaultdict(list)
    for t in history:
        score_buckets[t["confluence_score"]].append(t)

    worst_score = None
    worst_wr    = overall_wr

    for score, bucket in sorted(score_buckets.items()):
        if len(bucket) < MIN_TRADES_PER_BUCKET:
            continue
        wr = _win_rate(bucket)
        pf = _profit_factor(bucket)

        if wr < overall_wr - 10 and wr < 40:
            severity = "critical" if wr < 30 else "warning"
            insights.append(LearningInsight(
                category      = "confluence_score",
                description   = f"Score={score} trades have {wr:.1f}% win rate ({len(bucket)} trades)",
                sample_size   = len(bucket),
                win_rate      = wr,
                profit_factor = pf,
                severity      = severity,
                recommendation= f"Raise MIN_CONFLUENCE_SCORE above {score}",
                param_changes = {"MIN_CONFLUENCE_SCORE": score + 1},
            ))
            if wr < worst_wr:
                worst_wr    = wr
                worst_score = score

    # ── 2. Time-of-day analysis ────────────────────────────────────────────
    hour_buckets: dict[int, list[dict]] = defaultdict(list)
    for t in history:
        hour_buckets[t["entry_hour_utc"]].append(t)

    bad_hours:  list[int] = []
    good_hours: list[int] = []

    for hour, bucket in sorted(hour_buckets.items()):
        if len(bucket) < MIN_TRADES_PER_BUCKET:
            continue
        wr = _win_rate(bucket)
        pf = _profit_factor(bucket)

        if wr < overall_wr - 15 and pf < 1.0:
            bad_hours.append(hour)
            insights.append(LearningInsight(
                category      = "time_of_day",
                description   = f"UTC hour {hour:02d}:00 has {wr:.1f}% WR, PF={pf} ({len(bucket)} trades)",
                sample_size   = len(bucket),
                win_rate      = wr,
                profit_factor = pf,
                severity      = "warning",
                recommendation= f"Avoid trading at UTC hour {hour:02d}",
                param_changes = {"BAD_HOURS_UTC": bad_hours},
            ))
        elif wr > overall_wr + 10 and pf > 1.8:
            good_hours.append(hour)

    if good_hours:
        insights.append(LearningInsight(
            category      = "time_of_day",
            description   = f"Best performing hours UTC: {good_hours}",
            sample_size   = sum(len(hour_buckets[h]) for h in good_hours),
            win_rate      = _win_rate([t for h in good_hours for t in hour_buckets[h]]),
            profit_factor = _profit_factor([t for h in good_hours for t in hour_buckets[h]]),
            severity      = "info",
            recommendation= f"Prioritise entries during UTC hours {good_hours}",
            param_changes = {"PREFERRED_HOURS_UTC": good_hours},
        ))

    # ── 3. Pair performance ────────────────────────────────────────────────
    pair_buckets: dict[str, list[dict]] = defaultdict(list)
    for t in history:
        pair_buckets[t["pair"]].append(t)

    bad_pairs:  list[str] = []
    good_pairs: list[str] = []

    for pair, bucket in sorted(pair_buckets.items()):
        if len(bucket) < MIN_TRADES_PER_BUCKET:
            continue
        wr = _win_rate(bucket)
        pf = _profit_factor(bucket)

        if wr < 35 and pf < 0.9:
            bad_pairs.append(pair)
            insights.append(LearningInsight(
                category      = "pair_performance",
                description   = f"{pair}: {wr:.1f}% WR, PF={pf} ({len(bucket)} trades)",
                sample_size   = len(bucket),
                win_rate      = wr,
                profit_factor = pf,
                severity      = "critical" if pf < 0.7 else "warning",
                recommendation= f"Consider removing {pair} from PAIRS until strategy improves",
                param_changes = {"PAIRS_TO_AVOID": bad_pairs},
            ))
        elif wr > 50 and pf > 2.0:
            good_pairs.append(pair)

    if good_pairs:
        insights.append(LearningInsight(
            category      = "pair_performance",
            description   = f"Top performing pairs: {good_pairs}",
            sample_size   = sum(len(pair_buckets[p]) for p in good_pairs),
            win_rate      = _win_rate([t for p in good_pairs for t in pair_buckets[p]]),
            profit_factor = _profit_factor([t for p in good_pairs for t in pair_buckets[p]]),
            severity      = "info",
            recommendation= f"Increase lot sizing or trade frequency for {good_pairs}",
            param_changes = {"PREFERRED_PAIRS": good_pairs},
        ))

    # ── 4. SL size analysis ────────────────────────────────────────────────
    all_sl = [t["sl_pips"] for t in history if t["sl_pips"] > 0]
    if all_sl:
        median_sl = sorted(all_sl)[len(all_sl) // 2]
        small_sl  = [t for t in history if t["sl_pips"] < median_sl * 0.6]
        large_sl  = [t for t in history if t["sl_pips"] > median_sl * 1.5]

        if len(small_sl) >= MIN_TRADES_PER_BUCKET:
            wr = _win_rate(small_sl)
            pf = _profit_factor(small_sl)
            if wr < 35:
                insights.append(LearningInsight(
                    category      = "sl_sizing",
                    description   = f"Very tight SL (<{median_sl * 0.6:.0f} pips): {wr:.1f}% WR — getting stopped out prematurely",
                    sample_size   = len(small_sl),
                    win_rate      = wr,
                    profit_factor = pf,
                    severity      = "warning",
                    recommendation= "Widen minimum SL or use ATR-based floor",
                    param_changes = {"MIN_SL_PIPS": round(median_sl * 0.7, 1)},
                ))

        if len(large_sl) >= MIN_TRADES_PER_BUCKET:
            wr = _win_rate(large_sl)
            pf = _profit_factor(large_sl)
            if wr < 40:
                insights.append(LearningInsight(
                    category      = "sl_sizing",
                    description   = f"Oversized SL (>{median_sl * 1.5:.0f} pips): {wr:.1f}% WR, PF={pf}",
                    sample_size   = len(large_sl),
                    win_rate      = wr,
                    profit_factor = pf,
                    severity      = "warning",
                    recommendation= f"Lower MAX_SL_PIPS from current value",
                    param_changes = {"MAX_SL_PIPS": int(median_sl * 1.3)},
                ))

    # ── 5. Kill zone vs non-kill-zone ─────────────────────────────────────
    kz_trades     = [t for t in history if t.get("in_kill_zone")]
    non_kz_trades = [t for t in history if not t.get("in_kill_zone")]

    if len(kz_trades) >= MIN_TRADES_PER_BUCKET and len(non_kz_trades) >= MIN_TRADES_PER_BUCKET:
        kz_wr     = _win_rate(kz_trades)
        non_kz_wr = _win_rate(non_kz_trades)
        kz_pf     = _profit_factor(kz_trades)
        non_kz_pf = _profit_factor(non_kz_trades)

        if non_kz_wr < kz_wr - 12 and non_kz_pf < 1.0:
            insights.append(LearningInsight(
                category      = "kill_zone",
                description   = (f"Kill zone: {kz_wr:.1f}% WR vs non-kill-zone: {non_kz_wr:.1f}% WR — "
                                 f"outside-kill-zone trades are dragging results"),
                sample_size   = len(non_kz_trades),
                win_rate      = non_kz_wr,
                profit_factor = non_kz_pf,
                severity      = "critical",
                recommendation= "Enforce strict kill-zone-only entries",
                param_changes = {"REQUIRE_KILL_ZONE": True},
            ))
        elif kz_wr < non_kz_wr - 10:
            insights.append(LearningInsight(
                category      = "kill_zone",
                description   = (f"Non-kill-zone trades outperforming ({non_kz_wr:.1f}% vs {kz_wr:.1f}%) — "
                                 f"kill zones may be too narrow for this market"),
                sample_size   = len(kz_trades),
                win_rate      = kz_wr,
                profit_factor = kz_pf,
                severity      = "info",
                recommendation= "Consider expanding kill zone windows or relaxing the requirement",
                param_changes = {"REQUIRE_KILL_ZONE": False},
            ))

    # ── 6. Setup type (OB vs FVG) ─────────────────────────────────────────
    ob_trades  = [t for t in history if "OB" in t.get("setup_type", "")]
    fvg_trades = [t for t in history if t.get("setup_type") == "FVG"]

    if len(ob_trades) >= MIN_TRADES_PER_BUCKET and len(fvg_trades) >= MIN_TRADES_PER_BUCKET:
        ob_wr  = _win_rate(ob_trades)
        fvg_wr = _win_rate(fvg_trades)
        ob_pf  = _profit_factor(ob_trades)
        fvg_pf = _profit_factor(fvg_trades)

        if fvg_wr < ob_wr - 15 and fvg_pf < 1.0:
            insights.append(LearningInsight(
                category      = "setup_type",
                description   = f"FVG entries: {fvg_wr:.1f}% WR vs OB entries: {ob_wr:.1f}% WR",
                sample_size   = len(fvg_trades),
                win_rate      = fvg_wr,
                profit_factor = fvg_pf,
                severity      = "warning",
                recommendation= "Increase FVG minimum size or require OB confluence for FVG entries",
                param_changes = {"FVG_MIN_SIZE_PIPS": 3.0},
            ))
        elif ob_wr < fvg_wr - 15 and ob_pf < 1.0:
            insights.append(LearningInsight(
                category      = "setup_type",
                description   = f"OB entries underperforming FVG ({ob_wr:.1f}% vs {fvg_wr:.1f}% WR)",
                sample_size   = len(ob_trades),
                win_rate      = ob_wr,
                profit_factor = ob_pf,
                severity      = "warning",
                recommendation= "Raise OB_IMPULSE_FACTOR to filter weaker order blocks",
                param_changes = {"OB_IMPULSE_FACTOR": 1.6},
            ))

    # ── 7. Consecutive loss streak analysis ───────────────────────────────
    max_streak = streak = 0
    streak_trades: list[list[dict]] = [[]]
    current_streak_trades: list[dict] = []

    for t in history:
        if t["result"] == "LOSS":
            streak += 1
            current_streak_trades.append(t)
            if streak > max_streak:
                max_streak = streak
        else:
            if current_streak_trades:
                streak_trades.append(current_streak_trades[:])
            streak = 0
            current_streak_trades = []

    if max_streak > 5:
        insights.append(LearningInsight(
            category      = "drawdown_control",
            description   = f"Longest losing streak: {max_streak} consecutive losses",
            sample_size   = max_streak,
            win_rate      = 0.0,
            profit_factor = 0.0,
            severity      = "critical" if max_streak > 8 else "warning",
            recommendation= f"Lower MAX_CONSECUTIVE_LOSS to {max(2, max_streak - 2)} and increase pause duration",
            param_changes = {"MAX_CONSECUTIVE_LOSS": max(2, max_streak - 2)},
        ))

    # Sort: critical first, then warning, then info
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    insights.sort(key=lambda x: severity_order.get(x.severity, 3))

    return insights


# ---------------------------------------------------------------------------
# Config adaptation
# ---------------------------------------------------------------------------

def adapt_config(insights: Optional[list[LearningInsight]] = None) -> dict:
    """
    Merge all param_changes from insights into a single overlay dict.
    For conflicting keys, the most severe insight wins.
    Saves the result to learning_data/adapted_config.json.
    Returns the overlay dict.
    """
    if insights is None:
        insights = analyse_mistakes()

    overlay: dict[str, Any] = {}
    severity_order = {"critical": 0, "warning": 1, "info": 2}

    # Track which severity set each key (lower = more severe)
    key_severity: dict[str, int] = {}

    for insight in insights:
        sev = severity_order.get(insight.severity, 3)
        for key, value in insight.param_changes.items():
            existing_sev = key_severity.get(key, 99)
            if sev <= existing_sev:
                overlay[key] = value
                key_severity[key] = sev

    # Special merge for list-type keys (accumulate rather than overwrite)
    list_keys = {"BAD_HOURS_UTC", "PREFERRED_HOURS_UTC", "PAIRS_TO_AVOID", "PREFERRED_PAIRS"}
    for key in list_keys:
        all_vals: list = []
        for insight in insights:
            if key in insight.param_changes:
                vals = insight.param_changes[key]
                if isinstance(vals, list):
                    all_vals.extend(v for v in vals if v not in all_vals)
        if all_vals:
            overlay[key] = all_vals

    # Add metadata
    overlay["_generated_at"] = datetime.now(timezone.utc).isoformat()
    overlay["_total_trades_analysed"] = len(_load_history())
    overlay["_insights_count"] = len(insights)

    _save_adapted(overlay)
    logger.info("AdaptiveLearner: saved %d config adaptations", len(overlay) - 3)
    return overlay


def get_adaptive_config() -> dict:
    """
    Return the current config overlay merged with live config values.
    Call this at bot startup to get the adapted parameters.

    Usage in config.py or main.py:
        from adaptive_learner import get_adaptive_config
        ADAPTIVE = get_adaptive_config()
        MIN_CONFLUENCE_SCORE = ADAPTIVE.get("MIN_CONFLUENCE_SCORE", MIN_CONFLUENCE_SCORE)
    """
    return _load_adapted()


def apply_adaptive_config() -> dict:
    """
    Load the adapted config and patch the live `config` module in-place.
    Call once at bot startup (after import config).

    Returns the dict of changes applied.
    """
    try:
        import config as cfg
    except ImportError:
        return {}

    overlay  = _load_adapted()
    applied  = {}
    # Only apply numeric / boolean / simple list params that exist in config
    safe_keys = {
        "MIN_CONFLUENCE_SCORE", "MAX_SL_PIPS", "MIN_RR",
        "FVG_MIN_SIZE_PIPS", "OB_IMPULSE_FACTOR", "MAX_CONSECUTIVE_LOSS",
        "MIN_DAILY_ATR", "MIN_ADX_H1", "MAX_SPREAD_MAJORS",
    }
    for key in safe_keys:
        if key in overlay and hasattr(cfg, key):
            old_val = getattr(cfg, key)
            new_val = overlay[key]
            if old_val != new_val:
                setattr(cfg, key, new_val)
                applied[key] = {"from": old_val, "to": new_val}
                logger.info("AdaptiveLearner: %s  %s → %s", key, old_val, new_val)

    # Kill-zone enforcement flag (not in original config — add it)
    if "REQUIRE_KILL_ZONE" in overlay:
        setattr(cfg, "REQUIRE_KILL_ZONE", overlay["REQUIRE_KILL_ZONE"])
        applied["REQUIRE_KILL_ZONE"] = overlay["REQUIRE_KILL_ZONE"]

    return applied


# ---------------------------------------------------------------------------
# Learning report
# ---------------------------------------------------------------------------

def generate_learning_report(
    insights: Optional[list[LearningInsight]] = None,
    overlay:  Optional[dict] = None,
) -> str:
    """
    Generate a markdown report of what the bot has learned and what it changed.
    """
    history  = _load_history()
    insights = insights or analyse_mistakes()
    overlay  = overlay  or _load_adapted()

    if not history:
        return "# Adaptive Learning Report\n\n_No trade history yet._\n"

    # Overall stats
    total   = len(history)
    wr      = _win_rate(history)
    pf      = _profit_factor(history)
    pairs   = list({t["pair"] for t in history})
    sessions= list({t["session_id"] for t in history})

    lines: list[str] = [
        "# Adaptive Learning Report",
        f"_Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "## Overview",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total trades analysed | {total} |",
        f"| Sessions recorded | {len(sessions)} |",
        f"| Pairs covered | {', '.join(sorted(pairs))} |",
        f"| Overall win rate | {wr:.1f}% |",
        f"| Overall profit factor | {pf} |",
        "",
    ]

    # ── Insights ──────────────────────────────────────────────────────────
    if not insights:
        lines += [
            "## Patterns Found",
            "",
            "_Not enough data yet (need at least "
            f"{MIN_TRADES_TO_LEARN} trades)._",
            "",
        ]
    else:
        critical = [i for i in insights if i.severity == "critical"]
        warnings = [i for i in insights if i.severity == "warning"]
        info     = [i for i in insights if i.severity == "info"]

        if critical:
            lines += ["## 🔴 Critical Issues", ""]
            for ins in critical:
                lines += [
                    f"### {ins.category.replace('_', ' ').title()}",
                    f"**{ins.description}**",
                    f"- Sample size: {ins.sample_size} trades",
                    f"- Win rate: {ins.win_rate:.1f}%  |  Profit factor: {ins.profit_factor}",
                    f"- **Recommendation:** {ins.recommendation}",
                    "",
                ]

        if warnings:
            lines += ["## 🟡 Warnings", ""]
            for ins in warnings:
                lines += [
                    f"### {ins.category.replace('_', ' ').title()}",
                    f"**{ins.description}**",
                    f"- Sample size: {ins.sample_size} trades",
                    f"- Win rate: {ins.win_rate:.1f}%  |  Profit factor: {ins.profit_factor}",
                    f"- **Recommendation:** {ins.recommendation}",
                    "",
                ]

        if info:
            lines += ["## 🟢 Optimisation Opportunities", ""]
            for ins in info:
                lines += [
                    f"### {ins.category.replace('_', ' ').title()}",
                    ins.description,
                    f"- **Suggestion:** {ins.recommendation}",
                    "",
                ]

    # ── Config changes applied ────────────────────────────────────────────
    safe_keys = [k for k in overlay if not k.startswith("_")]
    if safe_keys:
        lines += [
            "## Config Adaptations Applied",
            "",
            "| Parameter | Adapted Value | Source |",
            "|-----------|--------------|--------|",
        ]
        for key in sorted(safe_keys):
            source = next(
                (i.category for i in insights if key in i.param_changes), "manual"
            )
            lines.append(f"| `{key}` | `{overlay[key]}` | {source} |")
        lines.append("")
    else:
        lines += [
            "## Config Adaptations Applied",
            "",
            "_No adaptations made yet (not enough data or no poor patterns found)._",
            "",
        ]

    # ── Performance by score heatmap (text table) ────────────────────────
    score_buckets: dict[int, list[dict]] = defaultdict(list)
    for t in history:
        score_buckets[t["confluence_score"]].append(t)

    if score_buckets:
        lines += [
            "## Performance by Confluence Score",
            "",
            "| Score | Trades | Win% | Profit Factor | Verdict |",
            "|-------|--------|------|---------------|---------|",
        ]
        for score in sorted(score_buckets.keys()):
            bucket = score_buckets[score]
            if len(bucket) < 2:
                continue
            b_wr  = _win_rate(bucket)
            b_pf  = _profit_factor(bucket)
            verdict = (
                "✅ Trade" if b_wr >= 40 and b_pf > 1.5 else
                "⚠️  Marginal" if b_wr >= 35 else
                "❌ Avoid"
            )
            lines.append(
                f"| {score} | {len(bucket)} | {b_wr:.0f}% | {b_pf} | {verdict} |"
            )
        lines.append("")

    # ── Per-pair breakdown ────────────────────────────────────────────────
    pair_buckets: dict[str, list[dict]] = defaultdict(list)
    for t in history:
        pair_buckets[t["pair"]].append(t)

    if pair_buckets:
        lines += [
            "## Per-Pair Performance",
            "",
            "| Pair | Trades | Win% | Profit Factor | Verdict |",
            "|------|--------|------|---------------|---------|",
        ]
        for pair in sorted(pair_buckets.keys()):
            bucket = pair_buckets[pair]
            if not bucket:
                continue
            p_wr  = _win_rate(bucket)
            p_pf  = _profit_factor(bucket)
            verdict = (
                "✅ Keep" if p_wr >= 40 and p_pf > 1.5 else
                "⚠️  Monitor" if p_wr >= 35 else
                "❌ Drop"
            )
            lines.append(
                f"| {pair} | {len(bucket)} | {p_wr:.0f}% | {p_pf} | {verdict} |"
            )
        lines.append("")

    # ── Hour of day breakdown ────────────────────────────────────────────
    hour_buckets: dict[int, list[dict]] = defaultdict(list)
    for t in history:
        hour_buckets[t["entry_hour_utc"]].append(t)

    if hour_buckets:
        lines += [
            "## Performance by UTC Entry Hour",
            "",
            "| Hour | Trades | Win% | Profit Factor |",
            "|------|--------|------|---------------|",
        ]
        for hour in sorted(hour_buckets.keys()):
            bucket = hour_buckets[hour]
            if len(bucket) < 3:
                continue
            h_wr = _win_rate(bucket)
            h_pf = _profit_factor(bucket)
            bar  = "█" * int(h_wr / 10)
            lines.append(
                f"| {hour:02d}:00 | {len(bucket)} | {h_wr:.0f}% {bar} | {h_pf} |"
            )
        lines.append("")

    report = "\n".join(lines)
    LEARNING_DIR.mkdir(exist_ok=True)
    REPORT_FILE.write_text(report, encoding="utf-8")
    return report


# ---------------------------------------------------------------------------
# Patch backtester.run_backtest to auto-record
# ---------------------------------------------------------------------------

def patch_backtester() -> None:
    """
    Monkey-patch backtester.run_backtest to automatically record trades
    and run adaptation after every backtest.  Call once at startup.

    Place in main.py:
        from adaptive_learner import patch_backtester
        patch_backtester()
    """
    try:
        import backtester
    except ImportError:
        return

    _original = backtester.run_backtest

    def _patched(*args, **kwargs):
        result = _original(*args, **kwargs)
        if result and result.trades:
            pair = result.pair
            n = record_session(result.trades, pair)
            if n > 0:
                insights = analyse_mistakes()
                overlay  = adapt_config(insights)
                apply_adaptive_config()
                report   = generate_learning_report(insights, overlay)
                logger.info("AdaptiveLearner: learning report → %s", REPORT_FILE)
        return result

    backtester.run_backtest = _patched
    logger.info("AdaptiveLearner: patched backtester.run_backtest")


# ---------------------------------------------------------------------------
# Hook for live/paper main loop
# ---------------------------------------------------------------------------

def record_and_adapt(closed_trades: list, pair: str) -> dict:
    """
    Convenience wrapper for main.py's run_iteration().
    Records new trades, re-analyses, adapts config, returns changes dict.

    Usage in main.py run_iteration():
        from adaptive_learner import record_and_adapt
        if closed:
            record_and_adapt(closed, pair)
    """
    if not closed_trades:
        return {}

    record_session(closed_trades, pair)
    history = _load_history()

    # Only re-run full analysis every 20 new trades to avoid thrashing config
    if len(history) % 20 == 0:
        insights = analyse_mistakes()
        overlay  = adapt_config(insights)
        changes  = apply_adaptive_config()
        generate_learning_report(insights, overlay)
        if changes:
            logger.info("AdaptiveLearner: config updated after %d trades | changes: %s",
                        len(history), changes)
        return changes
    return {}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(description="SMC Forex Bot — Adaptive Learner")
    parser.add_argument("--report", action="store_true", help="Generate and print learning report")
    parser.add_argument("--apply",  action="store_true", help="Print what config changes would be made")
    parser.add_argument("--reset",  action="store_true", help="Wipe all learning data (fresh start)")
    parser.add_argument("--stats",  action="store_true", help="Print summary statistics")
    args = parser.parse_args()

    if args.reset:
        for f in [HISTORY_FILE, ADAPTED_FILE, REPORT_FILE]:
            if f.exists():
                f.unlink()
                print(f"Deleted {f}")
        print("Learning data reset.")

    elif args.stats:
        history = _load_history()
        if not history:
            print("No trade history yet.")
        else:
            print(f"Total trades: {len(history)}")
            print(f"Win rate:     {_win_rate(history):.1f}%")
            print(f"Profit factor:{_profit_factor(history)}")
            pairs = sorted({t['pair'] for t in history})
            print(f"Pairs:        {', '.join(pairs)}")
            sessions = sorted({t['session_id'] for t in history})
            print(f"Sessions:     {len(sessions)}")

    elif args.apply:
        insights = analyse_mistakes()
        if not insights:
            print("Not enough data to generate adaptations yet.")
        else:
            overlay = adapt_config(insights)
            print("\nProposed config changes:")
            for k, v in overlay.items():
                if not k.startswith("_"):
                    print(f"  {k:35s} = {v}")

    else:  # --report or default
        insights = analyse_mistakes()
        overlay  = adapt_config(insights)
        report   = generate_learning_report(insights, overlay)
        print(report)
        print(f"\nReport saved to: {REPORT_FILE}")
