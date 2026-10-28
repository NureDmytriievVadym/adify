from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["Operations"])


class HealthResponse(BaseModel):
    status: str = "ok"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Process liveness only; does not imply database or integration readiness."""
    return HealthResponse()
