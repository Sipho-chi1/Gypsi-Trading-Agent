"""Live/recent Round Table deliberations, for the dashboard's deliberation view."""
from fastapi import APIRouter  # type: ignore

from app.schemas.trade import RoundTableEntryOut

router = APIRouter()


@router.get("/recent", response_model=list[RoundTableEntryOut])
async def recent_deliberations(limit: int = 20):
    # TODO: query trades joined with their verdict/reasoning fields.
    return []
