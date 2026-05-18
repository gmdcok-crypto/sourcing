from fastapi import APIRouter, Depends, Query

from app.core.config import Settings, get_settings
from app.schemas.keyword import KeywordSearchResponse
from app.services.naver_api import NaverShoppingService
from app.services.r2_storage import R2StorageService

router = APIRouter(prefix="/keywords", tags=["keywords"])


@router.get("/search", response_model=KeywordSearchResponse)
async def search_keywords(
    query: str = Query(..., min_length=1, description="Search keyword"),
    display: int = Query(10, ge=1, le=100),
    start: int = Query(1, ge=1, le=1000),
    sort: str = Query("sim", pattern="^(sim|date|asc|dsc)$"),
    settings: Settings = Depends(get_settings),
) -> KeywordSearchResponse:
    naver_service = NaverShoppingService(settings)
    r2_service = R2StorageService(settings)

    result = await naver_service.search_products(
        query=query,
        display=display,
        start=start,
        sort=sort,
    )
    r2_key = r2_service.save_search_result(query=query, payload=result)

    return KeywordSearchResponse(
        query=query,
        total=result.get("total", 0),
        start=result.get("start", start),
        display=result.get("display", display),
        items=result.get("items", []),
        saved_to_r2=bool(r2_key),
        r2_key=r2_key,
    )
