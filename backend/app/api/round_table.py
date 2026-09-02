"""Live/recent Round Table deliberations, for the dashboard's deliberation view."""
from fastapi import APIRouter  # type: ignore
from sqlalchemy import text

from app.core.database import get_session
from app.schemas.trade import RoundTableEntryOut

router = APIRouter()


@router.get("/recent", response_model=list[RoundTableEntryOut])
# query trades joined with their verdict/reasoning fields.
    
async def recent_deliberations(limit: int = Query(default=20, ge=1, le=100),):
    async with get_session() as session:
        result = await session.execute(
            text("""
                SELECT
                    symbol,
                    reasoning AS proposal_reasoning,
                    independent_reasoning,
                    verdict_decision AS decision,
                    bias_flags
                FROM trades
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )

        deliberations = []

        for row in result:
            data = dict(row._mapping)

            # Older trades may not contain Round Table bias flags.
            if data["bias_flags"] is None:
                data["bias_flags"] = []

            deliberations.append(
                RoundTableEntryOut(**data)
            )

        return deliberations