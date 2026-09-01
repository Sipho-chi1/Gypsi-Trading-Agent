"""Trade history + performance endpoints, read-only from Postgres."""
# pyright: reportMissingImports=false
from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import get_session
from app.schemas.trade import TradeOut

router = APIRouter()


@router.get("", response_model=list[TradeOut])
async def list_trades(limit: int = 50):
    async with get_session() as session:
        result = await session.execute(
            text("SELECT * FROM trades ORDER BY created_at DESC LIMIT :limit"),
            {"limit": limit},
        )
        trades = []

        for row in result:
            trade = TradeOut(**row._mapping)
            trades.append(trade)

        return trades


@router.get("/performance")
async def performance_summary():
    """Aggregate overall trading performance for the dashboard."""

    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT * FROM trades "
                "ORDER BY created_at DESC"
            )
        )

        trades = []

        for row in result:
            trade = TradeOut(**row._mapping)
            trades.append(trade)

        total_trades = len(trades)

        closed_trades = [
            trade for trade in trades
            if trade.status == "closed"
        ]

        winning_trades = [
            trade for trade in closed_trades
            if trade.pnl is not None and trade.pnl > 0
        ]

        losing_trades = [
            trade for trade in closed_trades
            if trade.pnl is not None and trade.pnl < 0
        ]

        total_pnl = sum(
            trade.pnl
            for trade in closed_trades
            if trade.pnl is not None
        )

        win_rate = (
            len(winning_trades) / len(closed_trades) * 100
            if closed_trades
            else 0
        )

        average_pnl = (
            total_pnl / len(closed_trades)
            if closed_trades
            else 0
        )

        verdict_accuracy = {
            "approve": sum(
                1
                for trade in trades
                if trade.verdict_decision == "approve"
            ),
            "downsize": sum(
                1
                for trade in trades
                if trade.verdict_decision == "downsize"
            ),
            "reject": sum(
                1
                for trade in trades
                if trade.verdict_decision == "reject"
            ),
        }

        return {
            "total_trades": total_trades,
            "closed_trades": len(closed_trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "average_pnl": round(average_pnl, 2),
            "verdict_accuracy": verdict_accuracy,
        }