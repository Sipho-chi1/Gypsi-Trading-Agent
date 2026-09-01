from fastapi import APIRouter  # type: ignore[reportMissingImports]

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}
