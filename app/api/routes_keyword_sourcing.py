import asyncio
import io
import json
from datetime import date
from typing import Any, Dict, Optional

import pandas as pd
from fastapi import APIRouter, Body, Depends, Form
from fastapi.responses import RedirectResponse
from starlette.responses import StreamingResponse

from app.core.config import Settings, get_settings
from app.services.keyword_sourcing import KeywordSourcingService

router = APIRouter(prefix="/api/admin", tags=["keyword-sourcing"])


@router.post("/keyword-sourcing/test")
async def run_keyword_sourcing_test(
    payload: Optional[Dict[str, Any]] = Body(default=None),
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    theme_id = payload.get("theme_id") if payload else None
    state = KeywordSourcingService.start_background_run(
        settings,
        display_per_cid=30,
        theme_id=theme_id,
    )
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


@router.get("/keyword-sourcing/export")
async def export_keyword_sourcing_excel(
    run_id: Optional[str] = None,
    date_value: Optional[date] = None,
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    if date_value is not None:
        state = KeywordSourcingService.load_saved_result_for_date(
            settings,
            target_date=date_value,
        )
    else:
        state = KeywordSourcingService.get_status(run_id=run_id)

    from app.api.routes_admin import build_keyword_summary_rows_data

    rows = build_keyword_summary_rows_data(state)
    dataframe = pd.DataFrame(
        rows,
        columns=[
            "themeDetail",
            "keyword",
            "group",
            "totalSearches",
            "clickRate",
            "competitionLevel",
            "exposureAds",
            "adEfficiency",
            "season",
            "productCount",
        ],
    )
    dataframe = dataframe.rename(
        columns={
            "themeDetail": "테마 세부위치",
            "keyword": "키워드명",
            "group": "소속그룹",
            "totalSearches": "검색량",
            "clickRate": "클릭률",
            "competitionLevel": "경쟁강도",
            "exposureAds": "노출광고수",
            "adEfficiency": "광고효율",
            "season": "시즌",
            "productCount": "등록상품수",
        }
    )

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, sheet_name="keyword-results", index=False)
    output.seek(0)

    filename = f"keyword-results-{date_value.isoformat() if date_value else (state.get('run_id') or 'latest')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
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
    theme_id: Optional[int] = Form(default=None),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    KeywordSourcingService.start_background_run(
        settings,
        display_per_cid=30,
        theme_id=theme_id,
    )
    return RedirectResponse(url="/admin?tab=pipeline", status_code=303)
