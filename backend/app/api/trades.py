"""Trade history + performance endpoints, read-only from Postgres."""
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
        # TODO: map rows -> TradeOut once the trades table migration exists.
        return []


@router.get("/performance")
async def performance_summary():
    """TODO: aggregate win rate, avg R, verdict-accuracy breakdown for the
    dashboard's performance chart."""
    return {"win_rate": None, "total_trades": 0, "verdict_accuracy": {}}
