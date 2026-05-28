from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup


LOCAL_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = LOCAL_ROOT.parent
PORTING_ROOT = WORKSPACE_ROOT / "porting" / "coupang_crawl_core"
ENV_PATH = LOCAL_ROOT / ".env"
OUTPUT_DIR = LOCAL_ROOT / "output"
SMOKE_DIR = PORTING_ROOT / ".smoke"
SMOKE_JSON_PATH = SMOKE_DIR / "last_smoke_extract.json"
SMOKE_HTML_PATH = SMOKE_DIR / "last_smoke_search.html"


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _prepare_environment() -> None:
    _load_env_file(ENV_PATH)
    os.environ.setdefault("COUPANG_SMOKE_EXTRACT_DB", "false")
    os.environ.setdefault("COUPANG_FORCE_GOOGLE_ENTRY", "1")
    os.environ.setdefault("COUPANG_BRIGHT_REQUEST", "off")
    if str(PORTING_ROOT) not in sys.path:
        sys.path.insert(0, str(PORTING_ROOT))


def _dump_result(payload: Dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / "ported_last_result.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _smoke_detail_limit_from_env() -> int:
    raw = str(os.environ.get("COUPANG_SMOKE_DETAIL_LIMIT", "5") or "5").strip()
    try:
        return max(1, min(10, int(raw)))
    except ValueError:
        return 5


def _review_count_value(item: Dict[str, Any]) -> int:
    raw = item.get("review_count")
    if raw in (None, ""):
        return -1
    try:
        return int(float(str(raw).replace(",", "").strip()))
    except (TypeError, ValueError):
        return -1


def _extract_product_id_from_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    for pattern in (
        r"/vp/products/(\d+)",
        r"/products/(\d+)",
        r"[?&]productId=(\d+)",
    ):
        match = re.search(pattern, raw, flags=re.I)
        if match:
            return match.group(1)
    return ""


def _coupang_item_merge_key(row: Dict[str, Any]) -> str:
    """SERP 순위가 바뀌어도 동일 SKU에 판매량을 붙이기 위한 키 (product_id + itemId + vendorItemId)."""
    url = str(row.get("url") or row.get("product_url") or "").strip()
    product_id = str(row.get("product_id") or "").strip() or _extract_product_id_from_url(url)
    if not url and not product_id:
        return ""

    parsed = urlparse(url) if url else None
    query = parse_qs(parsed.query) if parsed else {}

    def _first_param(name: str) -> str:
        values = query.get(name) or query.get(name.lower()) or []
        return str(values[0]).strip() if values else ""

    item_id = _first_param("itemId")
    vendor_item_id = _first_param("vendorItemId")
    if product_id and item_id:
        return f"{product_id}:{item_id}:{vendor_item_id}"
    if product_id:
        return f"pid:{product_id}"
    path = (parsed.path or "").strip().lower() if parsed else ""
    return f"url:{path}" if path else ""


def _apply_detail_sales_to_row(row: Dict[str, Any], detail: Dict[str, Any]) -> Dict[str, Any]:
    raw_sales = str(detail.get("monthly_sales") or row.get("monthly_sales") or "").strip()
    if raw_sales.endswith("개") and raw_sales != "0개":
        row["monthly_sales"] = raw_sales
    else:
        try:
            from coupang_crawler import normalize_monthly_sales_display

            row["monthly_sales"] = normalize_monthly_sales_display(
                raw_sales, default_zero=False
            )
        except Exception:
            row["monthly_sales"] = raw_sales
    if not row.get("monthly_sales") or row.get("monthly_sales") == "0개":
        row["monthly_sales"] = ""
    if row.get("monthly_sales"):
        row["detail_fetch_ok"] = True
    else:
        row.pop("detail_fetch_ok", None)
    return row


def _pick_top_items_by_reviews(
    items: List[Dict[str, Any]], *, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """키워드 내 1~10위 중 리뷰수 상위 N개만 남긴다."""
    cap = int(limit if limit is not None else _smoke_detail_limit_from_env())
    ordered = sorted(
        [dict(x) for x in items if isinstance(x, dict)],
        key=lambda row: (-_review_count_value(row), int(row.get("rank") or 999)),
    )
    picked = ordered[:cap]
    for idx, row in enumerate(picked, start=1):
        row["review_rank_in_keyword"] = idx
    return picked


def _detail_row_has_sales(row: Dict[str, Any]) -> bool:
    sales = str(row.get("monthly_sales") or "").strip()
    return bool(sales) and sales != "0개"


def _index_detail_rows(
    detail_rows: List[Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[int, Dict[str, Any]]]:
    by_key: Dict[str, Dict[str, Any]] = {}
    by_rank: Dict[int, Dict[str, Any]] = {}
    for row in detail_rows:
        if not isinstance(row, dict):
            continue
        merge_key = _coupang_item_merge_key(row)
        if merge_key:
            prev = by_key.get(merge_key)
            if not prev or (_detail_row_has_sales(row) and not _detail_row_has_sales(prev)):
                by_key[merge_key] = row
        try:
            rank = int(row.get("rank") or 0)
        except Exception:
            rank = 0
        if rank > 0:
            prev = by_rank.get(rank)
            if not prev or (_detail_row_has_sales(row) and not _detail_row_has_sales(prev)):
                by_rank[rank] = row
    return by_key, by_rank


def _lookup_detail_for_item(
    item: Dict[str, Any],
    *,
    by_key: Dict[str, Dict[str, Any]],
    by_rank: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    merge_key = _coupang_item_merge_key(item)
    if merge_key and merge_key in by_key:
        return by_key[merge_key]
    try:
        rank = int(item.get("rank") or 0)
    except Exception:
        rank = 0
    if rank > 0 and rank in by_rank:
        return by_rank[rank]
    product_id = str(item.get("product_id") or "").strip() or _extract_product_id_from_url(
        str(item.get("url") or item.get("product_url") or "")
    )
    if product_id:
        pid_key = f"pid:{product_id}"
        if pid_key in by_key:
            return by_key[pid_key]
    return {}


def _merge_detail_results_into_top10(
    top10_items: List[Dict[str, Any]],
    detail_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    by_key, by_rank = _index_detail_rows(detail_rows)
    merged: List[Dict[str, Any]] = []
    for item in top10_items:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        detail = _lookup_detail_for_item(row, by_key=by_key, by_rank=by_rank)
        if detail:
            _apply_detail_sales_to_row(row, detail)
        merged.append(row)
    return merged


def _apply_smoke_payload_to_result(
    result_data: Dict[str, Any], crawler: Any, smoke_payload: Dict[str, Any]
) -> Dict[str, Any]:
    smoke_result = crawler.build_result_from_smoke_payload(smoke_payload)
    if not smoke_result or not smoke_result.get("top10_items"):
        return result_data

    items = list(smoke_result.get("top10_items") or [])
    detail_rows = list(smoke_payload.get("detail_results") or [])
    if detail_rows:
        items = _merge_detail_results_into_top10(items, detail_rows)

    serp_by_rank: Dict[int, Dict[str, Any]] = {}
    for serp in list(result_data.get("top10_items") or []):
        if not isinstance(serp, dict):
            continue
        try:
            rank = int(serp.get("rank") or 0)
        except Exception:
            continue
        if rank > 0:
            serp_by_rank[rank] = serp

    enriched: List[Dict[str, Any]] = []
    for item in items:
        row = dict(item)
        serp = serp_by_rank.get(int(row.get("rank") or 0)) or {}
        for key in ("image_url", "delivery_type", "shipping_fee", "product_url"):
            if serp.get(key) and not row.get(key):
                row[key] = serp.get(key)
        if serp.get("url") and not row.get("url"):
            row["url"] = serp["url"]
        enriched.append(row)

    out = dict(result_data)
    out.update(smoke_result)
    out["top10_items"] = _pick_top_items_by_reviews(enriched)
    out["detail_pick_mode"] = smoke_payload.get("detail_pick_mode") or "top_reviews"
    out["detail_target_ranks"] = list(smoke_payload.get("detail_target_ranks") or [])
    if detail_rows:
        out["detail_debug"] = detail_rows
    return out


def _smoke_json_path_for_keyword(keyword: str) -> Path:
    slug = re.sub(r"[^\w가-힣]+", "_", str(keyword or "").strip()).strip("_")[:80]
    if slug:
        per_kw = SMOKE_DIR / f"last_smoke_extract_{slug}.json"
        if per_kw.is_file():
            return per_kw
    return SMOKE_JSON_PATH


def _wait_smoke_payload_ready(
    keyword: str, *, timeout_seconds: float = 180.0, not_before: float = 0.0
) -> Dict[str, Any]:
    """상세(detail_pick_mode)까지 끝난 JSON만 읽는다 — 이전 키워드/배치 잔여 파일은 무시."""
    deadline = time.monotonic() + max(30.0, float(timeout_seconds))
    last: Dict[str, Any] = {}
    paths = [SMOKE_JSON_PATH, _smoke_json_path_for_keyword(keyword)]
    while time.monotonic() < deadline:
        for path in paths:
            if not path.is_file():
                continue
            try:
                if not_before > 0 and path.stat().st_mtime < not_before:
                    continue
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            last = payload
            saved_kw = str(payload.get("keyword") or "").strip()
            if keyword and saved_kw and saved_kw != keyword:
                continue
            if payload.get("detail_pick_mode") and isinstance(
                payload.get("detail_results"), list
            ):
                return payload
        time.sleep(0.35)
    return last


def _clear_smoke_artifacts() -> None:
    for path in (SMOKE_JSON_PATH, SMOKE_HTML_PATH):
        try:
            path.unlink(missing_ok=True)
        except Exception:
            continue
    try:
        if SMOKE_DIR.is_dir():
            for path in SMOKE_DIR.glob("last_smoke_extract_*.json"):
                path.unlink(missing_ok=True)
    except Exception:
        pass


def _normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _first_text(soup: BeautifulSoup, selectors: Iterable[str]) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            text = _normalize_space(node.get_text(" ", strip=True))
            if text:
                return text
    return ""


def _first_attr(soup: BeautifulSoup, selectors: Iterable[str], attr: str) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            value = _normalize_space(node.get(attr, ""))
            if value:
                return value
    return ""


def _parse_json_ld_blocks(soup: BeautifulSoup) -> List[Any]:
    blocks: List[Any] = []
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text(strip=True) or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            blocks.append(json.loads(raw))
        except Exception:
            continue
    return blocks


def _walk_json_nodes(node: Any) -> Iterable[Any]:
    yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from _walk_json_nodes(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_json_nodes(value)


def _extract_json_ld_product(blocks: List[Any]) -> Dict[str, Any]:
    for block in blocks:
        for node in _walk_json_nodes(block):
            if isinstance(node, dict) and str(node.get("@type") or "").lower() == "product":
                return node
    return {}


def _extract_json_ld_breadcrumb(blocks: List[Any]) -> List[str]:
    for block in blocks:
        for node in _walk_json_nodes(block):
            if isinstance(node, dict) and str(node.get("@type") or "").lower() == "breadcrumblist":
                items = []
                for item in node.get("itemListElement") or []:
                    if not isinstance(item, dict):
                        continue
                    name = _normalize_space(item.get("name"))
                    if name:
                        items.append(name)
                if items:
                    return items
    return []


def _extract_product_id_from_url(url: Any) -> str:
    raw = _normalize_space(url)
    if not raw:
        return ""
    patterns = (
        r"/vp/products/(\d+)",
        r"/products/(\d+)",
        r"[?&]productId=(\d+)",
        r"[?&]itemId=(\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, raw)
        if match:
            return match.group(1)
    return ""


def _parse_optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    text = _normalize_space(value)
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _extract_json_ld_offer(product_json: Dict[str, Any]) -> Dict[str, Any]:
    offers = product_json.get("offers")
    if isinstance(offers, dict):
        return offers
    if isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, dict):
                return offer
    return {}


def _extract_labeled_value(soup: BeautifulSoup, labels: Iterable[str]) -> str:
    label_list = [_normalize_space(label) for label in labels if _normalize_space(label)]
    if not label_list:
        return ""

    row_selectors = (
        "table tr",
        "tbody tr",
        "dl",
        "ul li",
        "ol li",
        "[class*='spec'] li",
        "[class*='spec'] tr",
        "[class*='item'] li",
    )
    for selector in row_selectors:
        for row in soup.select(selector):
            row_text = _normalize_space(row.get_text(" ", strip=True))
            if not row_text or len(row_text) > 250:
                continue

            header_nodes = row.select("th, dt, strong, b, em, span")
            header_text = _normalize_space(" ".join(node.get_text(" ", strip=True) for node in header_nodes))
            value_nodes = row.select("td, dd")
            value_text = _normalize_space(" ".join(node.get_text(" ", strip=True) for node in value_nodes))

            for label in label_list:
                if label in header_text and value_text:
                    return value_text
                if row_text.startswith(label):
                    stripped = _normalize_space(re.sub(rf"^{re.escape(label)}\s*[:：]?\s*", "", row_text, count=1))
                    if stripped and stripped != row_text:
                        return stripped

    full_text = _normalize_space(soup.get_text("\n", strip=True))
    for label in label_list:
        match = re.search(rf"{re.escape(label)}\s*[:：]?\s*([^\n\r]+)", full_text)
        if match:
            value = _normalize_space(match.group(1))
            if value and value != label:
                return value
    return ""


def _extract_option_count(soup: BeautifulSoup, full_text: str) -> Optional[int]:
    match = re.search(r"옵션\s*(?:총)?\s*(\d+)\s*개", full_text)
    if match:
        return _parse_optional_int(match.group(1))

    select_counts: List[int] = []
    for select in soup.select("select"):
        texts = []
        for option in select.select("option"):
            text = _normalize_space(option.get_text(" ", strip=True))
            if not text:
                continue
            if any(token in text for token in ("선택", "품절", "옵션")):
                continue
            texts.append(text)
        if texts:
            select_counts.append(len(texts))

    button_like = soup.select(
        "[class*='option'] button, [class*='option'] li, [class*='Option'] button, [class*='Option'] li"
    )
    visible_option_texts = {
        _normalize_space(node.get_text(" ", strip=True))
        for node in button_like
        if _normalize_space(node.get_text(" ", strip=True))
    }
    if visible_option_texts:
        select_counts.append(len(visible_option_texts))

    return max(select_counts) if select_counts else None


def _detect_coupon_applied(text: str) -> bool:
    normalized = _normalize_space(text)
    coupon_keywords = (
        "쿠폰할인가",
        "쿠폰 적용가",
        "쿠폰적용가",
        "쿠폰가",
        "할인쿠폰",
        "즉시할인",
        "와우할인가",
    )
    return any(keyword in normalized for keyword in coupon_keywords)


def _detect_delivery_type(text: str) -> str:
    normalized = _normalize_space(text)
    delivery_map = [
        ("판매자로켓", "판매자로켓"),
        ("로켓그로스", "로켓그로스"),
        ("로켓프레시", "로켓프레시"),
        ("로켓프래쉬", "로켓프레시"),
        ("로켓배송", "로켓배송"),
        ("일반배송", "일반배송"),
        ("판매자배송", "일반배송"),
        ("판매자 배송", "일반배송"),
    ]
    for keyword, label in delivery_map:
        if keyword in normalized:
            return label
    return ""


def _detect_delivery_type_from_dom(soup: BeautifulSoup, text: str) -> str:
    badge_ids = {
        _normalize_space(node.get("data-badge-id", "")).upper()
        for node in soup.select("[data-badge-id]")
        if _normalize_space(node.get("data-badge-id", ""))
    }
    if "ROCKET_MERCHANT" in badge_ids:
        return "판매자로켓"
    if "ROCKET" in badge_ids:
        return "로켓배송"
    if "ROCKET_GROWTH" in badge_ids:
        return "로켓그로스"
    if "FRESH" in badge_ids or "ROCKET_FRESH" in badge_ids:
        return "로켓프레시"
    return _detect_delivery_type(text)


def _detect_shipping_fee(text: str) -> tuple[Optional[bool], str]:
    normalized = _normalize_space(text)
    if not normalized:
        return None, ""
    if "무료배송" in normalized:
        return False, "무료배송"

    match = re.search(r"배송비\s*([\d,]+원)", normalized)
    if match:
        return True, f"배송비 {match.group(1)}"
    if "배송비" in normalized:
        return True, "배송비 있음"
    return None, ""


def _detect_shipping_fee_from_dom(soup: BeautifulSoup, text: str) -> tuple[Optional[bool], str]:
    fee_badge_text = _first_text(
        soup,
        [
            '[data-badge-type="feePrice"]',
            '.TextBadge_feePrice__n_gta',
        ],
    )
    if fee_badge_text:
        return _detect_shipping_fee(fee_badge_text)
    return _detect_shipping_fee(text)


def _extract_category_text(soup: BeautifulSoup, blocks: List[Any]) -> str:
    breadcrumb = _extract_json_ld_breadcrumb(blocks)
    if breadcrumb:
        return " > ".join(breadcrumb)

    breadcrumb_nodes = [
        _normalize_space(node.get_text(" ", strip=True))
        for node in soup.select(
            "nav a, .breadcrumb a, [class*='breadcrumb'] a, [class*='Breadcrumb'] a"
        )
    ]
    breadcrumb_nodes = [node for node in breadcrumb_nodes if node]
    if breadcrumb_nodes:
        return " > ".join(breadcrumb_nodes)

    return ""


def _extract_detail_fields(html: str, item: Dict[str, Any]) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    blocks = _parse_json_ld_blocks(soup)
    product_json = _extract_json_ld_product(blocks)
    offer_json = _extract_json_ld_offer(product_json)
    full_text = _normalize_space(soup.get_text(" ", strip=True))

    image_url = (
        _normalize_space(product_json.get("image"))
        if isinstance(product_json.get("image"), str)
        else ""
    )
    if not image_url and isinstance(product_json.get("image"), list):
        first_image = product_json.get("image")[0] if product_json.get("image") else ""
        image_url = _normalize_space(first_image)
    if not image_url:
        image_url = _first_attr(
            soup,
            [
                'meta[property="og:image"]',
                'meta[name="og:image"]',
                'img.fw-aspect-square.fw-object-contain',
                'img[decoding="async"][data-nimg="1"]',
                "img.prod-image__detail",
                "img[src]",
            ],
            "content",
        ) or _first_attr(
            soup,
            [
                'img.fw-aspect-square.fw-object-contain',
                'img[decoding="async"][data-nimg="1"]',
                "img.prod-image__detail",
                "img[src]",
            ],
            "src",
        )

    category = _extract_category_text(soup, blocks)
    coupon_applied = _detect_coupon_applied(full_text)
    product_url = item.get("url") or item.get("product_url") or ""
    product_id = (
        _extract_product_id_from_url(product_url)
        or _normalize_space(product_json.get("productID"))
        or _normalize_space(product_json.get("sku"))
        or _extract_labeled_value(soup, ["쿠팡상품번호", "상품번호", "상품코드"])
    )

    title = (
        item.get("title")
        or _normalize_space(product_json.get("name"))
        or _first_text(soup, ["h1", ".prod-buy-header__title", "[class*='title']"])
    )

    offer_price = _normalize_space(offer_json.get("price"))
    price = item.get("price")
    if price in (None, "") and offer_price:
        price = _parse_optional_int(offer_price)

    aggregate_rating = product_json.get("aggregateRating") if isinstance(product_json.get("aggregateRating"), dict) else {}
    review_count = item.get("review_count")
    if review_count in (None, ""):
        review_count = _parse_optional_int(aggregate_rating.get("reviewCount"))
    review_score = item.get("review_score")
    if review_score in (None, ""):
        raw_score = _normalize_space(aggregate_rating.get("ratingValue"))
        try:
            review_score = float(raw_score) if raw_score else None
        except ValueError:
            review_score = None

    delivery_blob = " ".join(
        part
        for part in [
            _normalize_space(item.get("shipping_fee")),
            _first_text(
                soup,
                [
                    '[data-badge-id="ROCKET_MERCHANT"]',
                    '[data-badge-id="ROCKET"]',
                    '[data-badge-id="ROCKET_GROWTH"]',
                    '[data-badge-id="FRESH"]',
                    '[data-badge-id="ROCKET_FRESH"]',
                    '[data-testid="wp-ui-biz-badge"]',
                ],
            ),
            _first_text(
                soup,
                [
                    '[data-badge-type="feePrice"]',
                    '.TextBadge_feePrice__n_gta',
                    ".prod-shipping-fee-message",
                    ".shipping-fee-title",
                    ".delivery-fee",
                    "[class*='shipping']",
                    "[class*='Rocket']",
                ],
            ),
            full_text,
        ]
        if part
    )
    delivery_type = _detect_delivery_type_from_dom(soup, delivery_blob)
    has_shipping_fee, shipping_fee_text = _detect_shipping_fee_from_dom(soup, delivery_blob)
    seller_info = _extract_labeled_value(
        soup,
        [
            "판매자",
            "판매자 정보",
            "상호/대표자",
            "상호명 및 대표자",
            "판매자명",
        ],
    )
    origin_country = _extract_labeled_value(soup, ["제조국", "원산지", "제조국(원산지)"])
    model_name = _extract_labeled_value(soup, ["모델명", "품명 및 모델명"])
    option_count = _extract_option_count(soup, full_text)

    return {
        "title": title or "",
        "price": price,
        "review_count": review_count,
        "review_score": review_score,
        "product_url": product_url,
        "image_url": image_url or "",
        "category": category,
        "coupon_applied": coupon_applied,
        "delivery_type": delivery_type,
        "has_shipping_fee": has_shipping_fee,
        "shipping_fee": shipping_fee_text or item.get("shipping_fee"),
        "seller_info": seller_info,
        "product_id": product_id,
        "option_count": option_count,
        "origin_country": origin_country,
        "model_name": model_name,
    }


def _build_detail_parse_debug(item: Dict[str, Any], detail_fields: Dict[str, Any], html: str) -> Dict[str, Any]:
    filled_fields = [
        key
        for key in ("category", "seller_info", "option_count", "origin_country", "model_name", "delivery_type")
        if detail_fields.get(key) not in (None, "", [])
    ]
    return {
        "product_id": detail_fields.get("product_id") or _extract_product_id_from_url(item.get("url") or item.get("product_url")),
        "product_url": item.get("url") or item.get("product_url") or "",
        "html_len": len(str(html or "")),
        "filled_fields": filled_fields,
        "filled_count": len(filled_fields),
        "category_found": bool(detail_fields.get("category")),
        "seller_found": bool(detail_fields.get("seller_info")),
        "option_found": detail_fields.get("option_count") is not None,
        "origin_found": bool(detail_fields.get("origin_country")),
        "model_found": bool(detail_fields.get("model_name")),
        "delivery_found": bool(detail_fields.get("delivery_type")),
    }


def _enrich_result_with_detail_pages(crawler: Any, result_data: Dict[str, Any], *, keyword: str = "") -> Dict[str, Any]:
    items = list(result_data.get("top10_items") or [])
    if not items:
        return result_data

    enriched_items = []
    detail_debug_rows: List[Dict[str, Any]] = []
    detail_html_by_product_id: Dict[str, Dict[str, Any]] = {}
    if keyword and hasattr(crawler, "fetch_detail_pages_via_search"):
        try:
            detail_html_by_product_id = crawler.fetch_detail_pages_via_search(keyword, items) or {}
        except Exception:
            detail_html_by_product_id = {}
    for item in items:
        url = _normalize_space(item.get("url") or item.get("product_url"))
        enriched = dict(item)
        enriched["product_url"] = url
        enriched.setdefault("image_url", "")
        enriched.setdefault("category", "")
        enriched.setdefault("coupon_applied", False)
        enriched.setdefault("delivery_type", "")
        enriched.setdefault("has_shipping_fee", None)
        enriched.setdefault("seller_info", "")
        enriched.setdefault("product_id", _extract_product_id_from_url(url))
        enriched.setdefault("option_count", None)
        enriched.setdefault("origin_country", "")
        enriched.setdefault("model_name", "")
        enriched.setdefault("detail_fetch_ok", False)
        enriched.setdefault("detail_parse_filled_count", 0)
        product_id = enriched.get("product_id") or _extract_product_id_from_url(url)
        html_bundle = detail_html_by_product_id.get(str(product_id or ""))
        html = html_bundle.get("html") if isinstance(html_bundle, dict) else None
        fetch_debug = html_bundle.get("fetch_debug") if isinstance(html_bundle, dict) else {}

        if html is None and url:
            try:
                if hasattr(crawler, "fetch_detail_page_html"):
                    html = crawler.fetch_detail_page_html(url)
                elif hasattr(crawler, "_bright_request_fetch_html"):
                    html = crawler._bright_request_fetch_html(url)
                else:
                    html = None
            except Exception:
                html = None
            fetch_debug = (
                getattr(crawler, "get_last_detail_fetch_debug", lambda: {})()
                or getattr(crawler, "get_last_bright_request_debug", lambda: {})()
            )

        if url:
            if html:
                detail_fields = _extract_detail_fields(html, enriched)
                parse_debug = _build_detail_parse_debug(enriched, detail_fields, html)
                enriched.update(detail_fields)
                enriched["detail_fetch_ok"] = True
                enriched["detail_parse_filled_count"] = parse_debug.get("filled_count", 0)
                detail_debug_rows.append(
                    {
                        "product_id": parse_debug.get("product_id") or enriched.get("product_id"),
                        "product_url": url,
                        "fetch_ok": True,
                        "fetch_debug": fetch_debug,
                        "parse_debug": parse_debug,
                    }
                )
                print(
                    "[DETAIL_PARSE] "
                    f"product_id={parse_debug.get('product_id') or '-'} "
                    f"html_len={parse_debug.get('html_len')} "
                    f"filled={parse_debug.get('filled_count')} "
                    f"fields={','.join(parse_debug.get('filled_fields') or []) or '-'}"
                )
            else:
                enriched["detail_fetch_ok"] = False
                enriched["detail_parse_filled_count"] = 0
                detail_debug_rows.append(
                    {
                        "product_id": enriched.get("product_id") or _extract_product_id_from_url(url),
                        "product_url": url,
                        "fetch_ok": False,
                        "fetch_debug": fetch_debug,
                        "parse_debug": {},
                    }
                )
                print(
                    "[DETAIL_FETCH_FAIL] "
                    f"product_id={enriched.get('product_id') or '-'} "
                    f"status={fetch_debug.get('status_code', '-')} "
                    f"error={fetch_debug.get('error_code', '-')} "
                    f"body_len={fetch_debug.get('body_len', '-')} "
                    f"content_type={fetch_debug.get('content_type', '-')}"
                )

        enriched_items.append(enriched)

    updated = dict(result_data)
    updated["top10_items"] = enriched_items
    updated["detail_debug"] = detail_debug_rows
    return updated


def _run_keyword_via_smoke_worker(crawler: Any, keyword: str) -> Dict[str, Any]:
    kw = str(keyword or "").strip()
    if not kw:
        return crawler._result_with_reason("EMPTY_KEYWORD")

    _clear_smoke_artifacts()
    smoke_wait_not_before = time.time() - 0.5
    os.environ["COUPANG_SMOKE_COUPANG_QUERY"] = kw
    ok = crawler.smoke_open_playwright_chromium_window("https://www.google.com/", wait_seconds=5.0)
    if not ok:
        return crawler._result_with_reason("SMOKE_START_FAILED")

    try:
        probe_ok, status = crawler.poll_smoke_until_coupang_probe_finished(timeout_seconds=180.0)
        smoke_payload = _wait_smoke_payload_ready(
            kw, timeout_seconds=120.0, not_before=smoke_wait_not_before
        )
        if not smoke_payload and SMOKE_JSON_PATH.is_file():
            try:
                smoke_payload = json.loads(SMOKE_JSON_PATH.read_text(encoding="utf-8"))
            except Exception:
                smoke_payload = {}

        result_data: Dict[str, Any]
        if SMOKE_HTML_PATH.is_file():
            result_data = crawler.parse_local_html(str(SMOKE_HTML_PATH))
        else:
            result_data = crawler._result_with_reason("SMOKE_HTML_MISSING")

        if isinstance(smoke_payload, dict) and smoke_payload.get("top10"):
            result_data = _apply_smoke_payload_to_result(result_data, crawler, smoke_payload)
            result_data["reason_code"] = "OK"

        if isinstance(smoke_payload, dict):
            result_data["page_title"] = smoke_payload.get("title") or result_data.get("page_title") or ""
            result_data["page_url"] = smoke_payload.get("url") or result_data.get("page_url") or ""
            result_data["html_len"] = smoke_payload.get("html_len") or result_data.get("html_len")
            if smoke_payload.get("organic_count") not in (None, ""):
                result_data["product_count"] = smoke_payload.get("organic_count")
            result_data["fetch_source"] = "smoke"
            if not result_data.get("detail_debug"):
                detail_results = smoke_payload.get("detail_results")
                if isinstance(detail_results, list) and detail_results:
                    result_data["detail_debug"] = detail_results
                else:
                    rank1_detail = smoke_payload.get("rank1_detail")
                    if isinstance(rank1_detail, dict) and rank1_detail:
                        result_data["detail_debug"] = [rank1_detail]
                    else:
                        result_data.setdefault("detail_debug", [])
        if not probe_ok and str(result_data.get("reason_code") or "").strip() == "OK":
            result_data["reason_code"] = "SMOKE_PROBE_FAILED"
        if not probe_ok and not isinstance(smoke_payload, dict):
            result_data["reason_code"] = "SMOKE_PROBE_FAILED"
        return result_data
    finally:
        try:
            crawler.stop_smoke_playwright_chromium_window(join_timeout=15.0)
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ported Coupang crawler core")
    parser.add_argument("--keyword", default="", help="검색 키워드. 비우면 MANUAL_KEYWORD 사용")
    parser.add_argument("--bootstrap-login", action="store_true", help="로그인 세션 준비 모드")
    parser.add_argument("--wait-seconds", type=int, default=120, help="준비 모드 대기 시간")
    parser.add_argument("--open-home-ready", action="store_true", help="쿠팡 홈을 열고 수동 조작 대기")
    parser.add_argument("--open-google-ready", action="store_true", help="Google 홈을 열고 수동 조작 대기")
    parser.add_argument("--open-search-ready", action="store_true", help="쿠팡 검색 준비 화면 대기")
    parser.add_argument("--parse-url", default="", help="쿠팡 검색결과 URL 파싱")
    parser.add_argument("--parse-local-html", default="", help="저장된 HTML 파일 파싱")
    args = parser.parse_args()

    _prepare_environment()

    try:
        from coupang_crawler import get_shared_crawler, save_to_excel
    except Exception as exc:  # pragma: no cover - import errors are runtime setup issues
        raise RuntimeError(
            "ported crawler core import failed. Install local-crawler requirements first."
        ) from exc

    crawler = get_shared_crawler()
    result_data: Optional[Dict[str, Any]] = None

    if args.bootstrap_login:
        ok = crawler.bootstrap_login_session(wait_seconds=args.wait_seconds)
        _dump_result(
            {
                "mode": "bootstrap_login",
                "ok": bool(ok),
                "profile_dir": crawler._chrome_user_data_dir,
                "profile": crawler._chrome_profile,
            }
        )
        return

    if args.open_home_ready:
        ok = crawler.open_home_ready_session(wait_seconds=args.wait_seconds)
        _dump_result(
            {
                "mode": "open_home_ready",
                "ok": bool(ok),
                "profile_dir": crawler._chrome_user_data_dir,
                "profile": crawler._chrome_profile,
            }
        )
        return

    if args.open_google_ready:
        ok = crawler.open_google_ready_session(wait_seconds=args.wait_seconds)
        _dump_result(
            {
                "mode": "open_google_ready",
                "ok": bool(ok),
                "profile_dir": crawler._chrome_user_data_dir,
                "profile": crawler._chrome_profile,
            }
        )
        return

    if args.open_search_ready:
        ok = crawler.open_search_ready_session(wait_seconds=args.wait_seconds)
        _dump_result(
            {
                "mode": "open_search_ready",
                "ok": bool(ok),
                "profile_dir": crawler._chrome_user_data_dir,
                "profile": crawler._chrome_profile,
            }
        )
        return

    if args.parse_url:
        result_data = crawler.parse_coupang_search_url(args.parse_url)
    elif args.parse_local_html:
        result_data = crawler.parse_local_html(args.parse_local_html)
    else:
        keyword = (args.keyword or os.environ.get("MANUAL_KEYWORD") or "").strip()
        if not keyword:
            raise SystemExit("keyword is required. Pass --keyword or set MANUAL_KEYWORD in .env")
        result_data = _run_keyword_via_smoke_worker(crawler, keyword)
        if result_data and isinstance(result_data, dict):
            result_data.setdefault("detail_debug", [])

    _dump_result(
        {
            "result": result_data,
            "stats": crawler.get_stats(),
            "last_fetch_source": crawler.get_last_fetch_source(),
            "last_error": crawler.get_last_error(),
        }
    )
    if result_data:
        save_to_excel(result_data)


if __name__ == "__main__":
    main()
