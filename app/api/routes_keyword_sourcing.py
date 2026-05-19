import asyncio
import json
from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from starlette.responses import StreamingResponse

from app.core.config import Settings, get_settings
from app.services.keyword_sourcing import KeywordSourcingService

router = APIRouter(prefix="/api/admin", tags=["keyword-sourcing"])


@router.post("/keyword-sourcing/test")
async def run_keyword_sourcing_test(
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    state = KeywordSourcingService.start_background_run(settings, display_per_cid=30)
    return state


@router.post("/keyword-sourcing/stop")
async def stop_keyword_sourcing() -> Dict[str, Any]:
    return KeywordSourcingService.stop_active_run()


@router.get("/keyword-sourcing/status")
async def get_keyword_sourcing_status(run_id: Optional[str] = None) -> Dict[str, Any]:
    return KeywordSourcingService.get_progress_status(run_id=run_id)


@router.get("/keyword-sourcing/detail")
async def get_keyword_sourcing_detail(run_id: Optional[str] = None) -> Dict[str, Any]:
    return KeywordSourcingService.get_status(run_id=run_id)


@router.get("/keyword-sourcing/history")
async def get_keyword_sourcing_history(
    date_value: date,
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    return KeywordSourcingService.load_saved_result_for_date(
        settings,
        target_date=date_value,
    )


@router.get("/keyword-sourcing/stream")
async def stream_keyword_sourcing_status(run_id: Optional[str] = None) -> StreamingResponse:
    async def event_generator():
        yield "retry: 2000\n\n"
        while True:
            state = KeywordSourcingService.get_progress_status(run_id=run_id)
            yield f"data: {json.dumps(state, ensure_ascii=False)}\n\n"
            if state.get("status") in {"completed", "failed", "idle"}:
                break
            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/keyword-sourcing/start")
async def start_keyword_sourcing_via_form(
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    KeywordSourcingService.start_background_run(settings, display_per_cid=30)
    return RedirectResponse(url="/admin?tab=pipeline", status_code=303)
