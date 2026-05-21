from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional

from app.services.db import get_mysql_connection


class UserPwaFeedService:
    THEME_KEYWORD_LIMIT = 5
    LOCAL_UI_RESULTS_PATH = (
        Path(__file__).resolve().parents[2] / "local-crawler" / "output" / "ui_results.json"
    )

    @classmethod
    def build_feed(cls) -> Dict[str, Any]:
        image_map = cls._load_local_image_map()
        try:
            run_id = cls._latest_run_id()
            if not run_id:
                fallback_themes = cls._build_local_only_themes()
                return {
                    "status": "ok",
                    "run_id": None,
                    "themes": fallback_themes,
                }

            keyword_rows = cls._load_final_keywords(run_id)
            keyword_map = cls._group_keywords_by_theme(keyword_rows)
            snapshot_map = cls._load_latest_coupang_rows_for_keywords(
                [row["keyword"] for rows in keyword_map.values() for row in rows]
            )
        except Exception:
            fallback_themes = cls._build_local_only_themes()
            return {
                "status": "ok",
                "run_id": None,
                "themes": fallback_themes,
            }

        themes: List[Dict[str, Any]] = []
        for theme_name, rows in keyword_map.items():
            cards = []
            for row in rows[: cls.THEME_KEYWORD_LIMIT]:
                cards.append(
                    cls._build_keyword_card(
                        row,
                        snapshot_map.get(row["keyword"], []),
                        image_map.get(row["keyword"], ""),
                    )
                )
            if cards:
                themes.append(
                    {
                        "theme_name": theme_name,
                        "theme_detail": rows[0].get("theme_detail") or theme_name,
                        "cards": cards,
                    }
                )

        return {
            "status": "ok",
            "run_id": run_id,
            "themes": themes,
        }

    @classmethod
    def _build_local_only_themes(cls) -> List[Dict[str, Any]]:
        items = cls._load_local_ui_items()
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        seen_keywords: Dict[str, set[str]] = defaultdict(set)
        for item in items:
            if not isinstance(item, dict):
                continue
            theme_name = str(item.get("theme_name") or "").strip() or "기타"
            keyword = str(item.get("keyword") or "").strip()
            if not keyword or keyword in seen_keywords[theme_name]:
                continue
            if len(grouped[theme_name]) >= cls.THEME_KEYWORD_LIMIT:
                continue
            grouped[theme_name].append(item)
            seen_keywords[theme_name].add(keyword)

        themes = []
        for theme_name, rows in grouped.items():
            cards = [cls._build_local_card(row) for row in rows[: cls.THEME_KEYWORD_LIMIT]]
            themes.append(
                {
                    "theme_name": theme_name,
                    "theme_detail": str(rows[0].get("theme_detail") or theme_name),
                    "cards": cards,
                }
            )
        return themes

    @classmethod
    def _latest_run_id(cls) -> Optional[str]:
        connection = get_mysql_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT run_id
                    FROM keyword_sourcing_runs
                    WHERE status = 'completed'
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """
                )
                row = cursor.fetchone()
        finally:
            connection.close()
        if not row:
            return None
        return str(row.get("run_id") or "").strip() or None

    @classmethod
    def _load_final_keywords(cls, run_id: str) -> List[Dict[str, Any]]:
        connection = get_mysql_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        keyword,
                        theme_name,
                        shopping_category_path,
                        full_path,
                        rank_order,
                        monthly_mobile_searches,
                        group_name
                    FROM keyword_sourcing_final_keywords
                    WHERE run_id = %s
                    ORDER BY
                        theme_name ASC,
                        COALESCE(rank_order, 999999) ASC,
                        COALESCE(monthly_mobile_searches, 0) DESC,
                        keyword ASC
                    """,
                    (run_id,),
                )
                rows = cursor.fetchall() or []
        finally:
            connection.close()
        return list(rows)

    @classmethod
    def _group_keywords_by_theme(cls, rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in rows:
            theme_name = str(row.get("theme_name") or "").strip()
            keyword = str(row.get("keyword") or "").strip()
            if not theme_name or not keyword:
                continue
            if len(grouped[theme_name]) >= cls.THEME_KEYWORD_LIMIT:
                continue
            grouped[theme_name].append(
                {
                    "keyword": keyword,
                    "theme_name": theme_name,
                    "theme_detail": row.get("shopping_category_path")
                    or row.get("full_path")
                    or theme_name,
                    "group_name": row.get("group_name") or "-",
                }
            )
        return dict(grouped)

    @classmethod
    def _load_latest_coupang_rows_for_keywords(cls, keywords: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        keyword_list = [str(keyword or "").strip() for keyword in keywords if str(keyword or "").strip()]
        if not keyword_list:
            return {}

        placeholders = ", ".join(["%s"] * len(keyword_list))
        connection = get_mysql_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT
                        r.keyword_text,
                        i.rank_no,
                        i.product_title,
                        i.price_text,
                        i.shipping_text,
                        i.review_count_text,
                        i.review_score_text,
                        i.product_url
                    FROM coupang_search_runs r
                    INNER JOIN (
                        SELECT keyword_text, MAX(collected_at) AS latest_collected_at
                        FROM coupang_search_runs
                        WHERE keyword_text IN ({placeholders})
                        GROUP BY keyword_text
                    ) latest
                        ON latest.keyword_text = r.keyword_text
                       AND latest.latest_collected_at = r.collected_at
                    INNER JOIN coupang_search_ranked_items i
                        ON i.run_id = r.id
                    WHERE i.rank_no <= 10
                    ORDER BY r.keyword_text ASC, i.rank_no ASC
                    """,
                    tuple(keyword_list),
                )
                rows = cursor.fetchall() or []
        finally:
            connection.close()

        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row.get("keyword_text") or "").strip()].append(dict(row))
        return dict(grouped)

    @classmethod
    def _build_keyword_card(
        cls,
        row: Dict[str, Any],
        ranked_rows: List[Dict[str, Any]],
        fallback_image_url: str,
    ) -> Dict[str, Any]:
        top_row = ranked_rows[0] if ranked_rows else {}
        review_counts = [cls._parse_int(item.get("review_count_text")) for item in ranked_rows]
        review_counts = [value for value in review_counts if value is not None]
        review_average = round(sum(review_counts) / len(review_counts)) if review_counts else None
        review_median = int(median(review_counts)) if review_counts else None
        tier = cls._resolve_tier(review_median)
        delivery_mix = cls._build_delivery_mix(ranked_rows)

        return {
            "keyword": row.get("keyword") or "",
            "theme_name": row.get("theme_name") or "",
            "theme_detail": row.get("theme_detail") or "",
            "group_name": row.get("group_name") or "-",
            "top_product_title": str(top_row.get("product_title") or "").strip(),
            "top_product_url": str(top_row.get("product_url") or "").strip(),
            "top_product_price": cls._parse_int(top_row.get("price_text")),
            "top_product_image_url": fallback_image_url,
            "review_count_average": review_average,
            "review_count_median": review_median,
            "tier_key": tier["tier_key"],
            "tier_label": tier["tier_label"],
            "tier_reason": tier["tier_reason"],
            "delivery_mix": delivery_mix,
        }

    @classmethod
    def _load_local_image_map(cls) -> Dict[str, str]:
        items = cls._load_local_ui_items()
        image_map: Dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            keyword = str(item.get("keyword") or "").strip()
            image_url = str(item.get("image_url") or "").strip()
            rank = cls._parse_int(item.get("rank"))
            if not keyword or not image_url:
                continue
            if rank == 1 and keyword not in image_map:
                image_map[keyword] = image_url
        return image_map

    @classmethod
    def _load_local_ui_items(cls) -> List[Dict[str, Any]]:
        path = cls.LOCAL_UI_RESULTS_PATH
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        items = payload.get("items") or []
        return [item for item in items if isinstance(item, dict)]

    @classmethod
    def _build_local_card(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        review_average = cls._parse_int(row.get("avg_reviews")) or cls._parse_int(row.get("review_count"))
        review_median = cls._parse_int(row.get("review_count"))
        tier = cls._resolve_tier(review_median)
        delivery_label = cls._normalize_delivery_label(row.get("delivery_type") or row.get("shipping_fee"))
        delivery_mix = (
            [{"label": delivery_label, "count": 1, "ratio": 100}]
            if delivery_label
            else []
        )
        return {
            "keyword": str(row.get("keyword") or ""),
            "theme_name": str(row.get("theme_name") or ""),
            "theme_detail": str(row.get("theme_detail") or ""),
            "group_name": str(row.get("group_name") or "-"),
            "top_product_title": str(row.get("title") or "").strip(),
            "top_product_url": str(row.get("product_url") or "").strip(),
            "top_product_price": cls._parse_int(row.get("price")),
            "top_product_image_url": str(row.get("image_url") or "").strip(),
            "review_count_average": review_average,
            "review_count_median": review_median,
            "tier_key": tier["tier_key"],
            "tier_label": tier["tier_label"],
            "tier_reason": tier["tier_reason"],
            "delivery_mix": delivery_mix,
        }

    @classmethod
    def _build_delivery_mix(cls, ranked_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        counts: Dict[str, int] = defaultdict(int)
        total = 0
        for row in ranked_rows:
            label = cls._normalize_delivery_label(row.get("shipping_text"))
            if not label:
                continue
            counts[label] += 1
            total += 1
        if total <= 0:
            return []
        items = []
        for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
            items.append(
                {
                    "label": label,
                    "count": count,
                    "ratio": round((count / total) * 100),
                }
            )
        return items

    @staticmethod
    def _normalize_delivery_label(raw: Any) -> str:
        text = str(raw or "").strip()
        if not text:
            return ""
        if "판매자로켓" in text:
            return "판매자로켓"
        if "로켓그로스" in text:
            return "로켓그로스"
        if "로켓프레시" in text or "로켓프래시" in text:
            return "로켓프레시"
        if "로켓배송" in text:
            return "로켓배송"
        if "판매자배송" in text or "판매자 배송" in text or "일반배송" in text:
            return "일반배송"
        return ""

    @staticmethod
    def _parse_int(value: Any) -> Optional[int]:
        text = str(value or "").strip()
        if not text:
            return None
        normalized = (
            text.replace(",", "")
            .replace("원", "")
            .replace("(", "")
            .replace(")", "")
            .strip()
        )
        try:
            return int(float(normalized))
        except ValueError:
            pass
        digits = "".join(ch for ch in normalized if ch.isdigit())
        if not digits:
            return None
        try:
            return int(digits)
        except ValueError:
            return None

    @staticmethod
    def _resolve_tier(review_median: Optional[int]) -> Dict[str, str]:
        if review_median is None:
            return {
                "tier_key": "unknown",
                "tier_label": "⚪ 미검증",
                "tier_reason": "데이터 없음",
            }
        if review_median >= 1000:
            return {
                "tier_key": "premium",
                "tier_label": "👑 프리미엄",
                "tier_reason": "1,000 이상 구간 진입",
            }
        if review_median >= 700:
            return {
                "tier_key": "diamond",
                "tier_label": "💎 다이아",
                "tier_reason": "700 이상 ~ 1,000 미만",
            }
        if review_median >= 400:
            return {
                "tier_key": "gold",
                "tier_label": "🥇 골드",
                "tier_reason": "400 이상 ~ 700 미만",
            }
        return {
            "tier_key": "raw_gem",
            "tier_label": "🌱 원석",
            "tier_reason": "400 미만 구간 충족",
        }
