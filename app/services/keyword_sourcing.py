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
from app.services.naver_searchad import NaverSearchAdService
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

    def __init__(self, settings) -> None:
        self.settings = settings
        self.datalab_service = NaverShoppingInsightService(settings)
        self.searchad_service = NaverSearchAdService(settings)
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
            "preview_rows": (payload.get("rows") or [])[:20],
            "valid_keywords": payload.get("valid_keywords") or [],
            "noise_keywords": payload.get("noise_keywords") or [],
            "top_keywords": payload.get("top_keywords") or [],
            "classified_keywords": payload.get("classified_keywords") or [],
            "top150_count": len(payload.get("top_keywords") or []),
            "top100_count": len(payload.get("valid_keywords") or []),
            "searchad_count": len(payload.get("classified_keywords") or []),
            "group_counts": cls._count_groups(payload.get("classified_keywords") or []),
            "selected_date": target_date.isoformat(),
        }

        run_id = state.get("run_id") or f"saved-{target_date.strftime('%Y%m%d')}"
        cls._runs[run_id] = state
        cls._latest_run_id = run_id
        return state

    @classmethod
    def start_background_run(cls, settings, *, display_per_cid: int = 30) -> Dict[str, Any]:
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
        }
        cls._runs[run_id] = state
        cls._latest_run_id = run_id
        cls._active_run_id = run_id
        service = cls(settings)
        cls._active_task = asyncio.create_task(
            service._run_collection(run_id=run_id, display_per_cid=display_per_cid)
        )
        return state

    async def _run_collection(self, *, run_id: str, display_per_cid: int) -> None:
        state = self._runs[run_id]
        rows: List[Dict[str, Any]] = []
        keyword_pool: Dict[str, Dict[str, Any]] = {}

        try:
            categories = self._load_theme_categories()
            state["theme_count"] = len({row["theme_id"] for row in categories})
            state["category_count"] = len(categories)

            if not categories:
                state["status"] = "completed"
                state["message"] = "연결된 CID가 없어 실행을 종료했습니다."
                state["finished_at"] = datetime.now(timezone.utc).isoformat()
                state["logs"].append(state["message"])
                return

            for index, category in enumerate(categories, start=1):
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
                        seed_keywords=[],
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

            top_keywords = self._build_top_keyword_rows(keyword_pool)
            rows = [dict(row) for row in top_keywords]
            dataframe = pd.DataFrame(rows)
            valid_keywords = [row["keyword"] for row in top_keywords if row.get("is_valid")]
            noise_keywords = [row["keyword"] for row in top_keywords if row.get("is_noise")]
            metrics_map = await self.searchad_service.fetch_keyword_metrics(valid_keywords[:100])
            classified_keywords = self._classify_keywords(top_keywords=top_keywords, metrics_map=metrics_map)
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
            state["classified_keywords"] = classified_keywords[:100]
            self._append_log(state, f"실행 완료: 총 {len(top_keywords)}개 키워드 수집")
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

    def _load_theme_categories(self) -> List[Dict[str, Any]]:
        connection = get_mysql_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
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
                    ORDER BY t.id ASC, nc.id ASC
                    """
                )
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
    ) -> List[Dict[str, Any]]:
        enriched_rows: List[Dict[str, Any]] = []
        volumes = []

        for row in top_keywords:
            if not row.get("is_valid"):
                continue

            keyword = row["keyword"]
            metrics = metrics_map.get(keyword, {})
            total_searches = (metrics.get("monthly_pc_searches") or 0) + (
                metrics.get("monthly_mobile_searches") or 0
            )
            total_clicks = (metrics.get("monthly_pc_clicks") or 0.0) + (
                metrics.get("monthly_mobile_clicks") or 0.0
            )
            avg_ctr = self._safe_average(
                [metrics.get("monthly_pc_ctr"), metrics.get("monthly_mobile_ctr")]
            )
            competition = metrics.get("competition_index")

            enriched = {
                **row,
                **metrics,
                "total_searches": total_searches,
                "total_clicks": total_clicks,
                "avg_ctr": avg_ctr,
                "group_name": "미분류",
            }
            enriched_rows.append(enriched)
            if total_searches:
                volumes.append(total_searches)

        volume_median = median(volumes) if volumes else 0
        volume_high = max(volumes) * 0.7 if volumes else 0

        for row in enriched_rows:
            volume = row.get("total_searches") or 0
            ctr = row.get("avg_ctr") or 0.0
            competition = row.get("competition_index")
            rank = row.get("rank") or 999999

            if volume >= volume_high:
                group_name = "대형"
            elif volume >= volume_median and ctr >= 0.03:
                group_name = "중간성장"
            elif rank <= 50 and ctr >= 0.02 and (competition is None or competition <= 1.0):
                group_name = "고효율"
            elif volume >= volume_median:
                group_name = "중간성장"
            else:
                group_name = "고효율"

            row["group_name"] = group_name

        enriched_rows.sort(
            key=lambda item: (
                {"고효율": 0, "중간성장": 1, "대형": 2, "미분류": 3}.get(item["group_name"], 9),
                -(item.get("total_searches") or 0),
                item.get("rank") or 999999,
            )
        )
        return enriched_rows

    @staticmethod
    def _count_groups(rows: List[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {"고효율": 0, "중간성장": 0, "대형": 0}
        for row in rows:
            group_name = str(row.get("group_name") or "")
            if group_name in counts:
                counts[group_name] += 1
        return counts

    @staticmethod
    def _safe_average(values: List[float | None]) -> float | None:
        filtered = [value for value in values if value is not None]
        if not filtered:
            return None
        return sum(filtered) / len(filtered)

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
