from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from app.services.db import get_mysql_connection
from app.services.naver_api import NaverShoppingService
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

    def __init__(self, settings) -> None:
        self.settings = settings
        self.naver_service = NaverShoppingService(settings)
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
            }
        return cls._runs[target_run_id]

    @classmethod
    def start_background_run(cls, settings, *, display_per_cid: int = 30) -> Dict[str, Any]:
        current = cls.get_status()
        if current.get("status") == "running":
            return current

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
        }
        cls._runs[run_id] = state
        cls._latest_run_id = run_id
        cls._active_run_id = run_id
        asyncio.create_task(cls(settings)._run_collection(run_id=run_id, display_per_cid=display_per_cid))
        return state

    async def _run_collection(self, *, run_id: str, display_per_cid: int) -> None:
        state = self._runs[run_id]
        rows: List[Dict[str, Any]] = []

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
                    result = await self.naver_service.search_products(
                        query=query,
                        display=display_per_cid,
                        start=1,
                        sort="sim",
                    )
                    items = result.get("items", [])
                    collected_at = datetime.now(timezone.utc).isoformat()

                    for item in items:
                        rows.append(
                            {
                                "run_id": run_id,
                                "collected_at": collected_at,
                                "theme_id": category["theme_id"],
                                "theme_code": category["theme_code"],
                                "theme_name": category["theme_name"],
                                "category_id": category["category_id"],
                                "cid": category["cid"],
                                "category_name": category["category_name"],
                                "full_path": category["full_path"],
                                "seed_keyword": query,
                                "query": query,
                                "source": "naver_shop_api",
                                "product_id": item.get("product_id"),
                                "product_name": item.get("title"),
                                "mall_name": item.get("mall_name"),
                                "price": self._to_int(item.get("lprice")),
                                "product_type": item.get("product_type"),
                                "brand": item.get("brand"),
                                "maker": item.get("maker"),
                                "link": item.get("link"),
                            }
                        )

                    state["success_count"] += 1
                    self._append_log(
                        state,
                        f"[{index}/{len(categories)}] {category['category_name']} 완료 ({len(items)}건)",
                    )
                except Exception as error:  # noqa: BLE001
                    state["failure_count"] += 1
                    self._append_log(
                        state,
                        f"[{index}/{len(categories)}] {category['category_name']} 실패: {error}",
                    )

                state["processed_categories"] = index
                state["row_count"] = len(rows)
                state["progress_percent"] = self._progress_percent(index, len(categories))

            dataframe = pd.DataFrame(rows)
            r2_json_key, r2_parquet_key = self._save_dataframe_snapshot(
                run_id=run_id,
                dataframe=dataframe,
            )

            state["status"] = "completed"
            state["message"] = "키워드 소싱이 완료되었습니다."
            state["finished_at"] = datetime.now(timezone.utc).isoformat()
            state["row_count"] = len(rows)
            state["progress_percent"] = 100
            state["dataframe_columns"] = dataframe.columns.tolist()
            state["preview_rows"] = (
                dataframe.head(20).to_dict(orient="records") if not dataframe.empty else []
            )
            state["r2_json_key"] = r2_json_key
            state["r2_parquet_key"] = r2_parquet_key
            self._append_log(state, f"실행 완료: 총 {len(rows)}행 수집")
        except Exception as error:  # noqa: BLE001
            state["status"] = "failed"
            state["message"] = f"키워드 소싱 실패: {error}"
            state["finished_at"] = datetime.now(timezone.utc).isoformat()
            self._append_log(state, state["message"])
        finally:
            if self._active_run_id == run_id:
                self._active_run_id = None

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
    ) -> tuple[str | None, str | None]:
        payload = {
            "run_id": run_id,
            "row_count": len(dataframe),
            "columns": dataframe.columns.tolist(),
            "rows": dataframe.to_dict(orient="records"),
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
