from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from app.core.config import Settings, get_settings
from app.services.keyword_sourcing import KeywordSourcingService

router = APIRouter(prefix="/api/admin", tags=["keyword-sourcing"])


@router.post("/keyword-sourcing/test")
async def run_keyword_sourcing_test(
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    state = KeywordSourcingService.start_background_run(settings, display_per_cid=30)
    return state


@router.get("/keyword-sourcing/status")
async def get_keyword_sourcing_status(run_id: Optional[str] = None) -> Dict[str, Any]:
    return KeywordSourcingService.get_status(run_id=run_id)


@router.post("/keyword-sourcing/start")
async def start_keyword_sourcing_via_form(
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    KeywordSourcingService.start_background_run(settings, display_per_cid=30)
    return RedirectResponse(url="/admin?tab=pipeline", status_code=303)
