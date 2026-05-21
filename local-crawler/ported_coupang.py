from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from bs4 import BeautifulSoup


LOCAL_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = LOCAL_ROOT.parent
PORTING_ROOT = WORKSPACE_ROOT / "porting" / "coupang_crawl_core"
ENV_PATH = LOCAL_ROOT / ".env"
OUTPUT_DIR = LOCAL_ROOT / "output"


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
    if str(PORTING_ROOT) not in sys.path:
        sys.path.insert(0, str(PORTING_ROOT))


def _dump_result(payload: Dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / "ported_last_result.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


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
                "img.prod-image__detail",
                "img[src]",
            ],
            "content",
        ) or _first_attr(soup, ["img.prod-image__detail", "img[src]"], "src")

    category = _extract_category_text(soup, blocks)
    coupon_applied = _detect_coupon_applied(full_text)

    delivery_blob = " ".join(
        part
        for part in [
            _normalize_space(item.get("shipping_fee")),
            _first_text(
                soup,
                [
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
    delivery_type = _detect_delivery_type(delivery_blob)
    has_shipping_fee, shipping_fee_text = _detect_shipping_fee(delivery_blob)

    return {
        "product_url": item.get("url") or item.get("product_url") or "",
        "image_url": image_url or "",
        "category": category,
        "coupon_applied": coupon_applied,
        "delivery_type": delivery_type,
        "has_shipping_fee": has_shipping_fee,
        "shipping_fee": shipping_fee_text or item.get("shipping_fee"),
    }


def _enrich_result_with_detail_pages(crawler: Any, result_data: Dict[str, Any]) -> Dict[str, Any]:
    items = list(result_data.get("top10_items") or [])
    if not items:
        return result_data

    enriched_items = []
    for item in items:
        url = _normalize_space(item.get("url") or item.get("product_url"))
        enriched = dict(item)
        enriched["product_url"] = url
        enriched.setdefault("image_url", "")
        enriched.setdefault("category", "")
        enriched.setdefault("coupon_applied", False)
        enriched.setdefault("delivery_type", "")
        enriched.setdefault("has_shipping_fee", None)

        if url and hasattr(crawler, "_bright_request_fetch_html"):
            try:
                html = crawler._bright_request_fetch_html(url)
            except Exception:
                html = None
            if html:
                enriched.update(_extract_detail_fields(html, enriched))

        enriched_items.append(enriched)

    updated = dict(result_data)
    updated["top10_items"] = enriched_items
    return updated


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
        os.environ.setdefault("COUPANG_SMOKE_COUPANG_QUERY", keyword)
        result_data = crawler.crawl_coupang(keyword)
        if result_data and str(result_data.get("reason_code") or "") == "OK":
            result_data = _enrich_result_with_detail_pages(crawler, result_data)

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
