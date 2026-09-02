"""
Rewritten from forex_bot/journal_writer.py — writes to Postgres instead of
local JSON/markdown files, and now records the Round Table's verdict and
bias flags alongside each trade, not just the price-action outcome. This
extra context is what lets the adaptive learner measure the gate's own
accuracy later (see signal_engine/adaptive_learner.py TODOs).
"""
from sqlalchemy import text

from core.database import get_session


async def log_trade(instrument, signal, verdict, contract, position) -> None:

    if getattr(verdict, "independent_read", None) is not None:
        independent_reasoning = getattr(verdict.independent_read, "reasoning", None)

    async with get_session() as session:
        await session.execute(
            text("""
                INSERT INTO trades
                    (symbol, direction, entry, stop_loss, take_profit, reasoning, independent_reasoning,
                     verdict_decision, verdict_reason, bias_flags, size_factor,
                     contract_expiry, contract_strike, quantity, status)
                VALUES
                    (:symbol, :direction, :entry, :stop_loss, :take_profit, :reasoning, :independent_reasoning,
                     :verdict_decision, :verdict_reason, :bias_flags, :size_factor,
                     :contract_expiry, :contract_strike, :quantity, :status)
            """),
            {
                "symbol": instrument.symbol,
                "direction": signal.bias,
                "entry": signal.entry_price,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
                "reasoning": signal.reason,
                "independent_reasoning": independent_reasoning,
                "verdict_decision": verdict.decision,
                "verdict_reason": verdict.reason,
                "bias_flags": verdict.bias_flags,
                "size_factor": verdict.size_factor,
                "contract_expiry": contract.expiry,
                "contract_strike": contract.strike,
                "quantity": position.quantity,
                "status": position.status,
            },
        )
        await session.commit()


async def log_no_trade(instrument, reason: str) -> None:
    async with get_session() as session:
        await session.execute(
            text("""
                INSERT INTO trades (symbol, verdict_decision, verdict_reason, status)
                VALUES (:symbol, 'reject', :reason, 'skipped')
            """),
            {"symbol": instrument.symbol, "reason": reason},
        )
        await session.commit()
