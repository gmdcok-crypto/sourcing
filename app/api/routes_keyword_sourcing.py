import asyncio
import io
import json
from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, Form
from fastapi.responses import JSONResponse, RedirectResponse, Response
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from starlette.responses import StreamingResponse

from app.core.config import Settings, get_settings
from app.services.coupang_crawler import CoupangCrawlerService
from app.services.keyword_sourcing import KeywordSourcingService

router = APIRouter(prefix="/api/admin", tags=["keyword-sourcing"])


def _safe_excel_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, str):
        return ILLEGAL_CHARACTERS_RE.sub("", value)
    return value


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
async def get_keyword_sourcing_status(run_id: Optional[str] = None) -> JSONResponse:
    payload = KeywordSourcingService.get_progress_status(run_id=run_id)
    return JSONResponse(
        content=payload,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )


@router.get("/keyword-sourcing/events")
async def stream_keyword_sourcing_events(run_id: Optional[str] = None) -> StreamingResponse:
    """SSE — 새로고침 없이 진행 상태·로그 실시간 전달."""

    async def event_generator():
        resolved_run_id = str(run_id or "").strip() or None
        last_signature = ""
        idle_ticks = 0

        while idle_ticks < 6:
            state = KeywordSourcingService.get_progress_status(run_id=resolved_run_id)
            if state.get("run_id"):
                resolved_run_id = str(state["run_id"])

            signature = "|".join(
                [
                    str(state.get("updated_at") or ""),
                    str(state.get("log_count") or len(state.get("logs") or [])),
                    str(state.get("progress_percent") or 0),
                    str(state.get("processed_categories") or 0),
                    str(state.get("status") or ""),
                    str(state.get("message") or ""),
                ]
            )
            if signature != last_signature:
                last_signature = signature
                yield f"data: {json.dumps(state, ensure_ascii=False)}\n\n"

            status = str(state.get("status") or "")
            if status in {"completed", "failed"}:
                break
            if status == "running":
                idle_ticks = 0
            else:
                idle_ticks += 1

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/keyword-sourcing/detail")
async def get_keyword_sourcing_detail(run_id: Optional[str] = None) -> Dict[str, Any]:
    return KeywordSourcingService.get_export_state(run_id=run_id)


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
    selected_run_id = str(run_id or "").strip() or None
    state = KeywordSourcingService.get_export_state(run_id=selected_run_id)

    from app.api.routes_admin import build_keyword_summary_rows_data

    rows = build_keyword_summary_rows_data(state)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "keyword-results"
    headers = [
        "테마 세부위치",
        "키워드명",
        "소속그룹",
        "검색량",
        "클릭률",
        "경쟁강도",
        "노출광고수",
        "광고효율",
        "시즌",
        "등록상품수",
        "독점의심",
    ]
    worksheet.append(headers)
    for row in rows:
        worksheet.append(
            [
                _safe_excel_cell(row.get("themeDetail", "")),
                _safe_excel_cell(row.get("keyword", "")),
                _safe_excel_cell(row.get("group", "")),
                _safe_excel_cell(row.get("totalSearches", "")),
                _safe_excel_cell(row.get("clickRate", "")),
                _safe_excel_cell(row.get("competitionLevel", "")),
                _safe_excel_cell(row.get("exposureAds", "")),
                _safe_excel_cell(row.get("adEfficiency", "")),
                _safe_excel_cell(row.get("season", "")),
                _safe_excel_cell(row.get("productCount", "")),
                _safe_excel_cell(row.get("monopolySuspect", "")),
            ]
        )

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)

    filename = f"keyword-results-{date_value.isoformat() if date_value else (state.get('run_id') or 'latest')}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post("/keyword-sourcing/coupang-test")
async def run_coupang_crawling_test(
    payload: Optional[Dict[str, Any]] = Body(default=None),
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    run_id = payload.get("run_id") if payload else None
    limit = int(payload.get("limit") or 10) if payload else 10
    state = KeywordSourcingService.get_status(run_id=run_id)

    from app.api.routes_admin import build_keyword_summary_rows_data

    rows = build_keyword_summary_rows_data(state)
    keywords = []
    for row in rows:
        keyword = str(row.get("keyword") or "").strip()
        if keyword and keyword not in keywords:
            keywords.append(keyword)
        if len(keywords) >= limit:
            break

    if not keywords:
        return {
            "status": "error",
            "message": "크롤링할 키워드가 없습니다. 먼저 키워드 소싱 결과를 준비해주세요.",
            "items": [],
        }

    crawler = CoupangCrawlerService(settings)
    result = await crawler.crawl_keywords(keywords)
    return {
        "status": "ok",
        "message": f"{len(keywords)}개 키워드 기준 쿠팡 테스트 크롤링을 완료했습니다.",
        "keywords": keywords,
        **result,
    }


@router.get("/keyword-sourcing/crawler-keywords")
async def get_crawler_keywords(
    run_id: Optional[str] = None,
    date_value: Optional[date] = None,
    limit: int = 10,
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    if date_value is not None:
        state = KeywordSourcingService.load_saved_result_for_date(
            settings,
            target_date=date_value,
        )
        classified_keywords = state.get("classified_keywords") or []
        if not classified_keywords:
            classified_keywords = state.get("preview_rows") or []

        keywords = []
        seen_keywords = set()
        capped_limit = max(1, min(int(limit or 10), 100))

        for row in classified_keywords:
            keyword = str(
                row.get("keyword")
                or row.get("query")
                or row.get("seed_keyword")
                or ""
            ).strip()
            if not keyword or keyword in seen_keywords:
                continue
            seen_keywords.add(keyword)
            keywords.append(
                {
                    "keyword": keyword,
                    "group_name": row.get("group_name") or "-",
                    "theme_name": row.get("theme_name") or "",
                    "theme_detail": row.get("shopping_category_path")
                    or row.get("full_path")
                    or row.get("category_name")
                    or row.get("theme_name")
                    or "-",
                    "monthly_mobile_searches": row.get("monthly_mobile_searches")
                    or row.get("total_searches"),
                    "monthly_mobile_ctr": row.get("monthly_mobile_ctr"),
                    "competition_level": row.get("competition_level"),
                    "monthly_exposure_ads": row.get("monthly_exposure_ads"),
                    "product_count": row.get("product_count"),
                }
            )
            if len(keywords) >= capped_limit:
                break

        return {
            "status": "ok",
            "run_id": state.get("run_id"),
            "selected_date": date_value.isoformat(),
            "keyword_count": len(keywords),
            "keywords": keywords,
        }

    db_payload = KeywordSourcingService.get_final_keyword_rows(
        run_id=run_id,
        limit=limit,
    )
    if db_payload.get("keyword_count"):
        return {
            **db_payload,
            "selected_date": None,
        }
    state = KeywordSourcingService.get_status(run_id=run_id)
    classified_keywords = state.get("classified_keywords") or []
    if not classified_keywords:
        classified_keywords = state.get("preview_rows") or []

    keywords = []
    seen_keywords = set()
    capped_limit = max(1, min(int(limit or 10), 100))

    for row in classified_keywords:
        keyword = str(
            row.get("keyword")
            or row.get("query")
            or row.get("seed_keyword")
            or ""
        ).strip()
        if not keyword or keyword in seen_keywords:
            continue
        seen_keywords.add(keyword)
        keywords.append(
            {
                "keyword": keyword,
                "group_name": row.get("group_name") or "-",
                "theme_name": row.get("theme_name") or "",
                "theme_detail": row.get("shopping_category_path")
                or row.get("full_path")
                or row.get("category_name")
                or row.get("theme_name")
                or "-",
                "monthly_mobile_searches": row.get("monthly_mobile_searches")
                or row.get("total_searches"),
                "monthly_mobile_ctr": row.get("monthly_mobile_ctr"),
                "competition_level": row.get("competition_level"),
                "monthly_exposure_ads": row.get("monthly_exposure_ads"),
                "product_count": row.get("product_count"),
            }
        )
        if len(keywords) >= capped_limit:
            break

    return {
        "status": "ok",
        "run_id": state.get("run_id"),
        "selected_date": date_value.isoformat() if date_value else None,
        "keyword_count": len(keywords),
        "keywords": keywords,
    }


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
