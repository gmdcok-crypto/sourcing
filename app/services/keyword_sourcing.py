from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timezone
from statistics import median
from typing import Any, Dict, List, Optional

import pandas as pd

from app.services.db import get_mysql_connection
from app.services.naver_datalab import NaverShoppingInsightService
from app.services.keyword_noise import filter_noise
from app.services.naver_api import NaverShoppingService
from app.services.naver_searchad import NaverSearchAdService
from app.services.naver_search_trend import NaverSearchTrendService
from app.services.r2_storage import R2StorageService


@dataclass
class KeywordSourcingResult:
    run_id: str
    theme_count: int
    category_count: int
    row_count: int
    dataframe_columns: List[str]
    preview_rows: List[Dict[str, Any]]
    r2_json_key: str | None
    r2_parquet_key: str | None


class KeywordSourcingService:
    _runs: Dict[str, Dict[str, Any]] = {}
    _latest_run_id: Optional[str] = None
    _active_run_id: Optional[str] = None
    _active_task: Optional[asyncio.Task] = None
    CATEGORY_DELAY_SECONDS = 0.5

    def __init__(self, settings) -> None:
        self.settings = settings
        self.datalab_service = NaverShoppingInsightService(settings)
        self.searchad_service = NaverSearchAdService(settings)
        self.shopping_service = NaverShoppingService(settings)
        self.search_trend_service = NaverSearchTrendService(settings)
        self.r2_service = R2StorageService(settings)

    @classmethod
    def get_status(cls, run_id: Optional[str] = None) -> Dict[str, Any]:
        target_run_id = run_id or cls._active_run_id or cls._latest_run_id
        if not target_run_id or target_run_id not in cls._runs:
            return {
                "run_id": None,
                "status": "idle",
                "message": "아직 실행 이력이 없습니다.",
                "theme_count": 0,
                "category_count": 0,
                "processed_categories": 0,
                "row_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "progress_percent": 0,
                "current_theme_name": None,
                "current_cid": None,
                "current_query": None,
                "logs": [],
                "started_at": None,
                "finished_at": None,
                "r2_json_key": None,
                "r2_parquet_key": None,
                "valid_keywords": [],
                "noise_keywords": [],
                "top_keywords": [],
                "classified_keywords": [],
                "top150_count": 0,
                "top100_count": 0,
                "searchad_count": 0,
                "group_counts": {},
            }
        return cls._runs[target_run_id]

    @classmethod
    def get_progress_status(cls, run_id: Optional[str] = None) -> Dict[str, Any]:
        state = cls.get_status(run_id=run_id)
        return {
            "run_id": state.get("run_id"),
            "status": state.get("status") or "idle",
            "message": state.get("message") or "대기중",
            "theme_count": int(state.get("theme_count") or 0),
            "category_count": int(state.get("category_count") or 0),
            "processed_categories": int(state.get("processed_categories") or 0),
            "row_count": int(state.get("row_count") or 0),
            "success_count": int(state.get("success_count") or 0),
            "failure_count": int(state.get("failure_count") or 0),
            "progress_percent": int(state.get("progress_percent") or 0),
            "current_theme_name": state.get("current_theme_name"),
            "current_cid": state.get("current_cid"),
            "current_query": state.get("current_query"),
            "logs": state.get("logs") or [],
            "started_at": state.get("started_at"),
            "finished_at": state.get("finished_at"),
            "r2_json_key": state.get("r2_json_key"),
            "r2_parquet_key": state.get("r2_parquet_key"),
            "top150_count": int(state.get("top150_count") or 0),
            "top100_count": int(state.get("top100_count") or 0),
            "searchad_count": int(state.get("searchad_count") or 0),
            "group_counts": state.get("group_counts") or {},
        }

    @classmethod
    def load_saved_result_for_date(cls, settings, *, target_date: date) -> Dict[str, Any]:
        service = cls(settings)
        key = service.r2_service.find_latest_json_key_for_date(target_date=target_date)
        if not key:
            return {
                "status": "idle",
                "message": "선택한 날짜의 저장된 소싱 결과가 없습니다.",
                "selected_date": target_date.isoformat(),
            }

        payload = service.r2_service.read_json(key=key)
        if not payload:
            return {
                "status": "failed",
                "message": "선택한 날짜의 저장된 결과를 읽지 못했습니다.",
                "selected_date": target_date.isoformat(),
                "r2_json_key": key,
            }

        classified_keywords = payload.get("classified_keywords") or []
        fallback_rows = payload.get("rows") or []
        if not classified_keywords and fallback_rows:
            classified_keywords = cls._build_legacy_history_rows(fallback_rows)

        top_keywords = payload.get("top_keywords") or []
        valid_keywords = payload.get("valid_keywords") or []

        state = {
            "run_id": payload.get("run_id"),
            "status": "completed",
            "message": "저장된 소싱 결과를 불러왔습니다.",
            "theme_count": 0,
            "category_count": 0,
            "processed_categories": 0,
            "row_count": int(payload.get("row_count") or len(payload.get("rows") or [])),
            "success_count": 0,
            "failure_count": 0,
            "progress_percent": 100,
            "current_theme_name": None,
            "current_cid": None,
            "current_query": None,
            "logs": [f"{target_date.isoformat()} 저장 결과를 R2에서 조회했습니다."],
            "started_at": None,
            "finished_at": None,
            "r2_json_key": key,
            "r2_parquet_key": None,
            "dataframe_columns": payload.get("columns") or [],
            "preview_rows": fallback_rows[:20],
            "valid_keywords": valid_keywords,
            "noise_keywords": payload.get("noise_keywords") or [],
            "top_keywords": top_keywords,
            "classified_keywords": classified_keywords,
            "top150_count": len(top_keywords) or len(classified_keywords),
            "top100_count": len(valid_keywords) or len(classified_keywords),
            "searchad_count": len(classified_keywords),
            "group_counts": cls._count_groups(classified_keywords),
            "selected_date": target_date.isoformat(),
        }

        run_id = state.get("run_id") or f"saved-{target_date.strftime('%Y%m%d')}"
        cls._runs[run_id] = state
        cls._latest_run_id = run_id
        return state

    @classmethod
    def start_background_run(
        cls,
        settings,
        *,
        display_per_cid: int = 30,
        theme_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        current = cls.get_status()
        if current.get("status") == "running":
            active_task = cls._active_task
            if active_task is not None and not active_task.done():
                return current
            cls._mark_active_run_stale()

        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        state = {
            "run_id": run_id,
            "status": "running",
            "message": "키워드 소싱을 시작했습니다.",
            "theme_count": 0,
            "category_count": 0,
            "processed_categories": 0,
            "row_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "progress_percent": 0,
            "current_theme_name": None,
            "current_cid": None,
            "current_query": None,
            "logs": ["키워드 소싱을 시작했습니다."],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "r2_json_key": None,
            "r2_parquet_key": None,
            "dataframe_columns": [],
            "preview_rows": [],
            "valid_keywords": [],
            "noise_keywords": [],
            "top_keywords": [],
            "classified_keywords": [],
            "top150_count": 0,
            "top100_count": 0,
            "searchad_count": 0,
            "group_counts": {},
            "selected_theme_id": theme_id,
        }
        cls._runs[run_id] = state
        cls._latest_run_id = run_id
        cls._active_run_id = run_id
        service = cls(settings)
        cls._active_task = asyncio.create_task(
            service._run_collection(
                run_id=run_id,
                display_per_cid=display_per_cid,
                theme_id=theme_id,
            )
        )
        return state

    @classmethod
    def stop_active_run(cls) -> Dict[str, Any]:
        active_task = cls._active_task
        active_run_id = cls._active_run_id or cls._latest_run_id

        if active_task is None or active_task.done() or not active_run_id:
            return cls.get_status()

        active_task.cancel()
        state = cls._runs.get(active_run_id)
        if state is not None:
            state["status"] = "failed"
            state["message"] = "사용자 요청으로 소싱을 중지했습니다."
            state["finished_at"] = datetime.now(timezone.utc).isoformat()
            state["logs"] = (
                (state.get("logs") or []) + ["사용자 요청으로 백그라운드 작업을 취소했습니다."]
            )[-20:]

        cls._active_task = None
        cls._active_run_id = None
        return cls.get_status(run_id=active_run_id)

    async def _run_collection(
        self,
        *,
        run_id: str,
        display_per_cid: int,
        theme_id: Optional[int] = None,
    ) -> None:
        state = self._runs[run_id]
        rows: List[Dict[str, Any]] = []
        keyword_pool: Dict[str, Dict[str, Any]] = {}

        try:
            categories = self._load_theme_categories(theme_id=theme_id)
            state["theme_count"] = len({row["theme_id"] for row in categories})
            state["category_count"] = len(categories)

            if not categories:
                state["status"] = "completed"
                state["message"] = "연결된 CID가 없어 실행을 종료했습니다."
                state["finished_at"] = datetime.now(timezone.utc).isoformat()
                state["logs"].append(state["message"])
                return

            for index, category in enumerate(categories, start=1):
                await asyncio.sleep(0)
                query = category["category_name"].strip()
                state["current_theme_name"] = category["theme_name"]
                state["current_cid"] = category["cid"]
                state["current_query"] = query
                state["message"] = f"{category['theme_name']} / {category['category_name']} 수집 중"
                self._append_log(
                    state,
                    f"[{index}/{len(categories)}] {category['theme_name']} > {category['category_name']} 수집 시작",
                )

                if not query:
                    state["processed_categories"] = index
                    state["failure_count"] += 1
                    state["progress_percent"] = self._progress_percent(index, len(categories))
                    self._append_log(state, f"[{index}/{len(categories)}] 빈 카테고리명으로 건너뜀")
                    continue

                try:
                    top_keyword_result = await self.datalab_service.fetch_category_top_keywords(
                        cid=str(category["cid"]),
                        seed_keywords=[query],
                        limit=150,
                    )
                    top_keywords = top_keyword_result.keywords
                    state["top150_count"] += len(top_keywords)
                    self._append_log(
                        state,
                        f"[{index}/{len(categories)}] 쇼핑인사이트 top150 수집 {len(top_keywords)}건 ({top_keyword_result.source})",
                    )

                    raw_keyword_list = [row["keyword"] for row in top_keywords]
                    valid_keywords, noise_keywords = filter_noise(raw_keyword_list)
                    valid_top100 = valid_keywords[:100]
                    state["top100_count"] += len(valid_top100)

                    for row in top_keywords:
                        keyword = row["keyword"]
                        existing = keyword_pool.get(keyword)
                        row_payload = {
                            "run_id": run_id,
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "keyword": keyword,
                            "rank": row.get("rank"),
                            "ratio": row.get("ratio"),
                            "theme_id": category["theme_id"],
                            "theme_code": category["theme_code"],
                            "theme_name": category["theme_name"],
                            "category_id": category["category_id"],
                            "cid": category["cid"],
                            "category_name": category["category_name"],
                            "full_path": category["full_path"],
                            "is_noise": keyword in noise_keywords,
                            "is_valid": keyword in valid_top100,
                            "source": "naver_shopping_insight",
                        }
                        if not existing or (row_payload["rank"] or 999999) < (existing.get("rank") or 999999):
                            keyword_pool[keyword] = row_payload

                    state["success_count"] += 1
                    self._append_log(
                        state,
                        f"[{index}/{len(categories)}] {category['category_name']} 완료 (top150 {len(top_keywords)}건 / 유효키워드 {len(valid_top100)}건)",
                    )
                except Exception as error:  # noqa: BLE001
                    state["failure_count"] += 1
                    self._append_log(
                        state,
                        f"[{index}/{len(categories)}] {category['category_name']} 실패: {error}",
                    )

                state["processed_categories"] = index
                state["row_count"] = len(keyword_pool)
                state["progress_percent"] = self._progress_percent(index, len(categories))
                if index < len(categories):
                    await asyncio.sleep(self.CATEGORY_DELAY_SECONDS)

            top_keywords = self._build_top_keyword_rows(keyword_pool)
            rows = [dict(row) for row in top_keywords]
            dataframe = pd.DataFrame(rows)
            valid_keywords = [row["keyword"] for row in top_keywords if row.get("is_valid")]
            noise_keywords = [row["keyword"] for row in top_keywords if row.get("is_noise")]
            metrics_map: Dict[str, Dict[str, Any]] = {}
            product_info_map: Dict[str, Dict[str, Any]] = {}
            monthly_trend_map: Dict[str, List[Dict[str, Any]]] = {}

            if valid_keywords:
                try:
                    state["message"] = "광고 API 지표를 수집 중입니다."
                    self._append_log(
                        state,
                        f"SearchAd 지표 수집 시작 ({len(valid_keywords)}개 키워드)",
                    )
                    metrics_map = await self.searchad_service.fetch_keyword_metrics(valid_keywords)
                    self._append_log(
                        state,
                        f"SearchAd 지표 수집 완료 ({len(metrics_map)}개 키워드)",
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as error:  # noqa: BLE001
                    self._append_log(state, f"SearchAd 지표 수집 실패: {error}")

                try:
                    state["message"] = "네이버 쇼핑 상품수를 수집 중입니다."
                    self._append_log(
                        state,
                        f"쇼핑 상품수 수집 시작 ({len(valid_keywords)}개 키워드)",
                    )
                    product_info_map = await self.shopping_service.fetch_product_infos(valid_keywords)
                    self._append_log(
                        state,
                        f"쇼핑 상품수 수집 완료 ({len(product_info_map)}개 키워드)",
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as error:  # noqa: BLE001
                    self._append_log(state, f"쇼핑 상품수 수집 실패: {error}")

                try:
                    state["message"] = "월별 검색 트렌드를 수집 중입니다."
                    self._append_log(
                        state,
                        f"검색 트렌드 수집 시작 ({len(valid_keywords)}개 키워드)",
                    )
                    monthly_trend_map = await self.search_trend_service.fetch_monthly_trends(valid_keywords)
                    self._append_log(
                        state,
                        f"검색 트렌드 수집 완료 ({len(monthly_trend_map)}개 키워드)",
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as error:  # noqa: BLE001
                    self._append_log(state, f"검색 트렌드 수집 실패: {error}")
                    self._append_log(state, "시즌 컬럼은 수집된 트렌드 데이터 범위 내에서만 반영합니다.")

            classified_keywords = self._classify_keywords(
                top_keywords=top_keywords,
                metrics_map=metrics_map,
                product_info_map=product_info_map,
                monthly_trend_map=monthly_trend_map,
            )
            group_counts = self._count_groups(classified_keywords)

            state["searchad_count"] = len(metrics_map)
            state["group_counts"] = group_counts

            r2_json_key, r2_parquet_key = self._save_dataframe_snapshot(
                run_id=run_id,
                dataframe=dataframe,
                valid_keywords=valid_keywords,
                noise_keywords=noise_keywords,
                top_keywords=top_keywords,
                classified_keywords=classified_keywords,
            )

            state["status"] = "completed"
            state["message"] = "키워드 소싱이 완료되었습니다."
            state["finished_at"] = datetime.now(timezone.utc).isoformat()
            state["row_count"] = len(top_keywords)
            state["progress_percent"] = 100
            state["dataframe_columns"] = dataframe.columns.tolist()
            state["preview_rows"] = (
                dataframe.head(20).to_dict(orient="records") if not dataframe.empty else []
            )
            state["r2_json_key"] = r2_json_key
            state["r2_parquet_key"] = r2_parquet_key
            state["valid_keywords"] = valid_keywords[:100]
            state["noise_keywords"] = noise_keywords[:100]
            state["top_keywords"] = top_keywords[:150]
            state["classified_keywords"] = classified_keywords
            self._append_log(state, f"실행 완료: 총 {len(top_keywords)}개 키워드 수집")
        except asyncio.CancelledError:
            state["status"] = "failed"
            state["message"] = "사용자 요청으로 소싱을 중지했습니다."
            state["finished_at"] = datetime.now(timezone.utc).isoformat()
            self._append_log(state, state["message"])
            raise
        except Exception as error:  # noqa: BLE001
            state["status"] = "failed"
            state["message"] = f"키워드 소싱 실패: {error}"
            state["finished_at"] = datetime.now(timezone.utc).isoformat()
            self._append_log(state, state["message"])
        finally:
            if self._active_run_id == run_id:
                self._active_run_id = None
            current_task = asyncio.current_task()
            if current_task is not None and self._active_task is current_task:
                self._active_task = None

    @classmethod
    def _mark_active_run_stale(cls) -> None:
        stale_run_id = cls._active_run_id or cls._latest_run_id
        if stale_run_id and stale_run_id in cls._runs:
            state = cls._runs[stale_run_id]
            state["status"] = "failed"
            state["message"] = "이전 실행이 비정상 종료되어 새 실행으로 교체합니다."
            state["finished_at"] = datetime.now(timezone.utc).isoformat()
            state["logs"] = (
                (state.get("logs") or []) + ["백그라운드 작업이 종료되어 stale run으로 정리했습니다."]
            )[-20:]
        cls._active_run_id = None
        cls._active_task = None

    def collect_all_themes(self, *, display_per_cid: int = 30) -> KeywordSourcingResult:
        raise NotImplementedError("Use start_background_run() for admin-triggered collection.")

    def _load_theme_categories(self, *, theme_id: Optional[int] = None) -> List[Dict[str, Any]]:
        connection = get_mysql_connection()
        try:
            with connection.cursor() as cursor:
                query = """
                    SELECT
                        t.id AS theme_id,
                        t.theme_code,
                        t.theme_name,
                        nc.id AS category_id,
                        nc.cid,
                        nc.category_name,
                        nc.full_path
                    FROM theme_category_maps tcm
                    INNER JOIN themes t
                        ON tcm.theme_id = t.id
                    INNER JOIN naver_categories nc
                        ON tcm.category_id = nc.id
                """
                params: List[Any] = []
                if theme_id is not None:
                    query += " WHERE t.id = %s"
                    params.append(theme_id)
                query += " ORDER BY t.id ASC, nc.id ASC"
                cursor.execute(query, params)
                return cursor.fetchall()
        finally:
            connection.close()

    def _save_dataframe_snapshot(
        self,
        *,
        run_id: str,
        dataframe: pd.DataFrame,
        valid_keywords: List[str],
        noise_keywords: List[str],
        top_keywords: List[Dict[str, Any]],
        classified_keywords: List[Dict[str, Any]],
    ) -> tuple[str | None, str | None]:
        payload = {
            "run_id": run_id,
            "row_count": len(dataframe),
            "columns": dataframe.columns.tolist(),
            "rows": dataframe.to_dict(orient="records"),
            "valid_keywords": valid_keywords,
            "noise_keywords": noise_keywords,
            "top_keywords": top_keywords,
            "classified_keywords": classified_keywords,
        }
        json_key = f"search-results/raw/{run_id}.json"
        parquet_key = f"search-results/dataframe/{run_id}.parquet"

        saved_json_key = self.r2_service.save_json_bytes(key=json_key, payload=payload)
        saved_parquet_key = self.r2_service.save_dataframe_parquet(
            key=parquet_key,
            dataframe=dataframe,
        )
        return saved_json_key, saved_parquet_key

    @staticmethod
    def _build_top_keyword_rows(keyword_pool: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows = list(keyword_pool.values())
        rows.sort(key=lambda item: ((item.get("rank") or 999999), item.get("keyword") or ""))
        return rows

    def _classify_keywords(
        self,
        *,
        top_keywords: List[Dict[str, Any]],
        metrics_map: Dict[str, Dict[str, Any]],
        product_info_map: Dict[str, Dict[str, Any]],
        monthly_trend_map: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        enriched_rows: List[Dict[str, Any]] = []

        for row in top_keywords:
            if not row.get("is_valid"):
                continue

            keyword = row["keyword"]
            metrics = metrics_map.get(keyword, {})
            product_info = product_info_map.get(keyword) or {}
            monthly_mobile_searches = self._parse_int(metrics.get("monthly_mobile_searches"))
            monthly_mobile_ctr = self._parse_ctr(metrics.get("monthly_mobile_ctr"))
            competition_level = metrics.get("competition_level")
            product_count = self._parse_int(product_info.get("product_count")) or 0
            shopping_category_path = str(product_info.get("category_path") or "")
            monthly_trends = monthly_trend_map.get(keyword) or []
            season_months = self._estimate_season_months(monthly_trends)
            group_name = self._classify_group(
                monthly_mobile_searches=monthly_mobile_searches,
                monthly_mobile_ctr=monthly_mobile_ctr,
                competition_level=competition_level,
                product_count=product_count,
            )
            if not group_name:
                continue

            enriched = {
                **row,
                **metrics,
                "total_searches": monthly_mobile_searches,
                "avg_ctr": monthly_mobile_ctr,
                "monthly_mobile_searches": monthly_mobile_searches,
                "monthly_mobile_ctr": monthly_mobile_ctr,
                "product_count": product_count,
                "shopping_category_path": shopping_category_path,
                "season_months": season_months,
                "ad_efficiency": self._to_ad_efficiency_label(metrics.get("pl_avg_depth")),
                "group_name": group_name,
            }
            enriched_rows.append(enriched)

        enriched_rows.sort(
            key=lambda item: (
                {"고효율": 0, "중간성장": 1, "대형": 2}.get(item.get("group_name"), 9),
                -(item.get("monthly_mobile_searches") or 0),
                item.get("rank") or 999999,
            )
        )
        return enriched_rows

    @staticmethod
    def _classify_group(
        *,
        monthly_mobile_searches: Any,
        monthly_mobile_ctr: Any,
        competition_level: Any,
        product_count: Any,
    ) -> Optional[str]:
        searches = KeywordSourcingService._parse_int(monthly_mobile_searches) or 0
        ctr = KeywordSourcingService._parse_ctr(monthly_mobile_ctr) or 0.0
        products = KeywordSourcingService._parse_int(product_count) or 0
        competition = str(competition_level or "").strip()

        if (
            300 <= searches <= 5000
            and ctr >= 3.0
            and competition in {"중간", "낮음"}
            and 0 <= products <= 5000
        ):
            return "고효율"

        if (
            4000 <= searches <= 13000
            and ctr >= 2.0
            and products <= 15000
        ):
            return "중간성장"

        if (
            searches >= 13000
            and ctr >= 1.0
            and products >= 15000
        ):
            return "대형"

        return None

    @staticmethod
    def _estimate_season_months(monthly_trends: List[Dict[str, Any]]) -> str:
        if not monthly_trends:
            return "-"

        parsed = []
        for item in monthly_trends:
            period = str(item.get("period") or "")
            ratio = item.get("ratio")
            try:
                month = int(period[5:7])
                score = float(ratio)
            except (TypeError, ValueError):
                continue
            parsed.append((month, score))

        if not parsed:
            return "-"

        peak_score = max(score for _, score in parsed)
        threshold = peak_score * 0.7
        season_months = [month for month, score in parsed if score >= threshold]
        if not season_months:
            return "-"

        season_months = sorted(set(season_months))
        if len(season_months) == 1:
            return f"{season_months[0]}월"

        extended = season_months + [month + 12 for month in season_months]
        best_run = season_months
        current_run = [extended[0]]

        for value in extended[1:]:
            if value == current_run[-1] + 1:
                current_run.append(value)
            else:
                if len(current_run) > len(best_run):
                    best_run = current_run[:]
                current_run = [value]

        if len(current_run) > len(best_run):
            best_run = current_run[:]

        start_month = ((best_run[0] - 1) % 12) + 1
        end_month = ((best_run[-1] - 1) % 12) + 1
        if start_month == end_month:
            return f"{start_month}월"
        return f"{start_month}월~{end_month}월"

    @staticmethod
    def _to_ad_efficiency_label(value: Any) -> str:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return "-"

        if score >= 10:
            return "낮음"
        if score >= 9:
            return "비교적 낮음"
        if score >= 8:
            return "중간"
        return "좋음"

    @staticmethod
    def _count_groups(rows: List[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {"고효율": 0, "중간성장": 0, "대형": 0}
        for row in rows:
            group_name = str(row.get("group_name") or "")
            if group_name in counts:
                counts[group_name] += 1
        return counts

    @staticmethod
    def _parse_int(value: Any) -> Optional[int]:
        if value in (None, ""):
            return None
        text = str(value).strip().replace(",", "")
        if not text:
            return None
        if text == "< 10":
            return 0
        try:
            return int(float(text))
        except ValueError:
            return None

    @staticmethod
    def _parse_ctr(value: Any) -> Optional[float]:
        if value in (None, ""):
            return None
        text = str(value).strip().replace(",", "").replace("%", "")
        if not text:
            return None
        if text == "< 0.1":
            return 0.0
        try:
            numeric = float(text)
        except ValueError:
            return None
        if 0 < numeric < 1:
            return numeric * 100.0
        return numeric

    @staticmethod
    def _safe_average(values: List[float | None]) -> float | None:
        filtered = [value for value in values if value is not None]
        if not filtered:
            return None
        return sum(filtered) / len(filtered)

    @staticmethod
    def _build_legacy_history_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: Dict[str, Dict[str, Any]] = {}

        for row in rows:
            keyword = str(row.get("query") or row.get("seed_keyword") or "").strip()
            if not keyword:
                continue

            category_name = row.get("category_name")
            full_path = row.get("full_path")
            theme_name = row.get("theme_name")
            dedupe_key = f"{keyword}|{full_path or category_name or ''}|{theme_name or ''}"
            if dedupe_key in deduped:
                continue

            deduped[dedupe_key] = {
                "keyword": keyword,
                "full_path": full_path,
                "category_name": category_name,
                "theme_name": theme_name,
                "group_name": "이전 저장본",
                "competition_level": "-",
                "total_searches": 0,
                "avg_ctr": None,
                "legacy_source": True,
            }

        legacy_rows = list(deduped.values())
        legacy_rows.sort(
            key=lambda item: (
                str(item.get("theme_name") or ""),
                str(item.get("full_path") or item.get("category_name") or ""),
                str(item.get("keyword") or ""),
            )
        )
        return legacy_rows[:100]

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(str(value).replace(",", ""))
        except ValueError:
            return None

    @staticmethod
    def _progress_percent(processed: int, total: int) -> int:
        if total <= 0:
            return 0
        return int((processed / total) * 100)

    @staticmethod
    def _append_log(state: Dict[str, Any], message: str) -> None:
        state["logs"] = (state.get("logs", []) + [message])[-20:]
