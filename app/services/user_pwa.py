from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional

from app.services.db import get_mysql_connection
from app.core.config import get_settings
from app.services.r2_storage import R2StorageService


class UserPwaFeedService:
    THEME_KEYWORD_LIMIT = 5
    LOCAL_UI_RESULTS_PATH = (
        Path(__file__).resolve().parents[2] / "local-crawler" / "output" / "ui_results.json"
    )

    @classmethod
    def build_feed(cls) -> Dict[str, Any]:
        score_map = cls._build_keyword_score_map()
        try:
            crawled_rows = cls._load_latest_crawled_rows()
        except Exception:
            fallback_themes = cls._build_local_only_themes(score_map=score_map)
            return {
                "status": "ok",
                "run_id": None,
                "themes": fallback_themes,
            }

        if not crawled_rows:
            fallback_themes = cls._build_local_only_themes(score_map=score_map)
            return {
                "status": "ok",
                "run_id": None,
                "themes": fallback_themes,
            }

        return {
            "status": "ok",
            "run_id": None,
            "themes": cls._group_crawled_rows_by_theme(crawled_rows, score_map=score_map),
        }

    @classmethod
    def _build_keyword_score_map(cls) -> Dict[str, Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        for row in cls._load_local_keyword_scores():
            keyword = str(row.get("keyword") or "").strip()
            if keyword:
                merged[keyword] = cls._normalize_score_row(row)
        for row in cls._load_r2_keyword_scores():
            keyword = str(row.get("keyword") or "").strip()
            if keyword:
                merged[keyword] = cls._normalize_score_row(row)
        missing = [keyword for keyword, payload in merged.items() if payload.get("naver_score") is None]
        if missing:
            for keyword, naver_score in cls._load_naver_scores_from_db(missing).items():
                if keyword in merged and merged[keyword].get("naver_score") is None:
                    merged[keyword]["naver_score"] = naver_score
        return merged

    @classmethod
    def _load_r2_keyword_scores(cls) -> List[Dict[str, Any]]:
        settings = get_settings()
        service = R2StorageService(settings)
        key = service.find_latest_local_crawler_result_key()
        if not key:
            return []
        payload = service.read_json(key=key) or {}
        scores = payload.get("keyword_scores") or []
        return [row for row in scores if isinstance(row, dict)]

    @classmethod
    def _load_local_keyword_scores(cls) -> List[Dict[str, Any]]:
        path = cls.LOCAL_UI_RESULTS_PATH
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        scores = payload.get("keyword_scores") or []
        return [row for row in scores if isinstance(row, dict)]

    @classmethod
    def _normalize_score_row(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        coupang_score = cls._parse_score(row.get("coupang_score"))
        if coupang_score is None:
            coupang_score = cls._parse_score(row.get("final_score"))
        return {
            "coupang_score": coupang_score,
            "naver_score": cls._parse_score(row.get("naver_score")),
            "ai_score": cls._parse_score(row.get("ai_score")),
            "ai_tier": str(row.get("ai_tier") or "").strip(),
            "ai_scoring_ready": bool(row.get("ai_scoring_ready")),
            "ai_scoring_error": str(row.get("ai_scoring_error") or "").strip(),
        }

    @classmethod
    def _load_naver_scores_from_db(cls, keywords: List[str]) -> Dict[str, Optional[float]]:
        keyword_list = [str(keyword or "").strip() for keyword in keywords if str(keyword or "").strip()]
        if not keyword_list:
            return {}

        placeholders = ", ".join(["%s"] * len(keyword_list))
        connection = get_mysql_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT keyword, source_payload_json
                    FROM keyword_sourcing_final_keywords
                    WHERE keyword IN ({placeholders})
                    """,
                    tuple(keyword_list),
                )
                rows = cursor.fetchall() or []
        finally:
            connection.close()

        scores: Dict[str, Optional[float]] = {}
        for row in rows:
            keyword = str(row.get("keyword") or "").strip()
            if not keyword:
                continue
            payload = cls._json_loads(row.get("source_payload_json"), {})
            if not isinstance(payload, dict):
                continue
            final_score = cls._parse_score(payload.get("final_score"))
            if final_score is not None:
                scores[keyword] = final_score
                continue
            volume_score = cls._parse_score(payload.get("search_volume_score"))
            ctr_score = cls._parse_score(payload.get("ctr_score"))
            if volume_score is not None and ctr_score is not None:
                scores[keyword] = round((volume_score + ctr_score) / 2, 1)
        return scores

    @staticmethod
    def _json_loads(raw: Any, default: Any) -> Any:
        if isinstance(raw, dict):
            return raw
        text = str(raw or "").strip()
        if not text:
            return default
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return default

    @staticmethod
    def _parse_score(value: Any) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            return round(float(str(value).replace(",", "").strip()), 1)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _enrich_score_map_with_db_naver(
        cls,
        score_map: Dict[str, Dict[str, Any]],
        keywords: List[str],
    ) -> None:
        missing = [
            keyword
            for keyword in keywords
            if keyword and (score_map.get(keyword) or {}).get("naver_score") is None
        ]
        if not missing:
            return
        for keyword, naver_score in cls._load_naver_scores_from_db(missing).items():
            entry = score_map.setdefault(keyword, {})
            if entry.get("naver_score") is None:
                entry["naver_score"] = naver_score

    @classmethod
    def _apply_scores_to_card(cls, card: Dict[str, Any], score_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        keyword = str(card.get("keyword") or "").strip()
        scores = score_map.get(keyword) or {}
        card["coupang_score"] = scores.get("coupang_score")
        card["naver_score"] = scores.get("naver_score")
        card["ai_score"] = scores.get("ai_score")
        card["ai_tier"] = scores.get("ai_tier") or ""
        card["ai_scoring_ready"] = scores.get("ai_scoring_ready")
        card["ai_scoring_error"] = scores.get("ai_scoring_error") or ""
        return card

    @classmethod
    def _pick_keyword_preview_rows(cls, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """키워드당 카드 1개 — 로컬 크롤(리뷰 상위)은 rank=1이 없을 수 있음."""
        by_keyword: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in rows:
            if not isinstance(row, dict):
                continue
            keyword = str(row.get("keyword") or "").strip()
            if keyword:
                by_keyword[keyword].append(row)

        previews: List[Dict[str, Any]] = []
        for group in by_keyword.values():
            with_sales = [
                row
                for row in group
                if str(row.get("monthly_sales") or "").strip() not in {"", "0개"}
            ]
            pool = with_sales or group

            rank_one = [row for row in pool if cls._parse_int(row.get("rank")) == 1]
            if rank_one:
                previews.append(rank_one[0])
                continue
            if len(pool) == 1 and cls._parse_int(pool[0].get("rank")) is None:
                previews.append(pool[0])
                continue

            def _preview_sort_key(row: Dict[str, Any]) -> tuple[int, int]:
                rank = cls._parse_int(row.get("rank")) or 999
                reviews = cls._parse_int(row.get("review_count")) or 0
                return (rank, -reviews)

            previews.append(sorted(pool, key=_preview_sort_key)[0])
        return previews

    @classmethod
    def _build_local_only_themes(cls, *, score_map: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        score_map = score_map or cls._build_keyword_score_map()
        preview_items = cls._pick_keyword_preview_rows(cls._load_local_ui_items())
        preview_keywords = [
            str(item.get("keyword") or "").strip()
            for item in preview_items
            if str(item.get("keyword") or "").strip()
        ]
        cls._enrich_score_map_with_db_naver(score_map, preview_keywords)
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        seen_keywords: Dict[str, set[str]] = defaultdict(set)
        for item in preview_items:
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
            cards = [
                cls._apply_scores_to_card(cls._build_local_card(row), score_map)
                for row in rows[: cls.THEME_KEYWORD_LIMIT]
            ]
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
    def _load_latest_crawled_rows(cls) -> List[Dict[str, Any]]:
        r2_rows = cls._load_r2_crawled_rows()
        if r2_rows:
            return r2_rows
        return cls._load_crawled_keywords_from_db()

    @classmethod
    def _load_r2_crawled_rows(cls) -> List[Dict[str, Any]]:
        settings = get_settings()
        service = R2StorageService(settings)
        key = service.find_latest_local_crawler_result_key()
        if not key:
            return []
        payload = service.read_json(key=key) or {}
        items = payload.get("items") or []
        return [item for item in items if isinstance(item, dict)]

    @classmethod
    def _load_crawled_keywords_from_db(cls) -> List[Dict[str, Any]]:
        connection = get_mysql_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        r.keyword_text AS keyword,
                        MAX(r.collected_at) AS latest_collected_at,
                        MAX(CASE WHEN i.rank_no = 1 THEN i.product_title END) AS top_product_title,
                        MAX(CASE WHEN i.rank_no = 1 THEN i.price_text END) AS top_product_price,
                        MAX(CASE WHEN i.rank_no = 1 THEN i.product_url END) AS top_product_url,
                        MAX(meta.theme_name) AS theme_name,
                        MAX(meta.shopping_category_path) AS theme_detail,
                        MAX(meta.group_name) AS group_name
                    FROM coupang_search_runs r
                    INNER JOIN coupang_search_ranked_items i
                        ON i.run_id = r.id
                    LEFT JOIN (
                        SELECT
                            keyword,
                            theme_name,
                            shopping_category_path,
                            group_name
                        FROM keyword_sourcing_final_keywords
                    ) meta
                        ON meta.keyword = r.keyword_text
                    GROUP BY r.keyword_text
                    ORDER BY
                        latest_collected_at DESC
                    """,
                )
                rows = cursor.fetchall() or []
        finally:
            connection.close()
        return list(rows)

    @classmethod
    def _group_crawled_rows_by_theme(
        cls,
        rows: List[Dict[str, Any]],
        *,
        score_map: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        score_map = score_map or cls._build_keyword_score_map()
        preview_rows = cls._pick_keyword_preview_rows(rows)
        preview_keywords = [
            str(row.get("keyword") or "").strip()
            for row in preview_rows
            if str(row.get("keyword") or "").strip()
        ]
        cls._enrich_score_map_with_db_naver(score_map, preview_keywords)
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        seen_keywords: Dict[str, set[str]] = defaultdict(set)
        for row in preview_rows:
            theme_name = str(row.get("theme_name") or "").strip()
            keyword = str(row.get("keyword") or "").strip()
            if not keyword:
                continue
            theme_name = theme_name or "기타"
            if keyword in seen_keywords[theme_name]:
                continue
            if len(grouped[theme_name]) >= cls.THEME_KEYWORD_LIMIT:
                continue
            grouped[theme_name].append(
                cls._apply_scores_to_card(
                    cls._build_local_card(
                        {
                            "keyword": keyword,
                            "theme_name": theme_name,
                            "theme_detail": row.get("theme_detail") or theme_name,
                            "group_name": row.get("group_name") or "-",
                            "title": row.get("title") or row.get("top_product_title") or "",
                            "product_url": row.get("product_url") or row.get("top_product_url") or "",
                            "price": row.get("price") or row.get("top_product_price"),
                            "image_url": row.get("image_url") or "",
                            "review_count": row.get("review_count"),
                            "avg_reviews": row.get("avg_reviews"),
                            "delivery_type": row.get("delivery_type") or "",
                            "shipping_fee": row.get("shipping_fee"),
                        }
                    ),
                    score_map,
                )
            )
            seen_keywords[theme_name].add(keyword)

        themes: List[Dict[str, Any]] = []
        for theme_name, cards in grouped.items():
            themes.append(
                {
                    "theme_name": theme_name,
                    "theme_detail": str(cards[0].get("theme_detail") or theme_name),
                    "cards": cards[: cls.THEME_KEYWORD_LIMIT],
                }
            )
        return themes

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
        image_map: Dict[str, str] = {}
        for item in cls._pick_keyword_preview_rows(cls._load_local_ui_items()):
            keyword = str(item.get("keyword") or "").strip()
            image_url = str(item.get("image_url") or "").strip()
            if keyword and image_url and keyword not in image_map:
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
