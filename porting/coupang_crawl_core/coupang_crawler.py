import argparse
import asyncio
import atexit
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse, parse_qsl, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import BrowserContext, Error, Page, Playwright, TimeoutError, sync_playwright

try:
    from db import insert_coupang_search_snapshot
except Exception:
    insert_coupang_search_snapshot = None

# CP949 환경에서도 깨지지 않게 출력하기 위한 유틸 함수
def safe_print(*args, **kwargs):
    text = " ".join(map(str, args))
    try:
        print(text, **kwargs)
    except UnicodeEncodeError:
        print(text.encode("cp949", errors="ignore").decode("cp949", errors="ignore"), **kwargs)


def _dump_smoke_extract_report(payload: Dict[str, Any]) -> None:
    """스모크 결과를 .smoke/last_smoke_extract.json (+ 키워드별) 에 저장한다."""
    if not isinstance(payload, dict):
        return
    smoke_dir = Path(__file__).resolve().parent / ".smoke"
    out_p = smoke_dir / "last_smoke_extract.json"
    try:
        smoke_dir.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        safe_print(f"[SMOKE] 추출 결과 JSON 저장: {out_p}")
        kw = str(payload.get("keyword") or "").strip()
        if kw:
            slug = re.sub(r"[^\w가-힣]+", "_", kw).strip("_")[:80] or "keyword"
            per_kw = smoke_dir / f"last_smoke_extract_{slug}.json"
            with open(per_kw, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as ex:
        safe_print(f"[SMOKE] 추출 결과 JSON 저장 실패(무시): {ex!r}")


def _dump_smoke_search_html(html: str) -> None:
    """스모크 검색 결과 HTML을 .smoke/last_smoke_search.html 에 저장한다."""
    text = str(html or "")
    if not text.strip():
        return
    out_p = Path(__file__).resolve().parent / ".smoke" / "last_smoke_search.html"
    try:
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            f.write(text)
        safe_print(f"[SMOKE] 검색 결과 HTML 저장: {out_p}")
    except Exception as ex:
        safe_print(f"[SMOKE] 검색 결과 HTML 저장 실패(무시): {ex!r}")


def _smoke_strict_clean_enabled() -> bool:
    raw = os.environ.get("COUPANG_SMOKE_STRICT_CLEAN", "0")
    return str(raw).strip().lower() not in {"0", "false", "no", "off", "n"}


def _is_monthly_purchase_proof_text(text: str) -> bool:
    """ATF 배지: '한 달간 N명 이상 구매했어요' (리뷰 '…구매했어요' 제외)."""
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if not t or "구매했어요" not in t or "상품평" in t:
        return False
    return bool(re.search(r"한\s*달", t)) and bool(re.search(r"[\d,]+\s*명", t))


def _parse_user_atf_badge_html(html: str) -> str:
    """
    사용자 제공 ATF 구조:
    social_proof_purchase img + p.twc-text-bluegray-900 > 한 달간<span> N명 이상 </span>구매했어요
    """
    raw = str(html or "")
    if "social_proof_purchase" not in raw and "구매했어요" not in raw:
        return ""

    fast = _parse_monthly_sales_from_html_fast(raw)
    if fast:
        return fast

    try:
        soup = BeautifulSoup(raw, "html.parser")
        for img in soup.find_all("img", src=re.compile(r"social_proof_purchase", re.I)):
            box = img.find_parent("div", class_=re.compile(r"twc-flex"))
            if not box:
                box = img.parent
            if not box:
                continue
            for p in box.find_all("p"):
                text = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
                if _is_monthly_purchase_proof_text(text):
                    parsed = normalize_monthly_sales_display(text)
                    if parsed:
                        return parsed
    except Exception:
        pass
    return ""


# ATF: 한 달간<span> 800명 이상 </span>구매했어요 — span 분리 HTML용 빠른 정규식
_PURCHASE_PROOF_ATF_HTML_RE = re.compile(
    r"한\s*달간(?:\s*<[^>]+>\s*)*([\d,]+)\s*명\s*이상(?:\s*<[^>]+>\s*)*구매했어요",
    re.IGNORECASE | re.DOTALL,
)
_PURCHASE_PROOF_ATF_TEXT_RE = re.compile(
    r"한\s*달간\s*([\d,]+)\s*명\s*이상\s*구매했어요",
    re.IGNORECASE,
)
# JSON/SSR 이스케이프: 한 달간\u003cs\u003e800\u003c/s\u003e... 또는 태그 혼합
_PURCHASE_PROOF_LOOSE_RE = re.compile(
    r"한\s*달간(?:\\u003c[^\\]+\\u003e|<[^>]+>|\s)*([\d,]+)\s*명\s*이상",
    re.IGNORECASE,
)

_DOM_PURCHASE_PROOF_JS = """() => {
    const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
    const ok = (t) =>
        t.includes('구매했어요') &&
        t.includes('명') &&
        !t.includes('상품평') &&
        /한\\s*달/.test(t);
    const img = document.querySelector('img[src*="social_proof_purchase"]');
    if (img) {
        const box = img.closest('div.twc-flex') || img.parentElement;
        const p = box && box.querySelector('p');
        if (p) {
            const t = norm(p.textContent || p.innerText || '');
            if (ok(t)) return t;
        }
    }
    const nodes = document.querySelectorAll('p, span, div');
    for (const el of nodes) {
        const t = norm(el.textContent || '');
        if (!ok(t)) continue;
        if (/한\\s*달간\\s*[\\d,]+\\s*명/.test(t)) return t;
    }
    return '';
}"""


def _smoke_detail_fast_mode() -> bool:
    """기본 fast: HTML/ DOM 즉시 파싱 우선, networkidle·장대기 생략."""
    raw = str(os.environ.get("COUPANG_SMOKE_DETAIL_FAST", "1") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off", "n"}


def _smoke_detail_use_network_idle() -> bool:
    raw = str(os.environ.get("COUPANG_SMOKE_DETAIL_NETWORK_IDLE", "0") or "0").strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _smoke_detail_parse_attempts() -> int:
    default = "2" if _smoke_detail_fast_mode() else "4"
    raw = str(os.environ.get("COUPANG_SMOKE_DETAIL_PARSE_ATTEMPTS", default) or default).strip()
    try:
        return max(1, min(8, int(raw)))
    except ValueError:
        return 2 if _smoke_detail_fast_mode() else 4


def _smoke_detail_badge_wait_ms() -> int:
    default = "2800" if _smoke_detail_fast_mode() else "5000"
    raw = str(os.environ.get("COUPANG_SMOKE_DETAIL_BADGE_WAIT_MS", default) or default).strip()
    try:
        return max(600, min(15000, int(raw)))
    except ValueError:
        return 2800 if _smoke_detail_fast_mode() else 5000


def _smoke_detail_retry_wait_ms() -> int:
    raw = str(os.environ.get("COUPANG_SMOKE_DETAIL_RETRY_WAIT_MS", "350") or "350").strip()
    try:
        return max(150, min(2000, int(raw)))
    except ValueError:
        return 350


def _smoke_detail_goto_wait_until() -> str:
    raw = str(os.environ.get("COUPANG_SMOKE_DETAIL_GOTO_WAIT", "") or "").strip().lower()
    if raw in {"load", "domcontentloaded", "commit", "networkidle"}:
        return raw
    return "domcontentloaded" if _smoke_detail_fast_mode() else "load"


def _smoke_detail_goto_timeout_ms() -> int:
    raw = str(os.environ.get("COUPANG_SMOKE_DETAIL_GOTO_TIMEOUT_MS", "22000") or "22000").strip()
    try:
        return max(12000, min(45000, int(raw)))
    except ValueError:
        return 22000


def _smoke_detail_tab_pause_ms() -> Tuple[int, int]:
    if _smoke_detail_fast_mode():
        return (80, 160)
    return (180, 380)


def _smoke_detail_debug_mode() -> str:
    """
    COUPANG_SMOKE_DEBUG_DETAIL:
      - miss (기본): 판매량 파싱 실패·차단·타임아웃 시만 덤프
      - all / 1 / true: 상세 탭마다 덤프
      - off / 0: 덤프 안 함
    """
    raw = str(os.environ.get("COUPANG_SMOKE_DEBUG_DETAIL", "miss") or "miss").strip().lower()
    if raw in {"0", "off", "false", "no", "n"}:
        return "off"
    if raw in {"1", "true", "yes", "y", "all", "on"}:
        return "all"
    return "miss"


def _smoke_detail_debug_dir() -> Path:
    return Path(__file__).resolve().parent / ".smoke" / "detail_debug"


def _html_purchase_signals(html: str) -> Dict[str, Any]:
    """파싱 시점 HTML에 배지 관련 문자열이 실제로 있는지 진단."""
    raw = str(html or "")
    scan = raw[:500000]
    flat = re.sub(r"<[^>]+>", " ", scan)
    flat = re.sub(r"\\u003c[^\\]+\\u003e", " ", flat)
    flat = re.sub(r"\s+", " ", flat)
    text_match = bool(_PURCHASE_PROOF_ATF_TEXT_RE.search(flat))
    return {
        "has_badge_img": "social_proof_purchase" in raw,
        "has_purchase_text": text_match,
        "has_guwahaeyo": "구매했어요" in scan,
        "has_handal": bool(re.search(r"한\s*달", scan)),
        "fast_parse_preview": _parse_monthly_sales_from_html_fast(raw) or "",
    }


def _should_dump_smoke_detail_debug(*, parsed_sales: str, blocked: bool, error: bool) -> bool:
    mode = _smoke_detail_debug_mode()
    if mode == "off":
        return False
    if mode == "all":
        return True
    if blocked or error:
        return True
    return not str(parsed_sales or "").strip()


def _digits_to_monthly_sales_display(num_text: str) -> str:
    digits = str(num_text or "").replace(",", "").strip()
    if not digits.isdigit():
        return ""
    return f"{int(digits)}개"


def _parse_monthly_sales_from_html_fast(html: str) -> str:
    """social_proof 배지·ATF <p> 구조만 빠르게 스캔 (전체 BeautifulSoup 생략)."""
    raw = str(html or "")
    if "구매했어요" not in raw or "명" not in raw:
        return ""

    anchor = raw.find("social_proof_purchase")
    if anchor >= 0:
        chunk = raw[anchor : anchor + 2400]
        match = _PURCHASE_PROOF_ATF_HTML_RE.search(chunk)
        if match:
            out = _digits_to_monthly_sales_display(match.group(1))
            if out:
                return out
        match = _PURCHASE_PROOF_LOOSE_RE.search(chunk)
        if match:
            out = _digits_to_monthly_sales_display(match.group(1))
            if out:
                return out

    scan_limit = 800000 if len(raw) > 800000 else len(raw)
    head = raw[:scan_limit]
    for pattern in (_PURCHASE_PROOF_ATF_HTML_RE, _PURCHASE_PROOF_LOOSE_RE):
        match = pattern.search(head)
        if match:
            out = _digits_to_monthly_sales_display(match.group(1))
            if out:
                return out

    flat = re.sub(r"<[^>]+>", " ", head)
    flat = re.sub(r"\\u003c[^\\]+\\u003e", " ", flat)
    flat = re.sub(r"\s+", " ", flat)
    match = _PURCHASE_PROOF_ATF_TEXT_RE.search(flat)
    if match:
        return _digits_to_monthly_sales_display(match.group(1))
    return ""


def normalize_monthly_sales_display(raw: Any, *, default_zero: bool = False) -> str:
    """예: '한 달간 800명 이상 구매했어요' → '800개'. 이미 '800개' 형식이면 그대로 통과."""
    text = re.sub(r"\s+", " ", str(raw or "")).strip()
    if not text:
        return "0개" if default_zero else ""

    compact = re.sub(r"\s+", "", text)
    if re.fullmatch(r"[\d,]+개?", compact):
        digits = re.sub(r"[^\d]", "", compact)
        if digits:
            return f"{int(digits)}개"

    if not _is_monthly_purchase_proof_text(text):
        return "0개" if default_zero else ""

    match = re.search(r"([\d,]+)\s*명", text)
    if match:
        return f"{int(match.group(1).replace(',', ''))}개"
    match = re.search(r"한\s*달간.*?([\d,]+)\s*명", text)
    if match:
        return f"{int(match.group(1).replace(',', ''))}개"
    return "0개" if default_zero else ""


def _extract_purchase_proof_lines_from_html(html: str) -> List[str]:
    """상세 ATF proof 후보 (빠른 정규식 우선)."""
    raw = str(html or "")
    lines: List[str] = []
    fast = _parse_monthly_sales_from_html_fast(raw)
    if fast:
        digits = re.sub(r"[^\d]", "", fast)
        if digits:
            lines.append(f"한 달간 {digits}명 이상 구매했어요")

    anchor = raw.find("social_proof_purchase")
    if anchor >= 0:
        snippet = re.sub(r"<[^>]+>", " ", raw[anchor : anchor + 1400])
        snippet = re.sub(r"\s+", " ", snippet).strip()
        if _is_monthly_purchase_proof_text(snippet):
            lines.append(snippet[:200])

    if not lines:
        for match in re.finditer(r".{0,120}구매했어요", raw[:150000]):
            snippet = re.sub(r"<[^>]+>", " ", match.group(0))
            snippet = re.sub(r"\s+", " ", snippet).strip()
            if snippet and _is_monthly_purchase_proof_text(snippet) and "명" in snippet:
                lines.append(snippet)
    uniq: List[str] = []
    seen: set[str] = set()
    for text in lines:
        if text in seen:
            continue
        seen.add(text)
        uniq.append(text)
    return uniq


def _persist_smoke_extract_report_to_db(payload: Dict[str, Any]) -> None:
    """
    스모크 추출 결과를 쿠팡 전용 DB 테이블에 저장한다.
    기존 주제어 분석 테이블(keyword_metrics 등)과 분리된 경로다.
    """
    if insert_coupang_search_snapshot is None:
        return
    if not isinstance(payload, dict):
        return
    if str(os.environ.get("COUPANG_SMOKE_EXTRACT_DB", "true")).strip().lower() in {"0", "false", "off", "no"}:
        return
    try:
        stored = int(insert_coupang_search_snapshot(payload) or 0)
        safe_print(f"[SMOKE][DB] 쿠팡 스냅샷 저장 완료 items={stored}")
    except Exception as db_ex:
        safe_print(f"[SMOKE][DB] 쿠팡 스냅샷 저장 실패(무시): {db_ex!r}")


# --- playwright-stealth (탐지 완화 스크립트 주입) ---
# PyPI 패키지 "playwright-stealth" 2.x(Mattwmaster58): 동기 경로는 stealth_sync가 아니라
#   Stealth 인스턴스의 apply_stealth_sync(page) 가 공식 API다.
# 구버전 1.x 일부: stealth_sync(page) 단일 함수만 제공하는 배포가 있다.
# 따라서 v2 Stealth를 먼저 시도하고, 없을 때만 stealth_sync 로 폴백한다.
# STEALTH_AVAILABLE 은 둘 중 실제 호출 가능한 경로가 있으면 True (차단 reason 분기 등에 사용).
import importlib.util

_STEALTH_V2_INSTANCE: Optional[Any] = None
_STEALTH_LEGACY_FN: Optional[Any] = None

try:
    from playwright_stealth import Stealth as _StealthCls  # type: ignore

    if hasattr(_StealthCls, "apply_stealth_sync"):
        _STEALTH_V2_CLS = _StealthCls
    else:
        _STEALTH_V2_CLS = None
except Exception:
    _STEALTH_V2_CLS = None

if _STEALTH_V2_CLS is None:
    try:
        from playwright_stealth import stealth_sync as _legacy_sync  # type: ignore

        _STEALTH_LEGACY_FN = _legacy_sync if callable(_legacy_sync) else None
    except Exception:
        _STEALTH_LEGACY_FN = None

STEALTH_AVAILABLE = _STEALTH_V2_CLS is not None or _STEALTH_LEGACY_FN is not None
_STEALTH_PKG_PRESENT = importlib.util.find_spec("playwright_stealth") is not None


def apply_stealth(page: Page) -> None:
    global _STEALTH_V2_INSTANCE
    if not STEALTH_AVAILABLE:
        return
    try:
        if _STEALTH_V2_CLS is not None:
            if _STEALTH_V2_INSTANCE is None:
                _STEALTH_V2_INSTANCE = _STEALTH_V2_CLS()
            _STEALTH_V2_INSTANCE.apply_stealth_sync(page)
        elif _STEALTH_LEGACY_FN is not None:
            _STEALTH_LEGACY_FN(page)
        safe_print("[INFO] Stealth 적용 완료")
    except Exception as e:
        safe_print(f"[ERROR] Stealth 적용 실패: {str(e)}")


# 상품 리스트 대기·파싱 공통 셀렉터 (DOM 변경 시 한곳만 수정)
_PRODUCT_LIST_SELECTOR = (
    "li.search-product, "
    "li.ProductUnit_productUnit__Qd6sv, "
    "li[data-product-id], "
    "ul#product-list > li, "
    "ul#productList > li, "
    "li[class*='ProductUnit'], "
    "li[class*='productUnit']"
)

# BeautifulSoup 파싱 시 동일 범위의 카드 후보(CSS OR)
_PRODUCT_CARD_HTML_SELECTOR = (
    "li.ProductUnit_productUnit__Qd6sv, li.search-product, "
    "ul#product-list > li, ul#productList > li, li[data-product-id], "
    "li[class*='ProductUnit'], li[class*='productUnit']"
)

STABLE_GOOGLE_NAV_QUERIES: Tuple[str, ...] = (
    "쿠팡",
    "coupang",
    "쿠팡 로켓배송",
    "쿠팡 로켓와우",
    "로켓프레시",
    "쿠팡 로켓프레시",
    "쿠팡 로켓직구",
    "쿠팡 공식",
    "쿠팡 홈",
)

HEADLESS = True


def coupang_bright_request_is_enabled() -> bool:
    """대시보드 등 외부에서 Bright 선행(/request) 사용 여부를 묻는 용도."""
    return _coupang_bright_request_enabled()


def _coupang_bright_request_enabled() -> bool:
    """Bright /request 선행 수집: 기본 ON. `COUPANG_BRIGHT_REQUEST=off` 등으로만 끈다."""
    raw = os.environ.get("COUPANG_BRIGHT_REQUEST")
    if raw is None or str(raw).strip() == "":
        return True
    s = str(raw).strip().lower()
    if s in ("0", "false", "no", "off", "n"):
        return False
    return True


def _ensure_windows_proactor_policy() -> None:
    """Playwright subprocess requires Proactor loop on Windows."""
    if sys.platform != "win32":
        return
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        return

class CoupangCrawler:
    """Playwright 기반 쿠팡 검색 Top10 수집기."""

    def __init__(self) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._last_success_cache: Dict[str, Dict[str, Any]] = {}
        self._stats = {
            "cache_hit": 0,
            "requests_ok": 0,
            "playwright_ok": 0,
            "failed": 0,
            "blocked": 0,
            "bright_ok": 0,
            "bright_error": 0,
        }
        self._last_error: Dict[str, str] = {}
        self._last_fetch_source = "unknown"
        self._last_bright_request_debug: Dict[str, Any] = {}
        self._last_detail_fetch_debug: Dict[str, Any] = {}
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._io_lock = threading.RLock()
        self._smoke_thread: Optional[threading.Thread] = None
        self._smoke_stop_event: Optional[threading.Event] = None
        self._smoke_subproc: Optional[subprocess.Popen] = None
        self._smoke_stop_file: Optional[str] = None
        self._smoke_tmpdir: Optional[str] = None
        self._smoke_status: Dict[str, Any] = {
            "phase": "idle",
            "headless": None,
            "target_url": "",
            "page_url": "",
            "page_title": "",
            "opened_at": None,
            "closed_at": None,
            "hint": "",
            "error": "",
            "top10_items": [],
        }
        env_raw = str(os.environ.get("COUPANG_HEADLESS", "")).strip().lower()
        if env_raw in {"0", "false", "n", "no"}:
            self._headless = False
        elif env_raw in {"1", "true", "y", "yes"}:
            self._headless = True
        else:
            self._headless = HEADLESS

        self._chrome_user_data_dir = str(os.environ.get("COUPANG_CHROME_USER_DATA_DIR", "")).strip()
        self._chrome_profile = str(os.environ.get("COUPANG_CHROME_PROFILE", "")).strip()
        if not self._chrome_user_data_dir:
            self._chrome_user_data_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                ".coupang_chrome_profile_crawl",
            )
        os.makedirs(self._chrome_user_data_dir, exist_ok=True)
        # 수동 준비(홈/로그인/검색 대기)와 자동 크롤이 프로필 락을 나누지 않도록 분리
        self._prep_user_data_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            ".coupang_chrome_profile_prep",
        )
        os.makedirs(self._prep_user_data_dir, exist_ok=True)
        if not self._chrome_profile:
            self._chrome_profile = "Default"
        # 스모크 probe 직후 대시보드에 즉시 반영할 순위표 (같은 프로세스·스레드 공유 전제)
        self._smoke_ranked_ui_cache: Dict[str, Any] = {"keyword": "", "items": []}

    def _reset_smoke_ranked_ui_cache(self, keyword: str) -> None:
        kw = str(keyword or "").strip()
        with self._io_lock:
            self._smoke_ranked_ui_cache = {"keyword": kw, "items": []}

    def _sync_smoke_ranked_ui_cache_from_payload(self, keyword: str, payload: Dict[str, Any]) -> None:
        raw = payload.get("top10") or payload.get("top3") or []
        items_norm: List[Dict[str, Any]] = []
        if isinstance(raw, list):
            for it in raw:
                if not isinstance(it, dict):
                    continue
                try:
                    rk = int(it.get("rank") or 0)
                except Exception:
                    rk = 0
                if rk < 1:
                    continue
                items_norm.append(
                    {
                        "rank": rk,
                        "title": str(it.get("title", "")),
                        "price": str(it.get("price", "")),
                        "shipping": str(it.get("shipping", "")),
                        "review_count": str(it.get("review_count", "")),
                        "review_score": str(it.get("review_score", "")),
                        "url": str(it.get("url", "")),
                    }
                )
        items_norm.sort(key=lambda x: x["rank"])
        kw = str(keyword or "").strip()
        with self._io_lock:
            self._smoke_ranked_ui_cache = {"keyword": kw, "items": items_norm}

    def get_smoke_ranked_ui_cache(self, keyword: str) -> List[Dict[str, Any]]:
        kw = str(keyword or "").strip()
        if not kw:
            return []
        with self._io_lock:
            if self._smoke_ranked_ui_cache.get("keyword", "").strip() != kw:
                return []
            return list(self._smoke_ranked_ui_cache.get("items") or [])

    def _smoke_status_update(self, **kwargs: Any) -> None:
        with self._io_lock:
            merged = {**self._smoke_status, **kwargs}
            if "top10_items" in merged:
                merged["top3_items"] = merged["top10_items"]
            elif "top3_items" in merged and "top10_items" not in merged:
                merged["top10_items"] = merged["top3_items"]
            self._smoke_status = merged

    def get_smoke_playwright_status(self) -> Dict[str, Any]:
        """대시보드에서 스모크 Chromium 진행 여부 확인용(phase·URL 등)."""
        self._maybe_reap_smoke_subprocess()
        with self._io_lock:
            out = dict(self._smoke_status)
            if "top10_items" not in out and out.get("top3_items") is not None:
                out["top10_items"] = out["top3_items"]
            sub = self._smoke_subproc
        if sub is not None and sub.poll() is None:
            out = {
                **out,
                "phase": "windows_subprocess_running",
                "thread_alive": True,
                "headless": False,
                "subprocess_pid": sub.pid,
                "hint": (
                    "별도 Python 프로세스에서 headed Chromium이 실행 중입니다. "
                    "작업 표시줄·Alt+Tab에서 창을 확인하세요. "
                    "Railway 등 **원격 대시보드**만 쓰는 경우 Chromium은 **서버**에서만 떠서 이 PC에는 보이지 않습니다."
                ),
            }
            return out
        out["thread_alive"] = self.is_smoke_playwright_running()
        return out

    @staticmethod
    def _smoke_use_subprocess_launch() -> bool:
        """기본은 in-process(상태 공유). 필요 시 COUPANG_SMOKE_SUBPROCESS=1 로만 별도 프로세스 실행."""
        if str(os.environ.get("COUPANG_SMOKE_SUBPROCESS", "")).strip() == "1":
            return sys.platform == "win32"
        if (
            os.environ.get("RAILWAY_ENVIRONMENT")
            or os.environ.get("RAILWAY_SERVICE_NAME")
            or os.environ.get("RAILWAY_PROJECT_ID")
        ):
            return False
        return False

    def _maybe_reap_smoke_subprocess(self) -> None:
        with self._io_lock:
            sub = self._smoke_subproc
            tmp = self._smoke_tmpdir
        if sub is None:
            return
        if sub.poll() is None:
            return
        with self._io_lock:
            self._smoke_subproc = None
            self._smoke_stop_file = None
            self._smoke_tmpdir = None
            self._smoke_status = {
                **self._smoke_status,
                "phase": "closed",
                "closed_at": time.time(),
                "thread_alive": False,
                "hint": "스모크 자식 프로세스가 종료되었습니다.",
            }
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)

    def _terminate_smoke_subprocess_if_any(self) -> None:
        self._maybe_reap_smoke_subprocess()
        with self._io_lock:
            sub = self._smoke_subproc
            sf = self._smoke_stop_file
            tmp = self._smoke_tmpdir
            self._smoke_subproc = None
            self._smoke_stop_file = None
            self._smoke_tmpdir = None
        if sf:
            try:
                os.makedirs(os.path.dirname(sf), exist_ok=True)
            except OSError:
                pass
            try:
                with open(sf, "w", encoding="utf-8") as fp:
                    fp.write("stop")
            except OSError:
                pass
        if sub is not None and sub.poll() is None:
            try:
                sub.terminate()
                sub.wait(timeout=12.0)
            except Exception:
                try:
                    sub.kill()
                except Exception:
                    pass
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)

    def _sanitize_playwright_browser_env(self) -> None:
        """Railway 리눅스 경로를 Windows 로컬에 복사하면 Chromium을 못 찾으므로 무효 경로는 제거."""
        raw = str(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")).strip()
        if not raw:
            return
        norm = raw.replace("\\", "/")
        if sys.platform == "win32":
            if norm.startswith("/") and not norm.startswith("//"):
                safe_print(
                    "[PLAYWRIGHT_CHECK] Unix 스타일 PLAYWRIGHT_BROWSERS_PATH는 Windows에서 무시합니다. "
                    "(로컬은 기본 캐시 또는 Windows 경로를 사용합니다.)"
                )
                os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
                return
        try:
            base = Path(raw)
        except Exception:
            os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
            return
        if not base.exists():
            safe_print(
                f"[PLAYWRIGHT_CHECK] PLAYWRIGHT_BROWSERS_PATH={raw!r} 경로 없음 — "
                "Playwright 기본 브라우저 캐시로 대체합니다."
            )
            os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)

    def _prep_force_headless(self) -> bool:
        """Linux 서버에 DISPLAY 없으면 headed 실행이 곧바로 죽으므로 headless로 폴백."""
        if sys.platform == "win32":
            return False
        if os.environ.get("DISPLAY"):
            return False
        safe_print("[WARN] DISPLAY 없음 — 준비용 창은 headless로 진행합니다 (서버 환경).")
        return True

    def _cache_key(self, keyword: str) -> str:
        return f"{keyword.strip()}_{datetime.now().strftime('%Y%m%d')}"

    def _fallback_profile_dir(self, prep_profile: bool) -> str:
        suffix = "prep" if prep_profile else "crawl"
        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f".coupang_chrome_profile_{suffix}_fallback_{os.getpid()}_{int(time.time() * 1000)}",
        )

    def _log_playwright_preflight(self) -> None:
        path = str(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")).strip()
        if not path:
            safe_print("[PLAYWRIGHT_CHECK] PLAYWRIGHT_BROWSERS_PATH is not set.")
            return
        base = Path(path)
        bins: List[Path] = []
        if base.exists():
            bins = list(base.glob("chromium-*/chrome-linux64/chrome")) + list(
                base.glob("chromium-*/chrome-win64/chrome.exe")
            )
        safe_print(
            f"[PLAYWRIGHT_CHECK] path={path}, exists={base.exists()}, chromium_bin_count={len(bins)}"
        )

    def _parse_int(self, text: str) -> Optional[int]:
        raw = re.sub(r"[^0-9]", "", str(text or ""))
        if not raw:
            return None
        try:
            return int(raw)
        except Exception:
            return None

    def _parse_float(self, text: str) -> Optional[float]:
        raw = str(text or "").strip()
        if not raw:
            return None
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)", raw)
        if not m:
            return None
        try:
            return float(m.group(1))
        except Exception:
            return None

    def _pick_price_won_from_li(self, li: BeautifulSoup) -> str:
        """
        가격 텍스트에서 실제 판매가를 우선 추출한다.
        - custom-oos 블록의 대표 가격(span)을 최우선 사용
        - '1개당' 같은 단가 안내는 제외
        - fallback에서는 첫 번째 원화 값을 판매가로 사용
        """
        # 1) 최근 DOM: custom-oos (예: 할인율 + 판매가 + 1개당 단가)
        for n in li.select(".custom-oos span, .custom-oos div, [class*='custom-oos'] span"):
            t = n.get_text(" ", strip=True)
            if not t or "개당" in t:
                continue
            m = re.search(r"[\d,]+\s*원", t)
            if m:
                return re.sub(r"\s+", "", m.group(0))

        # 2) 기존 DOM fallback
        area = (
            li.select_one(".PriceArea_priceArea__NntJz")
            or li.select_one(".sale-price")
            or li.select_one("[class*='price']")
        )
        if not area:
            return ""
        blob = area.get_text(" ", strip=True)
        ms = list(re.finditer(r"[\d,]+\s*원", blob))
        if not ms:
            return ""
        # 일반적으로 첫 번째 값이 대표 판매가(뒤쪽은 단가/보조 문구일 수 있음)
        return re.sub(r"\s+", "", ms[0].group(0))

    def _pick_shipping_from_li(self, li: BeautifulSoup) -> str:
        """배송비/로켓 등 배송 관련 배지만 사용(할인율 % 배지 오탐 방지). 없으면 배송 키워드로 보조 추출."""
        n = li.select_one(".TextBadge_feePrice__n_gta, [data-badge-type='feePrice']")
        if n:
            return n.get_text(" ", strip=True)
        for sel in (
            "[class*='DeliveryInfo']",
            "[class*='deliveryInfo']",
            "[class*='DeliveryBadge']",
            "[class*='RocketBadge']",
            "[class*='RocketDelivery']",
            "[class*='rocketDelivery']",
            "[class*='ProductUnit_badge']",
            "[class*='ImageBadge']",
            "[class*='BadgeList']",
        ):
            n2 = li.select_one(sel)
            if n2:
                t = n2.get_text(" ", strip=True)
                if t and not re.fullmatch(r"\d+%", t.strip()):
                    return t
        badge_blob = " ".join(
            x.get_text(" ", strip=True)
            for x in li.select(
                "[class*='Badge'], [class*='badge'], [class*='Delivery'], "
                "[class*='delivery'], [class*='Label'], [class*='label'], "
                "[class*='Rocket'], [class*='rocket'], [data-badge-type]"
            )
        )
        kw_hit = self._pick_shipping_keywords_from_text(badge_blob)
        if kw_hit:
            return kw_hit
        return self._pick_shipping_keywords_from_text(li.get_text(" ", strip=True))

    @staticmethod
    def _absolutize_coupang_url(url: str) -> str:
        raw = str(url or "").strip()
        if not raw:
            return ""
        if raw.startswith("//"):
            return f"https:{raw}"
        if raw.startswith("/"):
            return f"https://www.coupang.com{raw}"
        return raw

    @staticmethod
    def _extract_product_id_from_url(url: str) -> str:
        raw = str(url or "").strip()
        if not raw:
            return ""
        for pattern in (
            r"/vp/products/(\d+)",
            r"/products/(\d+)",
            r"[?&]productId=(\d+)",
            r"[?&]itemId=(\d+)",
        ):
            match = re.search(pattern, raw)
            if match:
                return match.group(1)
        return ""

    def _pick_image_url_from_li(self, li: BeautifulSoup) -> str:
        """검색 결과 카드에서 대표 이미지 URL만 추출한다."""
        image_node = li.select_one(
            "img[src], img[data-src], img[data-img-src], img[data-image-src], img[srcset]"
        )
        if image_node is None:
            return ""

        for attr in ("src", "data-src", "data-img-src", "data-image-src"):
            value = str(image_node.get(attr, "")).strip()
            if value and not value.startswith("data:"):
                return self._absolutize_coupang_url(value)

        srcset = str(image_node.get("srcset", "")).strip()
        if srcset:
            first_item = srcset.split(",")[0].strip()
            first_url = first_item.split(" ")[0].strip()
            if first_url and not first_url.startswith("data:"):
                return self._absolutize_coupang_url(first_url)
        return ""

    @staticmethod
    def _pick_shipping_keywords_from_text(blob: str) -> str:
        """로켓/무료배송/출발·도착 등 검색 결과 카드에 자주 노출되는 배송 문구만 모은다."""
        if not blob:
            return ""
        seen: List[str] = []
        for kw in (
            "로켓배송",
            "판매자로켓",
            "로켓직구",
            "로켓그로스",
            "새벽배송",
            "오늘 출발",
            "오늘출발",
            "도착보장",
            "내일도착",
            "내일 도착",
            "무료배송",
            "판매자 배송",
            "판매자배송",
        ):
            if kw in blob and kw not in seen:
                seen.append(kw)
        return " / ".join(seen)

    @staticmethod
    def _extract_delivery_type_from_badges(li: Any) -> str:
        badge_ids = {
            str(node.get("data-badge-id", "")).strip().upper()
            for node in li.select("[data-badge-id]")
            if str(node.get("data-badge-id", "")).strip()
        }
        if "ROCKET_MERCHANT" in badge_ids:
            return "판매자로켓"
        if "ROCKET" in badge_ids:
            return "로켓배송"
        if "ROCKET_GROWTH" in badge_ids:
            return "로켓그로스"
        if "FRESH" in badge_ids or "ROCKET_FRESH" in badge_ids:
            return "로켓프레시"

        badge_blob = " ".join(
            x.get_text(" ", strip=True)
            for x in li.select(
                "[class*='Badge'], [class*='badge'], [class*='Delivery'], "
                "[class*='delivery'], [class*='Rocket'], [class*='rocket'], [data-testid='wp-ui-biz-badge']"
            )
        )
        for keyword, label in (
            ("판매자로켓", "판매자로켓"),
            ("로켓그로스", "로켓그로스"),
            ("로켓프레시", "로켓프레시"),
            ("로켓배송", "로켓배송"),
            ("판매자배송", "일반배송"),
            ("판매자 배송", "일반배송"),
            ("일반배송", "일반배송"),
        ):
            if keyword in badge_blob:
                return label

        full_blob = " ".join(
            part
            for part in (
                badge_blob,
                li.get_text(" ", strip=True),
            )
            if part
        )
        if any(
            token in full_blob
            for token in (
                "무료배송",
                "배송비",
                "오늘출발",
                "오늘 출발",
                "도착보장",
                "내일도착",
                "내일 도착",
                "무료반품",
            )
        ):
            return "일반배송"
        return ""

    def _normalize_review_count_display(self, raw: str) -> str:
        m = re.search(r"\(\s*([\d,]+)\s*\)", str(raw or ""))
        if m:
            return m.group(1).replace(",", "")
        n = self._parse_int(raw)
        return str(n) if n is not None else str(raw or "").strip()

    def _build_result(self, product_count: int, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        reviews = [float(it["review_count"]) for it in items if it.get("review_count") is not None]
        prices = [float(it["price"]) for it in items if it.get("price") is not None]
        if len(reviews) < 1 or len(prices) < 1:
            return {"product_count": int(product_count), "avg_reviews": 0.0, "avg_price": 0.0, "top10_items": items}
        return {
            "product_count": int(product_count),
            "avg_reviews": round(sum(reviews) / len(reviews), 2),
            "avg_price": round(sum(prices) / len(prices), 2),
            "top10_items": items,
        }

    def _default_result(self) -> Dict[str, Any]:
        return {
            "product_count": 0,
            "avg_reviews": 0.0,
            "avg_price": 0.0,
            "top10_items": [],
            "reason_code": "NO_RESULT",
        }

    def _result_with_reason(self, reason_code: str) -> Dict[str, Any]:
        one = self._default_result()
        one["reason_code"] = reason_code
        return one

    def _build_search_url(self, keyword: str) -> str:
        trace = f"bo{int(time.time())}{random.randint(100, 999)}"
        return (
            f"https://www.coupang.com/np/search?component=&q={quote(keyword)}"
            f"&traceId={trace}&channel=user"
        )

    def _is_blocked(self, html: str, title: str = "") -> bool:
        text = f"{title}\n{html}".lower()
        blocked_signals = [
            "access denied",
            "not a robot",
            "are you a robot",
            "automated queries",
            "unusual traffic",
            "captcha",
            "서비스 이용에 불편",
            "비정상적인 접근",
            "요청이 차단",
            "접근이 차단",
        ]
        return any(sig in text for sig in blocked_signals)

    @staticmethod
    def _organic_rank_from_rank_mark_li(li: Any) -> Optional[int]:
        """
        카드(li) 안쪽 말단의 RankMark `<span class="RankMark_rank{N}__...">N</span>` 에서 순위를 읽는다.
        링크 쿼리의 rank=/searchRank= 값과 불일치할 수 있어 RankMark를 우선한다.
        """
        for el in li.select("[class*='RankMark_rank']"):
            classes = el.get("class") or []
            if isinstance(classes, str):
                classes = classes.split()
            for cl in classes:
                if not isinstance(cl, str):
                    continue
                m = re.search(r"RankMark_rank(\d+)", cl)
                if m:
                    try:
                        r = int(m.group(1))
                        if 1 <= r <= 10:
                            return r
                    except ValueError:
                        continue
            try:
                txt = el.get_text(strip=True)
                if txt.isdigit():
                    r = int(txt)
                    if 1 <= r <= 10:
                        return r
            except Exception:
                continue
        return None

    def _extract_product_fields_from_li(self, li: Any) -> Optional[Dict[str, Any]]:
        """단일 상품 카드(li)에서 파싱 공통 필드 추출. 실패 시 None."""
        title_node = li.select_one(".ProductUnit_productNameV2__cV9cw, .name")
        price_raw = self._pick_price_won_from_li(li)
        review_count_node = li.select_one(
            ".ProductRating_productRating__jjf7W [class*='fw-text-'], "
            ".rating-total-count, .rating-count, .count"
        )
        review_score_node = li.select_one(
            ".ProductRating_productRating__jjf7W [aria-label], "
            ".ProductRating_productRating__jjf7W em, "
            ".ProductRating_productRating__jjf7W strong, "
            ".ProductRating_productRating__jjf7W [class*='rating'], "
            ".star .rating"
        )
        link_node = (
            li.select_one("a[href*='vp/products']")
            or li.select_one("a[href*='/products/']")
            or li.select_one("a[href*='www.coupang.com/vp/']")
            or li.select_one("a[href^='/vp/products']")
            or li.select_one("a[href]")
        )

        title = title_node.get_text(strip=True) if title_node else ""
        review_count_raw = review_count_node.get_text(strip=True) if review_count_node else ""
        review_score_raw = ""
        if review_score_node is not None:
            review_score_raw = str(
                review_score_node.get("aria-label", "") or review_score_node.get_text(strip=True) or ""
            )
        shipping_fee_raw = self._pick_shipping_from_li(li)
        delivery_type = self._extract_delivery_type_from_badges(li)
        image_url = self._pick_image_url_from_li(li)
        price_num = self._parse_int(price_raw)
        review_num = self._parse_int(self._normalize_review_count_display(review_count_raw))
        review_score = self._parse_float(review_score_raw)
        url = ""
        if link_node is not None:
            href = str(link_node.get("href", "")).strip()
            if href.startswith("http"):
                url = href
            elif href.startswith("/"):
                url = f"https://www.coupang.com{href}"

        if not title or price_num is None:
            return None
        return {
            "title": title,
            "price": float(price_num),
            "review_count": float(review_num) if review_num is not None else None,
            "review_score": float(review_score) if review_score is not None else None,
            "delivery_type": delivery_type or None,
            "shipping_fee": shipping_fee_raw or None,
            "url": url,
            "image_url": image_url,
        }

    def _li_is_ad_card(self, li: Any) -> bool:
        is_ad = bool(
            li.select_one(
                ".search-product__ad-badge, .search-product__ad, .ad-badge-text, "
                "[data-badge-type='ad'], [class*='AdMark'], [class*='adBadge']"
            )
        )
        if not is_ad:
            li_text = li.get_text(" ", strip=True)
            has_rank_mark = li.select_one("[class*='RankMark_rank']") is not None
            if "광고" in li_text and not has_rank_mark:
                is_ad = True
        return bool(is_ad)

    def _parse_top10_from_html(self, html: str) -> tuple[int, List[Dict[str, Any]]]:
        parser = "lxml"
        try:
            soup = BeautifulSoup(html, parser)
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        products = soup.select(_PRODUCT_CARD_HTML_SELECTOR)
        items: List[Dict[str, Any]] = []

        # 1) RankMark_rank{N}__ 기준으로 1~10위만 명시적으로 매칭 (광고 제외)
        by_rank: Dict[int, Dict[str, Any]] = {}
        for li in products:
            rk = self._organic_rank_from_rank_mark_li(li)
            if rk is None:
                continue
            if self._li_is_ad_card(li):
                continue
            fields = self._extract_product_fields_from_li(li)
            if fields is None:
                continue
            if rk not in by_rank:
                by_rank[rk] = {"rank": rk, **fields}

        if by_rank:
            for r in range(1, 11):
                if r in by_rank:
                    items.append(by_rank[r])
            return len(products), items

        # 2) RankMark 없는 레이아웃 폴백: 비광고 카드 순서대로 1..10 부여
        rank_no = 0
        for li in products:
            if self._li_is_ad_card(li):
                continue
            fields = self._extract_product_fields_from_li(li)
            if fields is None:
                continue
            rank_no += 1
            items.append({"rank": rank_no, **fields})
            if len(items) >= 10:
                break
        return len(products), items

    def get_cached_result(self, keyword: str) -> Optional[Dict[str, Any]]:
        key = str(keyword or "").strip()
        if not key:
            return None
        one = self._last_success_cache.get(key)
        return dict(one) if one is not None else None

    def _get_page(
        self, force_headless: Optional[bool] = None, *, prep_profile: bool = False
    ) -> Optional[Page]:
        if self._page is not None:
            return self._page
        try:
            self._sanitize_playwright_browser_env()
            self._log_playwright_preflight()
            _ensure_windows_proactor_policy()
            use_headless = self._headless if force_headless is None else bool(force_headless)
            primary_user_data_dir = self._prep_user_data_dir if prep_profile else self._chrome_user_data_dir
            user_data_dirs = [primary_user_data_dir, self._fallback_profile_dir(prep_profile)]
            self._playwright = sync_playwright().start()
            # --- launch_persistent_context 의 channel (브라우저 바이너리 선택) ---
            # 미설정(None): playwright install 로 받은 번들 Chromium — 서버·Docker·CI에 시스템 Chrome이 없어도 동일 동작.
            # 설정 시: OS에 깔린 브라우저를 씀. 예) chrome, msedge (Playwright 문서의 channel 값과 동일).
            # 기본을 번들로 둔 이유: 환경마다 설치 유무·버전이 달라져 오차가 나기 쉽기 때문. 필요할 때만 env로 전환.
            _channel = str(os.environ.get("COUPANG_PLAYWRIGHT_CHANNEL", "")).strip() or None
            last_error: Optional[Exception] = None
            for idx, user_data_dir in enumerate(user_data_dirs):
                try:
                    self._context = self._playwright.chromium.launch_persistent_context(
                        user_data_dir=user_data_dir,
                        headless=use_headless,
                        channel=_channel,
                        viewport={"width": 1440, "height": 2000},
                        locale="ko-KR",
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                        ),
                        extra_http_headers={
                            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                            "sec-ch-ua-mobile": "?0",
                            "sec-ch-ua-platform": '"Windows"',
                            "Referer": "https://www.google.com/"
                        },
                        args=[
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-gpu",
                            "--disable-blink-features=AutomationControlled",
                            "--disable-infobars",
                            "--window-size=1440,2000",
                            "--start-maximized",
                            f"--profile-directory={self._chrome_profile}",
                        ],
                    )
                    break
                except Error as e:
                    last_error = e
                    if idx == 0 and ("ProcessSingleton" in str(e) or "profile is already in use" in str(e)):
                        safe_print("[WARN] profile in use 감지 — fallback 프로필로 재시도합니다.")
                        continue
                    raise
            if self._context is None and last_error is not None:
                raise last_error
            page = self._context.new_page()

            # [USER_CUSTOM_STUFF]
            if STEALTH_AVAILABLE:
                safe_print("[INFO] Stealth 모드 활성화: 탐지 우회 적용 중...")
                apply_stealth(page)
            elif _STEALTH_PKG_PRESENT:
                safe_print(
                    "[WARN] playwright_stealth는 설치되어 있으나 stealth_sync API를 사용할 수 없습니다. "
                    "기본 모드로 실행합니다."
                )
            else:
                safe_print("[WARN] playwright_stealth 미설치: 기본 모드로 실행합니다. (차단 위험 높음)")

            # 공통 스크립트 주입 (라이브러리 없이도 가능한 우회)
            page.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                """
            )
            page.set_default_timeout(15000)
            self._page = page
            self._last_error = {}
            return self._page
        except Error as e:
            safe_print(f"[Crawler Error] keyword=PLAYWRIGHT_INIT, error={e}")
            self._last_error = {
                "code": "PLAYWRIGHT_INIT_FAILED",
                "message": str(e),
            }
            return None
        except Exception as e:
            safe_print(f"[Crawler Error] keyword=PLAYWRIGHT_INIT_UNEXPECTED, error={e!r}")
            self._last_error = {
                "code": "PLAYWRIGHT_INIT_UNEXPECTED",
                "message": repr(e),
            }
            return None

    def open_home_ready_session(self, wait_seconds: int = 120) -> bool:
        with self._io_lock:
            if self._page is not None:
                self.close()
            page = self._get_page(force_headless=self._prep_force_headless(), prep_profile=True)
            if page is None:
                return False
            try:
                page.goto("https://www.coupang.com", wait_until="domcontentloaded")
                if self._is_blocked(page.content(), page.title()):
                    safe_print("[WAF_BLOCK] 쿠팡 접속이 차단되었습니다. (Access Denied/CAPTCHA)")
                    self._stats["blocked"] += 1
                    return False
                page.wait_for_selector("input[name='q'], input[placeholder*='검색']", timeout=15000)
                safe_print("[Ready] 쿠팡 홈 접속 완료. 검색창 입력 가능 상태입니다.")
                safe_print("[Ready] 이 창에서 직접 키워드를 입력해 주세요.")
                safe_print(f"[Ready] 대기시간: {wait_seconds}초")
                time.sleep(max(10, int(wait_seconds)))
                return True
            except Exception as e:
                safe_print(f"[Crawler Error] keyword=OPEN_HOME_READY, error={e!r}")
                return False
            finally:
                self.close()

    def _simulate_human_actions(self, page: Page) -> None:
        try:
            page.wait_for_timeout(random.randint(500, 1200))
            page.mouse.move(random.randint(200, 700), random.randint(200, 550), steps=random.randint(10, 30))
            page.wait_for_timeout(random.randint(300, 800))
            page.mouse.wheel(0, random.randint(500, 1200))
            page.wait_for_timeout(random.randint(400, 900))
            page.mouse.wheel(0, random.randint(-250, 100))
            page.wait_for_timeout(random.randint(300, 700))
        except Exception:
            return

    @staticmethod
    def _human_sleep(min_seconds: float = 0.25, max_seconds: float = 0.9) -> None:
        try:
            lo = float(min_seconds)
            hi = float(max_seconds)
            if hi < lo:
                lo, hi = hi, lo
            time.sleep(random.uniform(max(0.05, lo), max(0.05, hi)))
        except Exception:
            time.sleep(0.25)

    @staticmethod
    def _fill_search_field(locator: Any, query: str) -> None:
        """IME 한자 깨짐 방지: keyboard.type 대신 fill."""
        q = str(query or "").strip()
        locator.click(timeout=5000)
        try:
            locator.fill("")
        except Exception:
            pass
        if q:
            locator.fill(q)

    @staticmethod
    def _smoke_rank1_detail_enabled() -> bool:
        return str(os.environ.get("COUPANG_SMOKE_RANK1_DETAIL", "1")).strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }

    def _smoke_detail_limit(self) -> int:
        raw = str(os.environ.get("COUPANG_SMOKE_DETAIL_LIMIT", "5") or "5").strip()
        try:
            return max(0, min(10, int(raw)))
        except ValueError:
            return 5

    def _smoke_review_count_from_row(self, row: Dict[str, Any]) -> int:
        raw = str(row.get("review_count") or "").strip()
        if not raw:
            return 0
        parsed = self._parse_int(self._normalize_review_count_display(raw))
        return int(parsed) if parsed is not None else 0

    def _smoke_select_detail_targets(
        self, ranked_rows: List[Tuple[int, Dict[str, Any]]]
    ) -> List[Tuple[int, Dict[str, Any]]]:
        """1~10위 중 리뷰수 상위 N개만 상세 수집."""
        limit = self._smoke_detail_limit()
        if limit <= 0:
            return []
        ordered = sorted(
            ranked_rows,
            key=lambda pair: (-self._smoke_review_count_from_row(pair[1]), pair[0]),
        )
        return ordered[:limit]

    def _parse_monthly_sales_from_html(self, html: str) -> str:
        fast = _parse_monthly_sales_from_html_fast(html)
        if fast:
            return fast
        for text in _extract_purchase_proof_lines_from_html(html):
            parsed = normalize_monthly_sales_display(text)
            if parsed:
                return parsed
        return ""

    def _parse_monthly_sales_from_cached_html(self, html: str) -> str:
        """상품 1건당 HTML 1번 — 사용자 ATF 구조 우선."""
        raw = str(html or "")
        if not raw:
            return ""
        parsed = _parse_user_atf_badge_html(raw)
        if parsed:
            return parsed
        fast = _parse_monthly_sales_from_html_fast(raw)
        if fast:
            return fast
        if "social_proof_purchase" in raw:
            anchor = raw.find("social_proof_purchase")
            fast = _parse_monthly_sales_from_html_fast(raw[max(0, anchor - 200) : anchor + 2000])
            if fast:
                return fast
        for text in _extract_purchase_proof_lines_from_html(raw):
            parsed = normalize_monthly_sales_display(text)
            if parsed:
                return parsed
        return ""

    def _prepare_smoke_detail_page(self, page: Page) -> None:
        """상세 진입 직후 최소 대기 — 파싱 실패 시에만 추가 재시도."""
        try:
            page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        if _smoke_detail_use_network_idle():
            try:
                page.wait_for_load_state(
                    "networkidle",
                    timeout=min(_smoke_detail_badge_wait_ms(), 5000),
                )
            except Exception:
                pass
        elif _smoke_detail_fast_mode():
            try:
                page.wait_for_load_state("load", timeout=3500)
            except Exception:
                pass
            page.wait_for_timeout(150)
        else:
            try:
                page.wait_for_load_state("load", timeout=8000)
            except Exception:
                pass

    def _extract_monthly_sales_from_detail_snapshot(
        self, page: Page, html: str
    ) -> str:
        """DOM + HTML 한 번에 파싱. 이미 'N개' 형식이면 normalize 통과."""
        sales = self._try_parse_monthly_sales_on_detail_page(page, html=html)
        if not sales:
            sales = self._parse_monthly_sales_from_cached_html(html)
        if not sales or sales == "0개":
            return ""
        parsed = normalize_monthly_sales_display(sales, default_zero=False)
        return parsed if parsed and parsed != "0개" else ""

    def _try_parse_monthly_sales_on_detail_page(self, page: Page, *, html: str = "") -> str:
        """DOM 전역 스캔 + HTML 파싱."""
        try:
            text = page.evaluate(_DOM_PURCHASE_PROOF_JS)
            parsed = normalize_monthly_sales_display(str(text or ""))
            if parsed and parsed != "0개":
                return parsed
        except Exception:
            pass

        if html:
            return self._parse_monthly_sales_from_cached_html(html)
        return ""

    def _read_monthly_sales_from_detail_page(self, page: Page) -> str:
        """상세 1건: 즉시 HTML/DOM 파싱 → 실패 시에만 짧은 재시도."""
        self._prepare_smoke_detail_page(page)

        html = page.content()
        sales = self._extract_monthly_sales_from_detail_snapshot(page, html)
        if sales:
            return sales

        badge_ms = _smoke_detail_badge_wait_ms()
        retry_ms = _smoke_detail_retry_wait_ms()
        attempts = max(0, _smoke_detail_parse_attempts() - 1)
        for _ in range(attempts):
            try:
                page.locator('img[src*="social_proof_purchase"]').first.wait_for(
                    state="attached",
                    timeout=min(1200, badge_ms // 2),
                )
            except Exception:
                page.wait_for_timeout(retry_ms)
            html = page.content()
            sales = self._extract_monthly_sales_from_detail_snapshot(page, html)
            if sales:
                return sales

        if not _smoke_detail_fast_mode():
            for selector in (
                'img[src*="social_proof_purchase"]',
                'text=/한\\s*달간[\\s\\d,]*명.*구매했어요/',
            ):
                try:
                    page.locator(selector).first.wait_for(
                        state="visible", timeout=badge_ms
                    )
                    html = page.content()
                    sales = self._extract_monthly_sales_from_detail_snapshot(page, html)
                    if sales:
                        return sales
                except Exception:
                    continue
        return ""

    def _attach_smoke_detail_network_tap(self, page: Page) -> List[Dict[str, Any]]:
        """상세 로딩 중 구매실적 관련 JSON 응답 후보를 수집 (디버그용)."""
        hits: List[Dict[str, Any]] = []
        keywords = (
            "social",
            "proof",
            "purchase",
            "구매",
            "sdp",
            "atf",
            "monthly",
            "sales",
        )

        def _on_response(response: Any) -> None:
            if len(hits) >= 24:
                return
            try:
                url = str(response.url or "")
                lower = url.lower()
                if "coupang" not in lower and "coupangcdn" not in lower:
                    return
                ctype = str(response.headers.get("content-type") or "").lower()
                if "json" not in ctype and "javascript" not in ctype and "text" not in ctype:
                    return
                if int(response.status) >= 400:
                    return
                body = response.text()
                if not body or len(body) < 40:
                    return
                blob = body[:12000]
                if not any(k in blob.lower() or k in lower for k in keywords):
                    return
                hits.append(
                    {
                        "url": url[:500],
                        "status": int(response.status),
                        "content_type": ctype[:120],
                        "body_preview": blob,
                    }
                )
            except Exception:
                return

        try:
            page.on("response", _on_response)
        except Exception:
            pass
        return hits

    def _dump_smoke_detail_debug(
        self,
        page: Page,
        *,
        rank: int,
        product_id: str,
        keyword: str,
        html: str,
        parsed_sales: str,
        signals: Dict[str, Any],
        network_hits: Optional[List[Dict[str, Any]]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[Path]:
        """판매량 미수집·디버그 모드 시 HTML/스크린샷/메타 저장."""
        try:
            out_dir = _smoke_detail_debug_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            kw_slug = re.sub(r"[^\w가-힣]+", "_", str(keyword or "").strip()).strip("_")[:40]
            stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
            base = f"rank{rank}_pid{product_id or 'na'}"
            if kw_slug:
                base = f"{kw_slug}_{base}"
            base = f"{base}_{stamp}"

            html_path = out_dir / f"{base}.html"
            png_path = out_dir / f"{base}.png"
            meta_path = out_dir / f"{base}.json"

            html_path.write_text(str(html or ""), encoding="utf-8")
            try:
                page.screenshot(path=str(png_path), full_page=False)
            except Exception as ss_ex:
                png_path = None
                ss_err = repr(ss_ex)
            else:
                ss_err = ""

            meta = {
                "saved_at": datetime.now().isoformat(timespec="seconds"),
                "rank": rank,
                "product_id": product_id,
                "keyword": keyword,
                "parsed_sales": parsed_sales,
                "body_len": len(str(html or "")),
                "signals": signals,
                "network_hit_count": len(network_hits or []),
                "network_hits": list(network_hits or [])[:12],
                "html_path": str(html_path),
                "png_path": str(png_path) if png_path else "",
                "screenshot_error": ss_err,
            }
            if extra:
                meta.update(extra)
            meta_path.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            safe_print(
                f"[SMOKE][detail][debug] rank={rank} saved html={html_path.name} "
                f"meta={meta_path.name}"
                + (f" png={png_path.name}" if png_path else " png=skip")
            )
            return out_dir
        except Exception as ex:
            safe_print(f"[SMOKE][detail][debug] dump failed rank={rank}: {ex!r}")
            return None

    @staticmethod
    def _finalize_smoke_detail_result(debug: Dict[str, Any], *, parsed_sales: str) -> Dict[str, Any]:
        """파싱 실패 시 실패 사인(error_code·False·0개) 없이 빈 값만 둔다."""
        out = dict(debug)
        sales = str(parsed_sales or "").strip()
        if sales == "0개":
            sales = ""
        out["monthly_sales"] = sales
        if sales:
            out["detail_fetch_ok"] = True
        else:
            out.pop("detail_fetch_ok", None)
        for key in ("error_code", "message", "sales_proof_candidates", "stage"):
            out.pop(key, None)
        return out

    def _smoke_fetch_product_sales_in_new_tab(
        self,
        serp_page: Page,
        row: Dict[str, Any],
        *,
        rank: int,
        serp_url: str,
        keyword: str = "",
    ) -> Dict[str, Any]:
        """SERP는 유지한 채 상세만 새 탭에서 열고·수집 후 탭 닫기."""
        debug: Dict[str, Any] = {
            "method": "smoke_detail_new_tab",
            "rank": rank,
            "monthly_sales": "",
        }
        target_url = self._absolutize_coupang_url(str(row.get("url") or "").strip())
        product_id = self._extract_product_id_from_url(target_url)
        debug["product_id"] = product_id
        debug["url"] = target_url
        kw = str(keyword or os.environ.get("COUPANG_SMOKE_COUPANG_QUERY") or "").strip()
        if not target_url:
            return self._finalize_smoke_detail_result(debug, parsed_sales="")

        safe_print(f"[SMOKE][detail] rank={rank} new tab open product_id={product_id}")
        detail_page: Optional[Page] = None
        network_hits: List[Dict[str, Any]] = []
        blocked = False
        html = ""
        try:
            detail_page = serp_page.context.new_page()
            if _smoke_detail_debug_mode() != "off":
                network_hits = self._attach_smoke_detail_network_tap(detail_page)
            referer = str(serp_url or serp_page.url or "https://www.coupang.com/").strip()
            detail_page.goto(
                target_url,
                wait_until=_smoke_detail_goto_wait_until(),
                referer=referer,
                timeout=_smoke_detail_goto_timeout_ms(),
            )
            sales = self._read_monthly_sales_from_detail_page(detail_page)
            html = detail_page.content()
            if not sales:
                sales = self._extract_monthly_sales_from_detail_snapshot(
                    detail_page, html
                )
            title = (detail_page.title() or "")[:120]
            debug["page_title"] = title
            debug["body_len"] = len(str(html or ""))
            if self._is_blocked(html, title):
                blocked = True
                safe_print(f"[SMOKE][detail] rank={rank} blocked title={title!r}")
                parsed = ""
            else:
                parsed = normalize_monthly_sales_display(sales, default_zero=False)
                if not parsed and html:
                    fallback = _parse_monthly_sales_from_html_fast(html)
                    if fallback:
                        parsed = normalize_monthly_sales_display(
                            fallback, default_zero=False
                        )
            signals = _html_purchase_signals(html)
            if not parsed and not blocked:
                safe_print(
                    f"[SMOKE][detail] rank={rank} parse_miss "
                    f"body_len={debug.get('body_len')} "
                    f"has_badge_img={signals.get('has_badge_img')} "
                    f"has_purchase_text={signals.get('has_purchase_text')} "
                    f"has_handal={signals.get('has_handal')} "
                    f"fast_preview={signals.get('fast_parse_preview')!r}"
                )
            if _should_dump_smoke_detail_debug(
                parsed_sales=parsed, blocked=blocked, error=False
            ):
                self._dump_smoke_detail_debug(
                    detail_page,
                    rank=rank,
                    product_id=product_id,
                    keyword=kw,
                    html=html,
                    parsed_sales=parsed,
                    signals=signals,
                    network_hits=network_hits,
                    extra={"url": target_url, "blocked": blocked},
                )
            safe_print(
                f"[SMOKE][detail] rank={rank} tab close sales={parsed!r}"
            )
            return self._finalize_smoke_detail_result(debug, parsed_sales=parsed)
        except TimeoutError:
            had_error = True
            safe_print(f"[SMOKE][detail] rank={rank} new tab timeout")
            if detail_page is not None and _should_dump_smoke_detail_debug(
                parsed_sales="", blocked=False, error=True
            ):
                try:
                    html = detail_page.content()
                except Exception:
                    html = ""
                self._dump_smoke_detail_debug(
                    detail_page,
                    rank=rank,
                    product_id=product_id,
                    keyword=kw,
                    html=html,
                    parsed_sales="",
                    signals=_html_purchase_signals(html),
                    network_hits=network_hits,
                    extra={"url": target_url, "error": "timeout"},
                )
            return self._finalize_smoke_detail_result(debug, parsed_sales="")
        except Exception as exc:
            had_error = True
            safe_print(f"[SMOKE][detail] rank={rank} new tab error={type(exc).__name__}")
            if detail_page is not None and _should_dump_smoke_detail_debug(
                parsed_sales="", blocked=False, error=True
            ):
                try:
                    html = detail_page.content()
                except Exception:
                    html = ""
                self._dump_smoke_detail_debug(
                    detail_page,
                    rank=rank,
                    product_id=product_id,
                    keyword=kw,
                    html=html,
                    parsed_sales="",
                    signals=_html_purchase_signals(html),
                    network_hits=network_hits,
                    extra={"url": target_url, "error": type(exc).__name__},
                )
            return self._finalize_smoke_detail_result(debug, parsed_sales="")
        finally:
            if detail_page is not None:
                try:
                    detail_page.close()
                except Exception:
                    pass

    def _smoke_fetch_topn_sales(
        self, page: Page, probe: Dict[str, Any], *, keyword: str = ""
    ) -> Dict[str, Any]:
        """smoke SERP 유지 · 1~10위 중 리뷰 상위 N개만 상세 탭 수집."""
        limit = self._smoke_detail_limit()
        bundle: Dict[str, Any] = {
            "detail_limit": limit,
            "detail_pick_mode": "top_reviews",
            "items": [],
            "serp_url": str(probe.get("url") or "").strip(),
        }
        if not self._smoke_rank1_detail_enabled() or limit <= 0:
            bundle["error_code"] = "DISABLED"
            return bundle

        serp_url = str(bundle.get("serp_url") or page.url or "").strip()
        ranked_rows: List[Tuple[int, Dict[str, Any]]] = []
        for row in list(probe.get("top10") or []):
            if not isinstance(row, dict):
                continue
            try:
                rank_no = int(row.get("rank") or 0)
            except Exception:
                continue
            if 1 <= rank_no <= 10:
                ranked_rows.append((rank_no, row))

        ordered_targets = sorted(
            ranked_rows,
            key=lambda pair: (-self._smoke_review_count_from_row(pair[1]), pair[0]),
        )
        target_ranks = [rank for rank, _ in ordered_targets[:limit]]
        bundle["target_ranks"] = target_ranks

        self._smoke_status_update(
            phase="smoke_topn_detail",
            hint=f"SERP 유지 · 리뷰순 상세 탭 (판매량 없으면 다음 상품)",
        )
        safe_print(
            f"[SMOKE][detail] top-reviews goal={limit} serp_candidates={len(ordered_targets)}"
        )

        detail_kw = str(
            keyword or probe.get("keyword") or os.environ.get("COUPANG_SMOKE_COUPANG_QUERY") or ""
        ).strip()
        detail_items: List[Dict[str, Any]] = []
        saved_with_sales = 0
        for rank_no, row in ordered_targets:
            if saved_with_sales >= limit:
                break
            result = self._smoke_fetch_product_sales_in_new_tab(
                page, row, rank=rank_no, serp_url=serp_url, keyword=detail_kw
            )
            parsed = normalize_monthly_sales_display(
                str(result.get("monthly_sales") or ""),
                default_zero=False,
            )
            row["monthly_sales"] = (
                parsed if parsed and parsed != "0개" else ""
            )
            if row["monthly_sales"]:
                row["detail_fetch_ok"] = True
                saved_with_sales += 1
            else:
                row.pop("detail_fetch_ok", None)
                safe_print(
                    f"[SMOKE][detail] rank={rank_no} 판매량 없음 — 다음 상품 시도"
                )
            row["detail_target"] = True
            detail_items.append(
                self._finalize_smoke_detail_result(result, parsed_sales=parsed)
            )
            pause_lo, pause_hi = _smoke_detail_tab_pause_ms()
            page.wait_for_timeout(random.randint(pause_lo, pause_hi))

        bundle["items"] = detail_items
        bundle["completed_ranks"] = [
            int(it.get("rank") or 0)
            for it in detail_items
            if str(it.get("monthly_sales") or "").strip()
            and int(it.get("rank") or 0) > 0
        ]
        safe_print(f"[SMOKE][detail] top-reviews done completed={bundle['completed_ranks']}")
        return bundle

    def _linger_on_results_page(self, page: Page, *, passes: int = 2) -> None:
        """
        검색 결과 화면에서 즉시 파싱하지 않고 사람이 상품 목록을 훑는 듯한 짧은 체류를 만든다.
        """
        try:
            page.wait_for_timeout(random.randint(450, 1100))
            self._human_sleep(0.2, 0.7)
            for idx in range(max(1, int(passes))):
                try:
                    page.mouse.move(
                        random.randint(180, 1100),
                        random.randint(220, 900),
                        steps=random.randint(12, 35),
                    )
                    page.wait_for_timeout(random.randint(180, 520))
                    wheel_delta = random.randint(260, 980)
                    if idx % 3 == 2:
                        wheel_delta *= -1
                    page.mouse.wheel(0, wheel_delta)
                    page.wait_for_timeout(random.randint(280, 760))
                    self._human_sleep(0.18, 0.55)
                except Exception:
                    continue
        except Exception:
            return

    def _hover_random_product_cards(self, page: Page, *, attempts: int = 2) -> None:
        """
        일부 상품 카드 근처로 마우스를 옮겨 실제 사용자가 목록을 읽는 흐름을 흉내 낸다.
        """
        try:
            cards = page.locator(_PRODUCT_LIST_SELECTOR)
            count = min(cards.count(), 8)
            if count <= 0:
                return
            order = list(range(count))
            random.shuffle(order)
            for idx in order[: max(1, int(attempts))]:
                try:
                    card = cards.nth(idx)
                    box = card.bounding_box()
                    if not box:
                        continue
                    target_x = int(box["x"] + min(max(20, box["width"] * 0.35), max(24, box["width"] - 20)))
                    target_y = int(box["y"] + min(max(20, box["height"] * 0.3), max(24, box["height"] - 20)))
                    page.mouse.move(target_x, target_y, steps=random.randint(16, 42))
                    page.wait_for_timeout(random.randint(260, 900))
                    if random.random() < 0.45:
                        page.mouse.wheel(0, random.randint(120, 420))
                        page.wait_for_timeout(random.randint(160, 420))
                except Exception:
                    continue
        except Exception:
            return

    def _scroll_coupang_search_results_page(self, page: Page, *, max_wheel_batches: int = 14) -> None:
        """
        검색 결과 상품 카드가 지연 로드되므로 마우스 휠과 페이지 하단 스크롤로 DOM을 채운 뒤 1~10위 추출을 한다.
        스모크 probe와 동일한 패턴을 공유한다.
        """
        try:
            page.wait_for_timeout(random.randint(220, 520))
            for i in range(max(1, int(max_wheel_batches))):
                wheel_amount = random.randint(950, 1850)
                page.mouse.wheel(0, wheel_amount)
                page.wait_for_timeout(random.randint(170, 420))
                if i % 4 == 3:
                    try:
                        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(random.randint(260, 620))
                    except Exception:
                        pass
                if i in {1, 4, 7}:
                    self._hover_random_product_cards(page, attempts=1)
        except Exception as ex:
            safe_print(f"[Crawler] 검색 결과 스크롤 생략: {ex!r}")

    def _accept_google_consent_if_present(self, page: Page) -> None:
        """
        Google 첫 진입 시 뜨는 동의 팝업(모두 수락/Accept all)을 1회 수락 시도한다.
        팝업이 없거나 셀렉터가 바뀐 경우에도 흐름은 계속 진행한다.
        """
        try:
            # 동의 화면에서는 종종 consent.google.com 으로 리다이렉트되므로 짧게 대기
            page.wait_for_timeout(600)
            url_lower = str(page.url or "").lower()

            # 1) 메인 문서에서 직접 버튼 탐색
            candidates = [
                page.get_by_role("button", name=re.compile(r"모두\s*수락|동의하고\s*계속", re.I)).first,
                page.get_by_role("button", name=re.compile(r"accept\s*all|i\s*agree", re.I)).first,
                page.locator("button[aria-label*='모두 수락'], button[aria-label*='Accept all']").first,
                page.locator("form[action*='consent'] button, form[action*='consent'] input[type='submit']").first,
            ]
            for btn in candidates:
                try:
                    btn.wait_for(state="visible", timeout=1800)
                    btn.click(timeout=2500)
                    safe_print("[SMOKE] Google 동의 팝업 수락 완료(메인 문서)")
                    page.wait_for_timeout(500)
                    return
                except Exception:
                    continue

            # 2) iframe 내부 동의 버튼 탐색
            for fr in page.frames:
                f_url = str(fr.url or "").lower()
                if "consent" not in f_url and "google" not in f_url and "intro" not in f_url:
                    continue
                for sel in (
                    "button:has-text('모두 수락')",
                    "button:has-text('동의하고 계속')",
                    "button:has-text('Accept all')",
                    "button:has-text('I agree')",
                    "form[action*='consent'] button",
                    "form[action*='consent'] input[type='submit']",
                ):
                    try:
                        b = fr.locator(sel).first
                        if b.count() > 0:
                            b.click(timeout=2500)
                            safe_print("[SMOKE] Google 동의 팝업 수락 완료(iframe)")
                            page.wait_for_timeout(500)
                            return
                    except Exception:
                        continue

            # 동의 도메인인데 버튼을 못 찾았으면 흔적만 남김
            if "consent.google.com" in url_lower:
                safe_print("[SMOKE] Google 동의 화면 감지했으나 수락 버튼을 찾지 못했습니다.")
        except Exception as e:
            safe_print(f"[SMOKE] Google 동의 팝업 처리 중 예외(무시): {e!r}")

    @staticmethod
    def _search_engine_referer(keyword: str = "") -> str:
        kw = str(keyword or "").strip()
        if kw:
            return f"https://www.google.com/search?q={quote(kw)}"
        return "https://www.google.com/"

    @staticmethod
    def _google_nav_query_sequence(explicit: str = "") -> List[str]:
        s = str(explicit or "").strip()
        if s:
            return [s] if s == "쿠팡" else [s, "쿠팡"]
        primary = random.choice(STABLE_GOOGLE_NAV_QUERIES)
        return [primary] if primary == "쿠팡" else [primary, "쿠팡"]

    def _session_headers_from_page(self, page: Page) -> Dict[str, str]:
        try:
            ua = str(page.evaluate("() => navigator.userAgent"))
        except Exception:
            ua = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Referer": self._search_engine_referer(),
        }
        return headers

    def _requests_with_browser_session(self, page: Page, search_url: str) -> Optional[Dict[str, Any]]:
        if self._context is None:
            return None
        try:
            storage = self._context.storage_state()
            cookies = storage.get("cookies", []) if isinstance(storage, dict) else []
            jar = requests.cookies.RequestsCookieJar()
            for c in cookies:
                jar.set(
                    str(c.get("name", "")),
                    str(c.get("value", "")),
                    domain=str(c.get("domain", "")).lstrip("."),
                    path=str(c.get("path", "/")),
                )
            headers = self._session_headers_from_page(page)
            headers["Referer"] = self._search_engine_referer(
                dict(parse_qsl(urlparse(search_url).query, keep_blank_values=True)).get("q", "")
            )
            headers["Sec-Fetch-Site"] = "cross-site"
            parsed = urlparse(search_url)
            q = dict(parse_qsl(parsed.query, keep_blank_values=True))
            q["component"] = q.get("component", "")
            q["channel"] = q.get("channel", "user")
            req_url = urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    urlencode(q, doseq=True),
                    parsed.fragment,
                )
            )
            res = requests.get(req_url, headers=headers, cookies=jar, timeout=12, allow_redirects=True)
            if res.status_code != 200:
                safe_print(f"[Crawler][requests] status={res.status_code}")
                self._last_error = {
                    "code": f"REQUESTS_HTTP_{int(res.status_code)}",
                    "message": f"requests status={int(res.status_code)}",
                }
                return None
            if self._is_blocked(res.text, ""):
                safe_print("[WAF_BLOCK][requests] blocked signal detected in requests parsing")
                self._stats["blocked"] += 1
                self._last_error = {
                    "code": "REQUESTS_BLOCKED_BY_WAF",
                    "message": "blocked signal detected in requests response",
                }
                return None
            product_count, items = self._parse_top10_from_html(res.text)
            safe_print(f"[Crawler][requests] parsed product_count={product_count} top10_items={len(items)}")
            if product_count <= 0:
                self._last_error = {
                    "code": "REQUESTS_NO_PRODUCTS",
                    "message": "requests parse returned zero products",
                }
                return None
            self._last_fetch_source = "requests"
            return self._build_result(product_count, items)
        except Exception as e:
            safe_print(f"[Crawler Error] keyword=REQUESTS_SESSION, error={e!r}")
            self._last_error = {
                "code": "REQUESTS_EXCEPTION",
                "message": repr(e),
            }
            return None

    def _requests_html_with_browser_session(
        self, page: Page, target_url: str, *, referer: str = ""
    ) -> Optional[str]:
        if self._context is None:
            return None
        try:
            storage = self._context.storage_state()
            cookies = storage.get("cookies", []) if isinstance(storage, dict) else []
            jar = requests.cookies.RequestsCookieJar()
            for c in cookies:
                jar.set(
                    str(c.get("name", "")),
                    str(c.get("value", "")),
                    domain=str(c.get("domain", "")).lstrip("."),
                    path=str(c.get("path", "/")),
                )
            headers = self._session_headers_from_page(page)
            ref = str(referer or page.url or "https://www.coupang.com/").strip()
            headers["Referer"] = ref
            headers["Sec-Fetch-Site"] = "same-origin" if "coupang.com" in ref.lower() else "none"
            res = requests.get(target_url, headers=headers, cookies=jar, timeout=15, allow_redirects=True)
            text = (res.text or "").strip()
            content_type = str(res.headers.get("content-type", "") or "").strip()
            preview = re.sub(r"\s+", " ", text[:300]).strip()
            self._last_detail_fetch_debug = {
                "method": "requests_browser_session",
                "url": str(target_url or "").strip(),
                "referer": ref,
                "status_code": int(res.status_code),
                "content_type": content_type,
                "body_len": len(text),
                "preview": preview,
            }
            if res.status_code != 200:
                self._last_detail_fetch_debug["error_code"] = f"HTTP_{int(res.status_code)}"
                safe_print(
                    f"[DETAIL][requests] status={res.status_code} url={target_url} "
                    f"content_type={content_type or '-'} body_len={len(text)} preview={preview[:120]}"
                )
                return None
            if not text:
                self._last_detail_fetch_debug["error_code"] = "EMPTY_BODY"
                safe_print(f"[DETAIL][requests] empty body url={target_url}")
                return None
            if self._is_blocked(text, ""):
                self._last_detail_fetch_debug["error_code"] = "BLOCKED_HTML"
                safe_print(f"[DETAIL][requests] blocked-like html url={target_url}")
                return None
            if "<" not in text:
                self._last_detail_fetch_debug["error_code"] = "NON_HTML_BODY"
                safe_print(
                    f"[DETAIL][requests] non-html url={target_url} "
                    f"content_type={content_type or '-'} body_len={len(text)} preview={preview[:120]}"
                )
                return None
            self._last_detail_fetch_debug["stage"] = "html_ok"
            return text
        except Exception as e:
            self._last_detail_fetch_debug = {
                "method": "requests_browser_session",
                "url": str(target_url or "").strip(),
                "referer": str(referer or page.url or "").strip(),
                "error_code": type(e).__name__,
                "message": repr(e),
            }
            safe_print(f"[DETAIL][requests] exception url={target_url} error={type(e).__name__}")
            return None

    def _find_search_result_anchor(
        self,
        page: Page,
        *,
        product_id: str,
        target_url: str,
    ) -> Optional[Any]:
        target_abs = self._absolutize_coupang_url(target_url)
        target_item_id = ""
        try:
            target_item_id = str(dict(parse_qsl(urlparse(target_abs).query, keep_blank_values=True)).get("itemId", "") or "")
        except Exception:
            target_item_id = ""

        selectors = (
            "a[href*='vp/products']",
            "a[href*='/products/']",
            "a[href*='www.coupang.com/vp/']",
        )
        handles: List[Any] = []
        for selector in selectors:
            try:
                handles.extend(page.query_selector_all(selector))
            except Exception:
                continue

        for handle in handles:
            try:
                href = self._absolutize_coupang_url(str(handle.get_attribute("href") or "").strip())
            except Exception:
                continue
            if not href:
                continue
            if product_id and product_id != self._extract_product_id_from_url(href):
                continue
            if target_item_id:
                try:
                    item_id = str(dict(parse_qsl(urlparse(href).query, keep_blank_values=True)).get("itemId", "") or "")
                except Exception:
                    item_id = ""
                if item_id and item_id != target_item_id:
                    continue
            return handle
        return None

    def _restore_search_results_page(self, page: Page, search_url: str) -> None:
        try:
            page.go_back(wait_until="domcontentloaded")
            page.wait_for_selector(_PRODUCT_LIST_SELECTOR, timeout=10000)
            page.wait_for_timeout(random.randint(500, 900))
            return
        except Exception:
            pass
        page.goto(
            search_url,
            wait_until="domcontentloaded",
            referer=self._search_engine_referer(
                dict(parse_qsl(urlparse(search_url).query, keep_blank_values=True)).get("q", "")
            ),
        )
        page.wait_for_selector(_PRODUCT_LIST_SELECTOR, timeout=10000)
        page.wait_for_timeout(random.randint(700, 1200))
        self._scroll_coupang_search_results_page(page, max_wheel_batches=8)

    def _open_search_results_page_via_ui(self, page: Page, keyword: str) -> str:
        kw = str(keyword or "").strip()
        page.goto(
            "https://www.coupang.com",
            wait_until="domcontentloaded",
            referer=self._search_engine_referer(kw),
        )
        if self._is_blocked(page.content(), page.title()):
            raise RuntimeError("BLOCKED_HOME")

        search_input = page.locator("input[name='q'], input[placeholder*='검색']").first
        search_input.wait_for(state="visible", timeout=15000)
        page.wait_for_timeout(random.randint(500, 1100))
        self._simulate_human_actions(page)
        search_input.click(timeout=3000)
        page.wait_for_timeout(random.randint(250, 700))
        try:
            search_input.fill("")
        except Exception:
            pass

        for ch in kw:
            page.keyboard.type(ch, delay=random.randint(60, 160))
        page.wait_for_timeout(random.randint(250, 600))
        with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
            page.keyboard.press("Enter")

        page.wait_for_selector(_PRODUCT_LIST_SELECTOR, timeout=15000)
        page.wait_for_timeout(random.randint(800, 1400))
        self._scroll_coupang_search_results_page(page, max_wheel_batches=10)
        return str(page.url or "").strip()

    def _open_search_results_via_google(self, page: Page, keyword: str) -> str:
        kw = str(keyword or "").strip()
        if not kw:
            raise RuntimeError("EMPTY_KEYWORD")
        explicit_google_query = str(os.environ.get("COUPANG_SMOKE_GOOGLE_QUERY") or "").strip()
        google_queries = self._google_nav_query_sequence(explicit_google_query)
        last_err: Optional[Exception] = None

        for attempt_i, google_query in enumerate(google_queries):
            if attempt_i == 0:
                page.goto("https://www.google.com/ncr", wait_until="domcontentloaded")
            else:
                safe_print(f"[Crawler][playwright] google nav retry query={google_query!r}")
                page.goto("https://www.google.com/", wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(400)

            self._accept_google_consent_if_present(page)
            self._human_sleep(0.25, 0.7)
            try:
                search_box = page.locator("textarea[name='q'], input[name='q']:not([type='hidden'])").first
                search_box.wait_for(state="visible", timeout=15000)
                search_box.click(timeout=5000)
                page.wait_for_timeout(250)
                try:
                    search_box.fill("")
                except Exception:
                    pass
                page.keyboard.type(google_query, delay=100)
                page.wait_for_timeout(400)
                page.keyboard.press("Enter")
                try:
                    page.wait_for_url(re.compile(r"/search\?"), timeout=25000)
                except Exception:
                    safe_print("[Crawler][playwright] google wait_for_url timeout — continue")
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(1200)

                refresh_serp_raw = os.environ.get("COUPANG_SMOKE_REFRESH_SERP", "1")
                do_refresh_serp = str(refresh_serp_raw).strip().lower() not in {"0", "false", "no", "off", "n"}
                if do_refresh_serp:
                    try:
                        safe_print("[Crawler][playwright] Google SERP refresh 1회 수행")
                        page.reload(wait_until="domcontentloaded", timeout=25000)
                        page.wait_for_timeout(900)
                    except Exception as refresh_err:
                        safe_print(f"[Crawler][playwright] SERP refresh 실패(무시): {refresh_err!r}")

                self._linger_on_results_page(page, passes=random.randint(1, 2))

                coupang_locators = [
                    page.locator("a").filter(has_text=re.compile(r"https://www\.coupang\.com", re.I)).first,
                    page.locator('a[href*="www.coupang.com/np/search"]').first,
                    page.locator('a[href*="coupang.com/np/search"]').first,
                    page.locator('a[href^="https://www.coupang.com"]').first,
                    page.locator('a[href*="www.coupang.com"]').first,
                    page.locator('a[href*="coupang.com"]').first,
                ]

                clicked = False
                local_last_err: Optional[Exception] = None
                for loc in coupang_locators:
                    try:
                        loc.wait_for(state="visible", timeout=6000)
                        loc.scroll_into_view_if_needed(timeout=5000)
                        self._human_sleep(0.15, 0.5)
                        ctx = page.context
                        before_pages = len(ctx.pages)
                        loc.click(timeout=15000)
                        page.wait_for_timeout(350)
                        if len(ctx.pages) > before_pages:
                            page = ctx.pages[-1]
                            page.wait_for_load_state("domcontentloaded", timeout=25000)
                        else:
                            page.wait_for_url(re.compile(r"coupang\.com"), timeout=25000)
                            page.wait_for_load_state("domcontentloaded")
                        page.wait_for_timeout(600)
                        clicked = True
                        break
                    except Exception as ex:
                        local_last_err = ex
                        continue

                if not clicked:
                    raise RuntimeError(f"쿠팡 링크 클릭 실패: {local_last_err!r}")

                cur_url = str(page.url or "").strip()
                if "coupang.com/np/search" in cur_url:
                    page.wait_for_selector(_PRODUCT_LIST_SELECTOR, timeout=15000)
                    page.wait_for_timeout(random.randint(700, 1400))
                    self._scroll_coupang_search_results_page(page, max_wheel_batches=8)
                    return cur_url

                if "coupang.com" not in cur_url.lower():
                    raise RuntimeError("GOOGLE_TO_COUPANG_NAVIGATION_FAILED")

                return self._open_search_results_page_via_ui(page, kw)
            except Exception as ex:
                last_err = ex
                continue

        raise RuntimeError(f"쿠팡 링크 진입 실패(시도 {google_queries!r}): {last_err!r}") from last_err

    def fetch_detail_pages_via_search(
        self,
        keyword: str,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        kw = str(keyword or "").strip()
        if not kw:
            self._last_detail_fetch_debug = {
                "method": "search_click",
                "error_code": "EMPTY_KEYWORD",
            }
            return {}

        targets: Dict[str, Dict[str, Any]] = {}
        for item in items:
            url = self._absolutize_coupang_url(str(item.get("url") or item.get("product_url") or "").strip())
            product_id = self._extract_product_id_from_url(url)
            if not product_id or product_id in targets:
                continue
            targets[product_id] = {
                "product_id": product_id,
                "target_url": url,
            }
        if not targets:
            return {}

        results: Dict[str, Dict[str, Any]] = {}
        search_url = self._build_search_url(kw)
        with self._io_lock:
            page = self._get_page()
            if page is None:
                self._last_detail_fetch_debug = {
                    "method": "search_click",
                    "error_code": "PLAYWRIGHT_INIT_FAILED",
                    "search_url": search_url,
                }
                return {}

            try:
                search_url = self._open_search_results_page_via_ui(page, kw)
                if self._is_blocked(page.content(), page.title()):
                    self._last_detail_fetch_debug = {
                        "method": "search_click",
                        "error_code": "BLOCKED_SEARCH",
                        "search_url": search_url,
                        "page_title": (page.title() or "")[:120],
                    }
                    safe_print("[DETAIL][search_click] search page blocked")
                    return {}

                for product_id, meta in targets.items():
                    target_url = str(meta.get("target_url") or "")
                    debug: Dict[str, Any] = {
                        "method": "search_click",
                        "search_url": search_url,
                        "product_id": product_id,
                        "url": target_url,
                    }
                    html: Optional[str] = None
                    anchor = self._find_search_result_anchor(page, product_id=product_id, target_url=target_url)
                    if anchor is None:
                        self._scroll_coupang_search_results_page(page, max_wheel_batches=6)
                        anchor = self._find_search_result_anchor(page, product_id=product_id, target_url=target_url)
                    if anchor is None:
                        debug["error_code"] = "SEARCH_RESULT_LINK_NOT_FOUND"
                        self._last_detail_fetch_debug = dict(debug)
                        safe_print(f"[DETAIL][search_click] link not found product_id={product_id}")
                        results[product_id] = {"html": None, "fetch_debug": dict(debug)}
                        continue

                    try:
                        anchor.scroll_into_view_if_needed()
                    except Exception:
                        pass
                    try:
                        anchor.hover(timeout=2500)
                    except Exception:
                        pass
                    page.wait_for_timeout(random.randint(350, 800))

                    try:
                        with page.expect_navigation(wait_until="domcontentloaded", timeout=12000):
                            anchor.click(timeout=5000)
                        page.wait_for_timeout(random.randint(900, 1600))
                        self._simulate_human_actions(page)
                        html = page.content()
                        title = (page.title() or "")[:120]
                        preview = re.sub(r"\s+", " ", (html or "")[:300]).strip()
                        debug.update(
                            {
                                "page_url": str(page.url or "").strip(),
                                "page_title": title,
                                "body_len": len(str(html or "")),
                                "preview": preview,
                            }
                        )
                        if not str(html or "").strip():
                            debug["error_code"] = "EMPTY_BODY"
                            html = None
                            safe_print(f"[DETAIL][search_click] empty body product_id={product_id}")
                        elif self._is_blocked(html, title):
                            debug["error_code"] = "BLOCKED_HTML"
                            html = None
                            safe_print(
                                f"[DETAIL][search_click] blocked product_id={product_id} "
                                f"title={title or '-'}"
                            )
                        else:
                            debug["stage"] = "html_ok"
                            safe_print(
                                f"[DETAIL][search_click] ok product_id={product_id} "
                                f"page_title={title or '-'} body_len={len(str(html or ''))}"
                            )
                    except TimeoutError as e:
                        debug["error_code"] = "TIMEOUT"
                        debug["message"] = str(e)
                        html = None
                        safe_print(f"[DETAIL][search_click] timeout product_id={product_id}")
                    except Exception as e:
                        debug["error_code"] = type(e).__name__
                        debug["message"] = repr(e)
                        html = None
                        safe_print(
                            f"[DETAIL][search_click] exception product_id={product_id} "
                            f"error={type(e).__name__}"
                        )
                    finally:
                        self._last_detail_fetch_debug = dict(debug)
                        results[product_id] = {
                            "html": html,
                            "fetch_debug": dict(debug),
                        }
                        try:
                            self._restore_search_results_page(page, search_url)
                        except Exception:
                            pass
                return results
            except Exception as e:
                err_code = "BLOCKED_SEARCH" if str(e) == "BLOCKED_HOME" else type(e).__name__
                self._last_detail_fetch_debug = {
                    "method": "search_click",
                    "search_url": search_url,
                    "error_code": err_code,
                    "message": repr(e),
                }
                safe_print(f"[DETAIL][search_click] search flow exception error={err_code}")
                return results

    def fetch_detail_page_html(self, target_url: str, *, referer: str = "") -> Optional[str]:
        url = str(target_url or "").strip()
        if not url:
            self._last_detail_fetch_debug = {
                "method": "detail_fetch",
                "url": "",
                "error_code": "EMPTY_URL",
            }
            return None
        with self._io_lock:
            page = self._get_page()
            if page is None:
                self._last_detail_fetch_debug = {
                    "method": "detail_fetch",
                    "url": url,
                    "error_code": "PLAYWRIGHT_INIT_FAILED",
                    "message": str((self._last_error or {}).get("message", "")),
                }
                return None

            try:
                cur_url = str(page.url or "").strip()
            except Exception:
                cur_url = ""

            if "coupang.com" not in cur_url.lower():
                try:
                    page.goto("https://www.coupang.com", wait_until="domcontentloaded")
                    if self._is_blocked(page.content(), page.title()):
                        self._last_detail_fetch_debug = {
                            "method": "playwright_prewarm",
                            "url": url,
                            "error_code": "BLOCKED_HOME",
                            "page_url": str(page.url or ""),
                            "page_title": (page.title() or "")[:120],
                        }
                        safe_print("[DETAIL][playwright] prewarm blocked by WAF/CAPTCHA")
                        return None
                    self._simulate_human_actions(page)
                except Exception as e:
                    self._last_detail_fetch_debug = {
                        "method": "playwright_prewarm",
                        "url": url,
                        "error_code": type(e).__name__,
                        "message": repr(e),
                    }

            ref = str(referer or page.url or "https://www.coupang.com/").strip()
            html = self._requests_html_with_browser_session(page, url, referer=ref)
            if html:
                return html

            try:
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(random.randint(700, 1300))
                self._simulate_human_actions(page)
                html = page.content()
                title = (page.title() or "")[:120]
                preview = re.sub(r"\s+", " ", (html or "")[:300]).strip()
                self._last_detail_fetch_debug = {
                    "method": "playwright",
                    "url": url,
                    "page_url": str(page.url or "").strip(),
                    "page_title": title,
                    "body_len": len(str(html or "")),
                    "preview": preview,
                }
                if not html.strip():
                    self._last_detail_fetch_debug["error_code"] = "EMPTY_BODY"
                    safe_print(f"[DETAIL][playwright] empty body url={url}")
                    return None
                if self._is_blocked(html, title):
                    self._last_detail_fetch_debug["error_code"] = "BLOCKED_HTML"
                    safe_print(f"[DETAIL][playwright] blocked-like html url={url}")
                    return None
                self._last_detail_fetch_debug["stage"] = "html_ok"
                return html
            except TimeoutError as e:
                self._last_detail_fetch_debug = {
                    "method": "playwright",
                    "url": url,
                    "error_code": "TIMEOUT",
                    "message": str(e),
                }
                safe_print(f"[DETAIL][playwright] timeout url={url}")
                return None
            except Exception as e:
                self._last_detail_fetch_debug = {
                    "method": "playwright",
                    "url": url,
                    "error_code": type(e).__name__,
                    "message": repr(e),
                }
                safe_print(f"[DETAIL][playwright] exception url={url} error={type(e).__name__}")
                return None

    def bootstrap_login_session(self, wait_seconds: int = 120) -> bool:
        with self._io_lock:
            if self._page is not None:
                self.close()
            page = self._get_page(force_headless=self._prep_force_headless(), prep_profile=True)
            if page is None:
                return False
            try:
                page.goto("https://www.coupang.com/np/coupanglogin/login", wait_until="domcontentloaded")
                safe_print("[Bootstrap] 쿠팡 로그인 페이지를 열었습니다.")
                safe_print(f"[Bootstrap] 아래 경로에 세션이 저장됩니다: {self._prep_user_data_dir}")
                safe_print(f"[Bootstrap] {wait_seconds}초 내 수동 로그인 후 창을 그대로 두세요.")
                time.sleep(max(10, int(wait_seconds)))
                safe_print("[Bootstrap] 세션 저장 절차를 종료합니다.")
                return True
            except Exception as e:
                safe_print(f"[Crawler Error] keyword=BOOTSTRAP_LOGIN, error={e!r}")
                return False
            finally:
                self.close()

    def open_search_ready_session(self, wait_seconds: int = 120) -> bool:
        with self._io_lock:
            if self._page is not None:
                self.close()
            page = self._get_page(force_headless=self._prep_force_headless(), prep_profile=True)
            if page is None:
                return False
            try:
                page.goto("https://www.coupang.com", wait_until="domcontentloaded")
                if self._is_blocked(page.content(), page.title()):
                    safe_print("[WAF_BLOCK] 쿠팡 접속이 차단되었습니다. (Access Denied/CAPTCHA)")
                    self._stats["blocked"] += 1
                    return False
                page.wait_for_selector("input[name='q'], input[placeholder*='검색']", timeout=15000)
                self._simulate_human_actions(page)
                safe_print("[Ready] 쿠팡 메인 페이지 접속 완료.")
                safe_print("[Ready] 검색창에 키워드를 직접 입력해 주세요.")
                safe_print(f"[Ready] {wait_seconds}초 동안 브라우저를 유지합니다.")
                time.sleep(max(10, int(wait_seconds)))
                safe_print("[Ready] 수동 입력 대기 모드를 종료합니다.")
                return True
            except Exception as e:
                safe_print(f"[Crawler Error] keyword=OPEN_SEARCH_READY, error={e!r}")
                return False
            finally:
                self.close()

    def open_google_ready_session(self, wait_seconds: int = 180) -> bool:
        with self._io_lock:
            if self._page is not None:
                self.close()
            page = self._get_page(force_headless=self._prep_force_headless(), prep_profile=True)
            if page is None:
                return False
            try:
                page.goto("https://www.google.com/ncr", wait_until="domcontentloaded")
                page.wait_for_selector("textarea[name='q'], input[name='q']:not([type='hidden'])", timeout=15000)
                safe_print("[Ready] Google 홈 화면이 열렸습니다.")
                safe_print("[Ready] 직접 검색 후 쿠팡 결과 페이지 URL을 복사해 전달해 주세요.")
                safe_print(f"[Ready] {wait_seconds}초 동안 브라우저를 유지합니다.")
                time.sleep(max(10, int(wait_seconds)))
                return True
            except Exception as e:
                safe_print(f"[Crawler Error] keyword=OPEN_GOOGLE_READY, error={e!r}")
                return False
            finally:
                self.close()

    def parse_coupang_search_url(self, search_url: str) -> Dict[str, Any]:
        url = str(search_url or "").strip()
        if not url:
            return self._result_with_reason("EMPTY_URL")
        if "coupang.com/np/search" not in url:
            return self._result_with_reason("INVALID_URL")

        with self._io_lock:
            page = self._get_page(force_headless=True)
            if page is None:
                return self._result_with_reason("PLAYWRIGHT_INIT_FAILED")
            try:
                page.goto(url, wait_until="domcontentloaded")
                html = page.content()
                if self._is_blocked(html, page.title()):
                    safe_print("[WAF_BLOCK] 지정된 URL 파싱 중 WAF 차단 발생.")
                    self._stats["blocked"] += 1
                    reason = "BLOCKED_BY_WAF" if STEALTH_AVAILABLE else "BLOCKED_BY_WAF_NO_STEALTH"
                    return self._result_with_reason(reason)

                page.wait_for_selector(_PRODUCT_LIST_SELECTOR, timeout=10000)
                page.wait_for_timeout(800)
                html = page.content()
                product_count, items = self._parse_top10_from_html(html)
                if product_count <= 0:
                    return self._result_with_reason("NO_PRODUCTS")
                out = self._build_result(product_count, items)
                out["reason_code"] = "OK"
                return out
            except TimeoutError:
                return self._result_with_reason("TIMEOUT")
            except Exception as e:
                safe_print(f"[Crawler Error] keyword=PARSE_URL, error={e!r}")
                return self._result_with_reason("PARSE_FAILED")
            finally:
                self.close()

    def build_result_from_smoke_payload(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raw_items = list(payload.get("top10") or [])
        if not raw_items:
            return None

        items: List[Dict[str, Any]] = []
        for row in raw_items:
            if not isinstance(row, dict):
                continue
            try:
                rank = int(row.get("rank") or 0)
            except Exception:
                rank = 0
            if rank < 1:
                continue
            title = str(row.get("title") or "").strip()
            if not title:
                continue
            price_num = self._parse_int(str(row.get("price") or ""))
            if price_num is None:
                continue
            review_num = self._parse_int(str(row.get("review_count") or ""))
            review_score = self._parse_float(str(row.get("review_score") or ""))
            shipping = str(row.get("shipping") or "").strip()
            url = str(row.get("url") or "").strip()
            detail_ok = row.get("detail_fetch_ok")
            items.append(
                {
                    "rank": rank,
                    "title": title,
                    "price": float(price_num),
                    "review_count": float(review_num) if review_num is not None else None,
                    "review_score": float(review_score) if review_score is not None else None,
                    "delivery_type": None,
                    "shipping_fee": shipping or None,
                    "url": url,
                    "image_url": "",
                    "monthly_sales": str(row.get("monthly_sales") or ""),
                    "detail_fetch_ok": detail_ok if detail_ok is not None else None,
                }
            )

        if not items:
            return None

        try:
            product_count = int(payload.get("organic_count") or payload.get("card_count") or len(items))
        except Exception:
            product_count = len(items)

        out = self._build_result(product_count, items)
        out["reason_code"] = "OK"
        out["fetch_source"] = "smoke"
        return out

    def parse_local_html(self, file_path: str, *, skip_block_check: bool = False) -> Dict[str, Any]:
        """직접 저장한 로컬 HTML 파일 파싱 기능"""
        if not os.path.exists(file_path):
            return self._result_with_reason("FILE_NOT_FOUND")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                html = f.read()

            if not skip_block_check and self._is_blocked(html, ""):
                safe_print(f"[WAF_BLOCK] 로컬 파일({file_path}) 내에 WAF/CAPTCHA 차단 신호가 있습니다.")
                self._stats["blocked"] += 1
                return self._result_with_reason("BLOCKED_BY_WAF")

            product_count, items = self._parse_top10_from_html(html)
            if product_count <= 0 or not items:
                return self._result_with_reason("NO_PRODUCTS")

            out = self._build_result(product_count, items)
            out["reason_code"] = "OK"
            return out
        except Exception as e:
            safe_print(f"[Crawler Error] keyword=PARSE_LOCAL, error={e!r}")
            return self._result_with_reason("PARSE_FAILED")

    def _crawl_with_playwright(self, keyword: str) -> Optional[Dict[str, Any]]:
        with self._io_lock:
            page = self._get_page()
            if page is None:
                return None
            try:
                url = self._build_search_url(keyword)
                force_google_entry = str(os.environ.get("COUPANG_FORCE_GOOGLE_ENTRY", "")).strip().lower() in {
                    "1",
                    "true",
                    "y",
                    "yes",
                    "on",
                }
                try:
                    opened_url = self._open_search_results_via_google(page, keyword)
                    safe_print(f"[Crawler][playwright] google entry ok keyword={keyword} url={opened_url}")
                except Exception as google_ex:
                    if force_google_entry:
                        safe_print(
                            f"[Crawler][playwright] google entry required keyword={keyword} "
                            f"error={type(google_ex).__name__}"
                        )
                        self._last_error = {
                            "code": "GOOGLE_ENTRY_FAILED",
                            "message": repr(google_ex),
                        }
                        return None
                    safe_print(
                        f"[Crawler][playwright] google entry fallback keyword={keyword} "
                        f"error={type(google_ex).__name__}"
                    )
                    page.goto(url, wait_until="domcontentloaded")
                if self._is_blocked(page.content(), page.title()):
                    safe_print("[WAF_BLOCK][playwright] initial load blocked by WAF/CAPTCHA")
                    self._stats["blocked"] += 1
                    self._last_error = {
                        "code": "PLAYWRIGHT_BLOCKED_BY_WAF_INITIAL",
                        "message": "initial load blocked by WAF/CAPTCHA",
                    }
                    return None
                self._simulate_human_actions(page)
                self._linger_on_results_page(page, passes=random.randint(2, 4))
                self._hover_random_product_cards(page, attempts=random.randint(1, 2))
                self._human_sleep(0.25, 0.8)

                req_result = self._requests_with_browser_session(page, url)
                req_n = len((req_result or {}).get("top10_items") or [])
                if req_result is not None and req_n >= 10:
                    return req_result
                if req_result is not None and req_n < 10:
                    safe_print(
                        f"[Crawler][playwright] requests 비광고 {req_n}개만 확보 — 페이지 스크롤 후 DOM으로 10위까지 재시도"
                    )

                page.wait_for_selector(_PRODUCT_LIST_SELECTOR, timeout=12000)
                page.wait_for_timeout(random.randint(900, 1600))
                self._linger_on_results_page(page, passes=random.randint(2, 3))
                safe_print(
                    f"[Crawler][playwright] ready keyword={keyword} "
                    f"title={page.title()[:80]} url={page.url}"
                )
                self._scroll_coupang_search_results_page(page)
                self._hover_random_product_cards(page, attempts=random.randint(1, 3))
                self._human_sleep(0.2, 0.65)
                html = page.content()
                if self._is_blocked(html, page.title()):
                    safe_print("[WAF_BLOCK][playwright] blocked signal detected before parsing")
                    self._stats["blocked"] += 1
                    return None
                product_count, items = self._parse_top10_from_html(html)
                safe_print(
                    f"[Crawler][playwright] parsed keyword={keyword} "
                    f"product_count={product_count} top10_items={len(items)} (after scroll)"
                )
                if len(items) < 10:
                    self._linger_on_results_page(page, passes=2)
                    self._scroll_coupang_search_results_page(page, max_wheel_batches=12)
                    page.wait_for_timeout(random.randint(400, 900))
                    self._hover_random_product_cards(page, attempts=1)
                    html2 = page.content()
                    if not self._is_blocked(html2, page.title()):
                        pc2, items2 = self._parse_top10_from_html(html2)
                        if len(items2) > len(items):
                            product_count, items = pc2, items2
                            safe_print(
                                f"[Crawler][playwright] second pass keyword={keyword} "
                                f"product_count={product_count} top10_items={len(items)}"
                            )

                dom_n = len(items)
                if dom_n == 0 and req_result is None:
                    self._last_error = {
                        "code": "PLAYWRIGHT_NO_PRODUCTS",
                        "message": "playwright parse returned zero products",
                    }
                    return None
                if dom_n == 0:
                    self._last_fetch_source = "requests"
                    return req_result
                built_dom = self._build_result(product_count, items)
                if req_result is not None and req_n > dom_n:
                    self._last_fetch_source = "requests"
                    return req_result
                self._last_fetch_source = "playwright"
                return built_dom
            except TimeoutError as e:
                safe_print(f"[Crawler Error] keyword={keyword}, error=timeout, detail={e}")
                self._last_error = {
                    "code": "PLAYWRIGHT_SELECTOR_TIMEOUT",
                    "message": str(e),
                }
                return None
            except Exception as e:
                err_name = type(e).__name__
                if err_name == "TargetClosedError" or "TargetClosed" in err_name:
                    safe_print(f"[Crawler Error] keyword={keyword}, browser/context closed: {e!r}")
                    self._last_error = {"code": "BROWSER_CLOSED", "message": str(e)}
                    try:
                        self.close()
                    except Exception:
                        pass
                    return None
                try:
                    cur = page.url if page else "N/A"
                    title = (page.title() if page else "N/A") or "N/A"
                except Exception:
                    cur = "N/A"
                    title = "N/A"
                safe_print(f"[Crawler Error] keyword={keyword}, current_url={cur}, title={title}, error={e!r}")
                self._last_error = {
                    "code": "PLAYWRIGHT_EXCEPTION",
                    "message": repr(e),
                }
                return None

    def _bright_request_fetch_html(self, url: str) -> Optional[str]:
        """Bright Data Web Unlocker /request API 로 URL HTML을 가져온다. 실패 시 None."""
        token = (os.environ.get("BRIGHTDATA_API_TOKEN") or "").strip()
        zone = (os.environ.get("BRIGHTDATA_REQUEST_ZONE") or "").strip()
        if not token or not zone:
            self._last_bright_request_debug = {
                "stage": "precheck",
                "url": str(url or "").strip(),
                "error_code": "MISSING_BRIGHT_ENV",
                "message": "token or zone missing",
            }
            return None
        try:
            to = int(float(os.environ.get("BRIGHTDATA_REQUEST_TIMEOUT_SEC", "35")))
            to = max(10, min(120, to))
        except Exception:
            to = 35
        try:
            extra = int(float(os.environ.get("BRIGHTDATA_REQUEST_RETRIES", "1")))
            extra = max(0, min(3, extra))
        except Exception:
            extra = 1
        attempts = 1 + extra
        parsed_url = urlparse(str(url or "").strip())
        ref_q = dict(parse_qsl(parsed_url.query, keep_blank_values=True)).get("q", "")
        payload = {
            "zone": zone,
            "url": str(url or "").strip(),
            "format": "raw",
            "headers": {
                "Referer": self._search_engine_referer(ref_q),
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        }
        for attempt in range(attempts):
            if attempt > 0:
                time.sleep(0.55)
            r = None
            try:
                r = requests.post(
                    "https://api.brightdata.com/request",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    timeout=float(to),
                )
            except Exception as ex:
                self._last_bright_request_debug = {
                    "stage": "request_exception",
                    "url": str(url or "").strip(),
                    "attempt": attempt + 1,
                    "attempts": attempts,
                    "error_code": type(ex).__name__,
                    "message": repr(ex),
                }
                if attempt + 1 < attempts:
                    continue
                self._stats["bright_error"] += 1
                safe_print(f"[BRIGHT] request exception {type(ex).__name__}")
                return None
            content_type = str(r.headers.get("content-type", "") or "").strip()
            text = (r.text or "").strip()
            preview = re.sub(r"\s+", " ", text[:300]).strip()
            self._last_bright_request_debug = {
                "stage": "response",
                "url": str(url or "").strip(),
                "attempt": attempt + 1,
                "attempts": attempts,
                "status_code": int(r.status_code),
                "content_type": content_type,
                "body_len": len(text),
                "preview": preview,
            }
            if r.status_code != 200:
                retryable = r.status_code >= 500 or r.status_code == 429
                if retryable and attempt + 1 < attempts:
                    safe_print(f"[BRIGHT] HTTP {r.status_code} → retry {attempt + 1}/{attempts}")
                    continue
                self._stats["bright_error"] += 1
                self._last_bright_request_debug["error_code"] = f"HTTP_{r.status_code}"
                safe_print(
                    f"[BRIGHT][DETAIL] status={r.status_code} url={str(url or '').strip()} "
                    f"content_type={content_type or '-'} body_len={len(text)} preview={preview[:120]}"
                )
                return None
            if not text:
                self._stats["bright_error"] += 1
                self._last_bright_request_debug["error_code"] = "EMPTY_BODY"
                safe_print(f"[BRIGHT][DETAIL] empty body url={str(url or '').strip()} status=200")
                return None
            if text.lstrip().startswith("{"):
                try:
                    obj = r.json()
                    if isinstance(obj, dict):
                        for key in ("body", "html", "content", "result", "data"):
                            v = obj.get(key)
                            if isinstance(v, str) and "<" in v:
                                text = v.strip()
                                break
                except Exception:
                    pass
            if "<" not in text:
                self._stats["bright_error"] += 1
                self._last_bright_request_debug["error_code"] = "NON_HTML_BODY"
                self._last_bright_request_debug["body_len"] = len(text)
                self._last_bright_request_debug["preview"] = re.sub(r"\s+", " ", text[:300]).strip()
                safe_print(
                    f"[BRIGHT][DETAIL] non-html url={str(url or '').strip()} "
                    f"content_type={content_type or '-'} body_len={len(text)} "
                    f"preview={self._last_bright_request_debug['preview'][:120]}"
                )
                return None
            self._last_bright_request_debug["stage"] = "html_ok"
            self._last_bright_request_debug["body_len"] = len(text)
            self._last_bright_request_debug["preview"] = re.sub(r"\s+", " ", text[:300]).strip()
            return text

    def crawl_coupang(self, keyword: str) -> Dict[str, Any]:
        kw = str(keyword or "").strip()
        if not kw:
            return self._result_with_reason("EMPTY_KEYWORD")

        ck = self._cache_key(kw)
        if ck in self._cache:
            self._stats["cache_hit"] += 1
            hit = dict(self._cache[ck])
            hit.setdefault("fetch_source", "cache")
            return hit

        if _coupang_bright_request_enabled():
            tok = (os.environ.get("BRIGHTDATA_API_TOKEN") or "").strip()
            zn = (os.environ.get("BRIGHTDATA_REQUEST_ZONE") or "").strip()
            if tok and zn:
                surl = self._build_search_url(kw)
                html_bd = self._bright_request_fetch_html(surl)
                if html_bd and not self._is_blocked(html_bd, ""):
                    try:
                        min_n = int(os.environ.get("COUPANG_BRIGHT_MIN_ITEMS", "7"))
                        min_n = max(1, min(10, min_n))
                    except Exception:
                        min_n = 7
                    pc_bd, items_bd = self._parse_top10_from_html(html_bd)
                    if len(items_bd) >= min_n:
                        built_bd = self._build_result(pc_bd, items_bd)
                        built_bd["fetch_source"] = "bright_request"
                        self._cache[ck] = built_bd
                        self._last_success_cache[kw] = built_bd
                        self._last_fetch_source = "bright_request"
                        self._stats["bright_ok"] += 1
                        out_bd = dict(built_bd)
                        out_bd["reason_code"] = "OK"
                        safe_print(
                            f"[BRIGHT] SERP ok keyword={kw!r} items={len(items_bd)} "
                            f"min_required={min_n} url_len={len(surl)}"
                        )
                        return out_bd
                    safe_print(
                        f"[BRIGHT] SERP parse weak keyword={kw!r} items={len(items_bd)} "
                        f"min_required={min_n} → playwright fallback"
                    )
                elif html_bd and self._is_blocked(html_bd, ""):
                    safe_print(f"[BRIGHT] blocked-like HTML keyword={kw!r} → playwright fallback")
            else:
                safe_print("[BRIGHT] Bright 선행이 켜져 있으나 토큰 또는 zone 비어 있음 → skip")

        result = self._crawl_with_playwright(kw)
        if result is not None:
            src = str(self._last_fetch_source or "playwright")
            result["fetch_source"] = src
            self._cache[ck] = result
            self._last_success_cache[kw] = result
            if self._last_fetch_source == "requests":
                self._stats["requests_ok"] += 1
            else:
                self._stats["playwright_ok"] += 1
            result["reason_code"] = "OK"
            return dict(result)

        self._stats["failed"] += 1
        cached = self.get_cached_result(kw)
        if cached is not None:
            cached["reason_code"] = "CACHE_FALLBACK"
            return cached
        if self._stats.get("blocked", 0) > 0:
            reason = "BLOCKED_BY_WAF" if STEALTH_AVAILABLE else "BLOCKED_BY_WAF_NO_STEALTH"
            return self._result_with_reason(reason)
        code = str((self._last_error or {}).get("code", "")).strip().upper()
        if code == "PLAYWRIGHT_SELECTOR_TIMEOUT":
            return self._result_with_reason("PLAYWRIGHT_TIMEOUT")
        if code == "PLAYWRIGHT_NO_PRODUCTS":
            return self._result_with_reason("NO_PRODUCTS_PARSED")
        if code.startswith("REQUESTS_HTTP_"):
            return self._result_with_reason(code)
        if code == "REQUESTS_NO_PRODUCTS":
            return self._result_with_reason("REQUESTS_NO_PRODUCTS")
        if code == "REQUESTS_EXCEPTION":
            return self._result_with_reason("REQUESTS_EXCEPTION")
        if code == "PLAYWRIGHT_EXCEPTION":
            return self._result_with_reason("PLAYWRIGHT_EXCEPTION")
        if code == "GOOGLE_ENTRY_FAILED":
            return self._result_with_reason("GOOGLE_ENTRY_FAILED")
        if code == "PLAYWRIGHT_BLOCKED_BY_WAF_INITIAL":
            return self._result_with_reason("BLOCKED_BY_WAF_INITIAL")
        return self._result_with_reason("CRAWL_FAILED")

    def is_smoke_playwright_running(self) -> bool:
        self._maybe_reap_smoke_subprocess()
        with self._io_lock:
            sub = self._smoke_subproc
            t = self._smoke_thread
        if sub is not None and sub.poll() is None:
            return True
        return t is not None and t.is_alive()

    def stop_smoke_playwright_chromium_window(self, join_timeout: float = 20.0) -> None:
        """백그라운드 스모크 Chromium을 즉시 닫도록 신호를 보낸 뒤 스레드 종료를 기다린다."""
        self._terminate_smoke_subprocess_if_any()
        thr: Optional[threading.Thread] = None
        with self._io_lock:
            ev = self._smoke_stop_event
            thr = self._smoke_thread
        if ev is not None:
            ev.set()
        if thr is not None:
            thr.join(timeout=max(1.0, float(join_timeout)))
        with self._io_lock:
            self._smoke_thread = None
            self._smoke_stop_event = None

    def poll_smoke_startup_outcome(self, timeout_seconds: float = 10.0) -> Tuple[bool, Dict[str, Any]]:
        """
        스모크 Chromium 기동 직후 phase 안정화까지 폴링한다.
        Streamlit 버튼 핸들러에 두던 로직과 동일한 성공 판정을 유지한다.
        """
        deadline_poll = time.monotonic() + float(timeout_seconds)
        ok = False
        last: Dict[str, Any] = {}
        while time.monotonic() < deadline_poll:
            last = self.get_smoke_playwright_status()
            if last.get("phase") == "opened":
                ok = True
                break
            if last.get("phase") == "failed":
                ok = False
                break
            if not self.is_smoke_playwright_running():
                break
            time.sleep(0.2)
        if not ok and self.is_smoke_playwright_running():
            last = self.get_smoke_playwright_status()
            ph = str(last.get("phase") or "")
            if ph not in ("failed", "idle", "closed", "queued"):
                ok = True
        return ok, last

    def poll_smoke_until_coupang_probe_finished(
        self,
        *,
        timeout_seconds: float = 120.0,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        구글→쿠팡→HTML probe 및 `insert_coupang_search_snapshot` 직후에 worker가 올리는 phase까지 대기한다.
        - `opened`는 **DB 저장 이후**에 설정되므로, 창이 아직 열려 있어도(top10 반영 후) 곧바로 성공으로 반환 가능하다.
        - `poll_smoke_startup_outcome`과 달리 **타임아웃 시 임의 phase를 성공으로 치지 않는다.**
        - `COUPANG_SMOKE_SUBPROCESS=1` 등 **자식 프로세스 스모크**는 부모 phase가 부정확할 수 있어
          False를 돌려두고, 호출 측에서 DB 폴링으로 보완하는 것을 전제로 한다.
        """
        deadline = time.monotonic() + float(max(5.0, timeout_seconds))
        last: Dict[str, Any] = {}
        post_probe_phases = frozenset({"opened", "holding", "closed"})
        while time.monotonic() < deadline:
            last = self.get_smoke_playwright_status()
            ph = str(last.get("phase") or "")
            if ph == "failed":
                return False, last
            if ph in post_probe_phases:
                return True, last
            # 자식 프로세스 스모크: opened 등이 부모 status에 안 올라올 수 있음 → 곧장 DB 폴링 쪽에 맡김
            if ph in ("windows_subprocess", "windows_subprocess_running"):
                if not self.is_smoke_playwright_running():
                    return False, last
                time.sleep(0.35)
                continue
            if not self.is_smoke_playwright_running():
                items = list(last.get("top10_items") or [])
                if len(items) > 0:
                    return True, last
                return False, last
            time.sleep(0.2)
        last = self.get_smoke_playwright_status()
        if str(last.get("phase") or "") == "failed":
            return False, last
        items = list(last.get("top10_items") or [])
        if len(items) > 0:
            return True, last
        return False, last

    def _run_smoke_worker(self, url: str, max_wait_seconds: float, stop_event: threading.Event) -> None:
        """별도 스레드에서 실행. persistent 크롤 세션과 무관한 ephemeral Chromium."""
        target = str(url).strip() or "https://www.google.com/"
        hint_h_env = "headless=True (COUPANG_SMOKE_HEADLESS) — OS 창 없음. phase·상태로 확인."
        hint_h_auto = (
            "headless=True — Linux에 DISPLAY가 없어 자동 headless입니다. "
            "Railway/Docker에서는 phase·상태(JSON)로만 확인됩니다."
        )
        hint_v = (
            "headless=False — Playwright Chromium이 별도 창으로 보여야 합니다 (로컬 Windows 등)."
        )
        self._smoke_status_update(
            phase="launching",
            target_url=target,
            page_url="",
            page_title="",
            opened_at=None,
            closed_at=None,
            error="",
            top10_items=[],
            hint="브라우저 기동 중…",
        )
        self._sanitize_playwright_browser_env()
        self._log_playwright_preflight()
        _ensure_windows_proactor_policy()
        # env 명시 시 우선. 미설정 시 DISPLAY 없는 Linux는 headed 불가 → _prep_force_headless 와 동일하게 headless.
        _sh = str(os.environ.get("COUPANG_SMOKE_HEADLESS", "")).strip().lower()
        if _sh in {"1", "true", "y", "yes"}:
            use_headless = True
            _smoke_hint = hint_h_env
        elif _sh in {"0", "false", "n", "no"}:
            use_headless = False
            if sys.platform != "win32" and not (os.environ.get("DISPLAY") or "").strip():
                safe_print(
                    "[SMOKE] COUPANG_SMOKE_HEADLESS=false 이지만 DISPLAY가 없어 headless로 강제합니다."
                )
                use_headless = True
                _smoke_hint = hint_h_auto
            else:
                _smoke_hint = hint_v
        elif self._prep_force_headless():
            use_headless = True
            _smoke_hint = hint_h_auto
            safe_print("[SMOKE] DISPLAY 없음 — 스모크는 headless로 실행합니다.")
        else:
            use_headless = False
            _smoke_hint = hint_v
        self._smoke_status_update(headless=use_headless, hint=_smoke_hint)
        strict_clean = _smoke_strict_clean_enabled()
        if strict_clean:
            safe_print("[SMOKE] strict clean mode ON: profile/cache/session reset")
            for pdir in [self._chrome_user_data_dir, self._prep_user_data_dir]:
                try:
                    if pdir and os.path.isdir(pdir):
                        shutil.rmtree(pdir, ignore_errors=True)
                    if pdir:
                        os.makedirs(pdir, exist_ok=True)
                except Exception as ce:
                    safe_print(f"[SMOKE] profile dir reset 실패(무시): {pdir} {ce!r}")
            try:
                state_path = (Path(__file__).resolve().parent / ".smoke" / "coupang_state.json").resolve()
                if state_path.is_file():
                    state_path.unlink(missing_ok=True)
            except Exception as se:
                safe_print(f"[SMOKE] storage_state 삭제 실패(무시): {se!r}")

        _raw_ss = os.environ.get("COUPANG_SMOKE_STORAGE_STATE")
        smoke_storage_state_path = str(_raw_ss).strip() if _raw_ss is not None else ""
        if strict_clean:
            smoke_storage_state_path = ""
        elif not smoke_storage_state_path:
            smoke_storage_state_path = ".smoke/coupang_state.json"
        elif smoke_storage_state_path.lower() in {"0", "off", "false", "none"}:
            smoke_storage_state_path = ""
        context_kwargs: Dict[str, Any] = {
            "viewport": {"width": 1280, "height": 900},
            "locale": "ko-KR",
        }
        if smoke_storage_state_path:
            try:
                _ssp = Path(smoke_storage_state_path).expanduser()
                if not _ssp.is_absolute():
                    _ssp = (Path(__file__).resolve().parent / _ssp).resolve()
                smoke_storage_state_path = str(_ssp)
                if _ssp.is_file():
                    context_kwargs["storage_state"] = smoke_storage_state_path
                    safe_print(f"[SMOKE] storage_state 로드: {smoke_storage_state_path}")
                else:
                    safe_print(f"[SMOKE] storage_state 파일 없음(신규 세션 시작): {smoke_storage_state_path}")
            except Exception as ss_e:
                safe_print(f"[SMOKE] storage_state 경로 처리 실패(무시): {ss_e!r}")
                smoke_storage_state_path = ""
        _channel = str(os.environ.get("COUPANG_PLAYWRIGHT_CHANNEL", "")).strip() or None
        pw: Optional[Playwright] = None
        browser = None
        failed = False
        try:
            pw = sync_playwright().start()
            self._smoke_status_update(phase="playwright_started")
            browser = pw.chromium.launch(
                headless=use_headless,
                channel=_channel,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--window-size=1280,900",
                ],
            )
            self._smoke_status_update(phase="chromium_launched")
            context = browser.new_context(**context_kwargs)
            if strict_clean:
                try:
                    context.clear_cookies()
                except Exception as ce:
                    safe_print(f"[SMOKE] clear_cookies 실패(무시): {ce!r}")
            page = context.new_page()
            page.set_default_timeout(30000)
            self._smoke_status_update(phase="navigating")
            page.goto(target, wait_until="domcontentloaded")
            safe_print(f"[SMOKE] Playwright Chromium 준비 완료 url={target} headless={use_headless}")
            try:
                page.evaluate(
                    """async () => {
                        const link = document.createElement('link');
                        link.rel = 'stylesheet';
                        link.href = 'https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap';
                        document.head.appendChild(link);
                        await new Promise((r) => setTimeout(r, 500));
                        if (document.fonts && document.fonts.ready) {
                            await document.fonts.ready;
                        }
                    }"""
                )
                page.add_style_tag(
                    content="html, body, input, textarea, button { font-family: 'Noto Sans KR', sans-serif !important; }"
                )
                page.wait_for_timeout(500)
            except Exception as fe:
                safe_print(f"[SMOKE] 웹폰트 주입 생략/실패: {fe!r}")

            # 구글 검색창에 입력 후 Enter (로컬 headed에서 타이핑이 보임). 비활성: COUPANG_SMOKE_GOOGLE_QUERY=""
            _raw_sq = os.environ.get("COUPANG_SMOKE_GOOGLE_QUERY")
            google_query = "쿠팡" if _raw_sq is None else str(_raw_sq).strip()
            if google_query:
                try:
                    self._accept_google_consent_if_present(page)
                    self._smoke_status_update(
                        phase="google_search_input",
                        hint=f"구글 검색창에 입력 중: {google_query!r}",
                    )
                    box = page.locator("textarea[name='q'], input[name='q']").first
                    box.wait_for(state="visible", timeout=15000)
                    box.click(timeout=5000)
                    page.wait_for_timeout(250)
                    self._fill_search_field(box, google_query)
                    page.wait_for_timeout(400)
                    page.keyboard.press("Enter")
                    try:
                        page.wait_for_url(re.compile(r"/search\?"), timeout=25000)
                    except Exception:
                        safe_print("[SMOKE] 검색 결과 URL 대기 타임아웃 — 계속 진행")
                    page.wait_for_load_state("domcontentloaded")
                    page.wait_for_timeout(1200)
                    _refresh_serp_raw = os.environ.get("COUPANG_SMOKE_REFRESH_SERP", "1")
                    do_refresh_serp = str(_refresh_serp_raw).strip().lower() not in {"0", "false", "no", "off", "n"}
                    if do_refresh_serp:
                        try:
                            safe_print("[SMOKE] Google SERP refresh 1회 수행")
                            page.reload(wait_until="domcontentloaded", timeout=25000)
                            page.wait_for_timeout(900)
                        except Exception as re_serp:
                            safe_print(f"[SMOKE] SERP refresh 실패(무시): {re_serp!r}")
                    self._smoke_status_update(
                        phase="google_search_done",
                        hint=f"구글 검색 완료: {google_query!r}",
                    )
                    safe_print(f"[SMOKE] 구글 검색 실행 완료 query={google_query!r}")

                    # 원형 마우스 이동은 시연용. 기본 켜짐. 끄려면 COUPANG_SMOKE_MOUSE_DEMO=0 (또는 coupang_smoke_mouse_demo=0).
                    _raw_mouse = (
                        os.environ.get("COUPANG_SMOKE_MOUSE_DEMO")
                        or os.environ.get("coupang_smoke_mouse_demo")
                        or "1"
                    )
                    _mouse_demo = str(_raw_mouse).strip().lower() not in {"0", "false", "no", "off", "n"}
                    try:
                        if _mouse_demo:
                            self._smoke_status_update(
                                phase="smoke_mouse_circle",
                                hint="검색 결과 창 안에서 마우스 포인터를 원형으로 한 바퀴 이동합니다.",
                            )
                            vp = page.viewport_size or {"width": 1280, "height": 900}
                            vw = float(vp.get("width", 1280))
                            vh = float(vp.get("height", 900))
                            cx = vw / 2.0
                            cy = vh / 2.0
                            radius = min(vw, vh) * 0.22
                            steps = 52
                            page.mouse.move(cx + radius, cy)
                            page.wait_for_timeout(40)
                            for _i in range(1, steps + 1):
                                ang = (2.0 * math.pi * _i) / steps
                                page.mouse.move(
                                    cx + radius * math.cos(ang),
                                    cy + radius * math.sin(ang),
                                )
                                page.wait_for_timeout(12)
                            page.wait_for_timeout(200)

                        self._smoke_status_update(
                            phase="smoke_find_coupang_link",
                            hint="검색 결과에서 https://www.coupang.com 또는 coupang.com 링크를 찾아 클릭합니다.",
                        )
                        coupang_locators = [
                            page.locator("a").filter(
                                has_text=re.compile(r"https://www\.coupang\.com", re.I)
                            ).first,
                            page.locator('a[href^="https://www.coupang.com"]').first,
                            page.locator('a[href*="www.coupang.com"]').first,
                            page.locator('a[href*="coupang.com"]').first,
                        ]
                        clicked = False
                        last_pick_err: Optional[Exception] = None
                        for loc in coupang_locators:
                            try:
                                loc.wait_for(state="visible", timeout=6000)
                                loc.scroll_into_view_if_needed(timeout=5000)
                                ctx = page.context
                                n_before = len(ctx.pages)
                                loc.click(timeout=15000)
                                page.wait_for_timeout(350)
                                if len(ctx.pages) > n_before:
                                    page = ctx.pages[-1]
                                    page.wait_for_load_state("domcontentloaded", timeout=25000)
                                else:
                                    page.wait_for_url(
                                        re.compile(r"coupang\.com"),
                                        timeout=25000,
                                    )
                                    page.wait_for_load_state("domcontentloaded")
                                page.wait_for_timeout(600)
                                clicked = True
                                break
                            except Exception as pe:
                                last_pick_err = pe
                                continue
                        if clicked:
                            self._smoke_status_update(
                                phase="smoke_coupang_opened",
                                hint="쿠팡 페이지로 이동했습니다.",
                            )
                            safe_print("[SMOKE] 검색 결과에서 쿠팡 링크 클릭 후 로드까지 완료")

                            # 쿠팡 진입 후 검색까지 (마우스 원형 시연은 기본 켜짐·환경변수로만 끔)
                            try:
                                page.wait_for_timeout(400)
                                if _mouse_demo:
                                    self._smoke_status_update(
                                        phase="smoke_coupang_mouse_circle",
                                        hint="쿠팡 화면 안에서 마우스 포인터를 원형으로 2바퀴 이동합니다.",
                                    )
                                    page.wait_for_timeout(300)
                                    vp2 = page.viewport_size or {"width": 1280, "height": 900}
                                    vw2 = float(vp2.get("width", 1280))
                                    vh2 = float(vp2.get("height", 900))
                                    cx2 = vw2 / 2.0
                                    cy2 = vh2 / 2.0
                                    radius2 = min(vw2, vh2) * 0.20
                                    turns = 2
                                    steps2 = 52 * turns
                                    page.mouse.move(cx2 + radius2, cy2)
                                    page.wait_for_timeout(40)
                                    for _j in range(1, steps2 + 1):
                                        ang2 = (2.0 * math.pi * _j) / 52.0
                                        page.mouse.move(
                                            cx2 + radius2 * math.cos(ang2),
                                            cy2 + radius2 * math.sin(ang2),
                                        )
                                        page.wait_for_timeout(10)
                                    page.wait_for_timeout(220)

                                _raw_cq = os.environ.get("COUPANG_SMOKE_COUPANG_QUERY")
                                search_kw = "그램 노트북" if _raw_cq is None else str(_raw_cq).strip()
                                if not search_kw:
                                    raise RuntimeError("COUPANG_SMOKE_COUPANG_QUERY 가 비어 있습니다.")
                                self._smoke_status_update(
                                    phase="smoke_coupang_search_input",
                                    hint=f"쿠팡 검색창에 입력 중: {search_kw!r}",
                                )
                                input_locators = [
                                    page.locator("input[name='q']").first,
                                    page.get_by_placeholder("찾고 싶은 상품을 검색해보세요!").first,
                                    page.locator("input[placeholder*='상품']").first,
                                    page.locator("input[type='search']").first,
                                    page.locator("header input").first,
                                ]
                                search_box = None
                                for in_loc in input_locators:
                                    try:
                                        in_loc.wait_for(state="visible", timeout=5000)
                                        search_box = in_loc
                                        break
                                    except Exception:
                                        continue
                                if search_box is None:
                                    raise RuntimeError("쿠팡 검색 입력창을 찾지 못했습니다.")

                                search_box.click(timeout=5000)
                                page.wait_for_timeout(200)
                                search_box.click(timeout=5000)
                                page.wait_for_timeout(220)
                                self._fill_search_field(search_box, search_kw)
                                page.wait_for_timeout(250)

                                self._smoke_status_update(
                                    phase="smoke_coupang_search_enter",
                                    hint=f"쿠팡 검색 Enter 실행: {search_kw!r}",
                                )
                                page.keyboard.press("Enter")
                                try:
                                    page.wait_for_load_state("domcontentloaded", timeout=30000)
                                except Exception:
                                    pass
                                try:
                                    page.wait_for_load_state("networkidle", timeout=18000)
                                except Exception:
                                    pass
                                page.wait_for_timeout(600)
                                try:
                                    page.wait_for_selector(_PRODUCT_LIST_SELECTOR, timeout=22000, state="attached")
                                except Exception:
                                    safe_print("[SMOKE] 상품 리스트 DOM 대기 타임아웃 — probe는 계속 시도")
                                page.wait_for_timeout(500)
                                # 먼저 현재 DOM만 evaluate로 읽음(RankMark 등). 부족할 때만 아래에서 스크롤 후 재시도.
                                self._smoke_status_update(
                                    phase="smoke_coupang_search_done",
                                    hint=f"쿠팡 검색 실행 완료: {search_kw!r}",
                                )
                                safe_print(f"[SMOKE] 쿠팡 검색 실행 완료 query={search_kw!r}")
                                try:
                                    self._smoke_status_update(
                                        phase="smoke_coupang_html_probe",
                                        hint="결과 페이지 DOM에서 RankMark·카드 정보를 읽습니다(선 스크롤 없음).",
                                    )
                                    _probe_js = r"""() => {
                                        const norm = (s) => (s || "").replace(/\s+/g, " ").trim();
                                        const text = (el) => (el ? norm(el.textContent) : "");
                                        const pickPrice = (card) => {
                                            // 1) custom-oos 대표 판매가 우선
                                            const cands = card.querySelectorAll(
                                                ".custom-oos span, .custom-oos div, [class*='custom-oos'] span"
                                            );
                                            for (const n of cands) {
                                                const t = norm(n.innerText || n.textContent || "");
                                                if (!t || t.includes("개당")) continue;
                                                const mm = t.match(/[\d,]+\s*원/);
                                                if (mm) return norm(mm[0].replace(/\s+/g, ""));
                                            }
                                            // 2) fallback
                                            const area = card.querySelector(".PriceArea_priceArea__NntJz")
                                                || card.querySelector(".sale-price")
                                                || card.querySelector("[class*='price']");
                                            if (!area) return "";
                                            const blob = norm(area.innerText || area.textContent || "");
                                            const re = /[\d,]+\s*원/g;
                                            let first = "";
                                            let m;
                                            while ((m = re.exec(blob)) !== null) {
                                                if (!first) first = m[0];
                                            }
                                            return first ? norm(first.replace(/\s+/g, "")) : "";
                                        };
                                        const pickShippingKeywords = (blob) => {
                                            if (!blob) return "";
                                            const kws = [
                                                "로켓배송", "판매자로켓", "로켓직구", "로켓그로스", "새벽배송",
                                                "오늘 출발", "오늘출발", "도착보장", "내일도착", "내일 도착",
                                                "무료배송", "판매자 배송", "판매자배송",
                                            ];
                                            const seen = [];
                                            for (let i = 0; i < kws.length; i++) {
                                                const kw = kws[i];
                                                if (blob.includes(kw) && seen.indexOf(kw) === -1) seen.push(kw);
                                            }
                                            return seen.join(" / ");
                                        };
                                        const pickShipping = (card) => {
                                            const fee = card.querySelector(
                                                ".TextBadge_feePrice__n_gta, [data-badge-type='feePrice']"
                                            );
                                            if (fee) return norm(fee.textContent);
                                            const trySels = [
                                                "[class*='DeliveryInfo']",
                                                "[class*='deliveryInfo']",
                                                "[class*='DeliveryBadge']",
                                                "[class*='RocketBadge']",
                                                "[class*='RocketDelivery']",
                                                "[class*='rocketDelivery']",
                                                "[class*='ProductUnit_badge']",
                                                "[class*='ImageBadge']",
                                                "[class*='BadgeList']",
                                            ];
                                            for (let i = 0; i < trySels.length; i++) {
                                                const n = card.querySelector(trySels[i]);
                                                if (n) {
                                                    const t = norm(n.textContent);
                                                    if (t && !/^\d+%$/.test(t)) return t;
                                                }
                                            }
                                            const badgeBlob = Array.from(card.querySelectorAll(
                                                "[class*='Badge'], [class*='badge'], [class*='Delivery'], "
                                                + "[class*='delivery'], [class*='Label'], [class*='label'], "
                                                + "[class*='Rocket'], [class*='rocket'], [data-badge-type]"
                                            )).map((n) => norm(n.textContent)).join(" ");
                                            let kw = pickShippingKeywords(badgeBlob);
                                            if (kw) return kw;
                                            kw = pickShippingKeywords(norm(card.innerText || card.textContent || ""));
                                            return kw;
                                        };
                                        const pickReviewScore = (card) => {
                                            const wrap = card.querySelector(".ProductRating_productRating__jjf7W");
                                            if (!wrap) return "";
                                            const labeled = wrap.querySelector("[aria-label]");
                                            if (labeled) {
                                                const al = norm(labeled.getAttribute("aria-label") || "");
                                                const am = al.match(/(\d+(?:\.\d+)?)/);
                                                if (am) return am[1];
                                            }
                                            const starSels = ["em", "strong", "[class*='rating']"];
                                            for (let si = 0; si < starSels.length; si++) {
                                                const n = wrap.querySelector(starSels[si]);
                                                if (n) {
                                                    const t = norm(n.textContent);
                                                    const tm = t.match(/(\d+(?:\.\d+)?)/);
                                                    if (tm) return tm[1];
                                                }
                                            }
                                            return "";
                                        };
                                        const pickProductUrl = (card) => {
                                            let a = card.querySelector(
                                                "a[href*='vp/products'], a[href*='/products/'], "
                                                + "a[href*='www.coupang.com/vp/'], a[href^='/vp/products']"
                                            );
                                            if (!a) a = card.querySelector("a[href]");
                                            if (!a) return "";
                                            let href = (a.getAttribute("href") || "").trim();
                                            if (!href) return "";
                                            if (href.startsWith("/")) href = "https://www.coupang.com" + href;
                                            return href;
                                        };
                                        const pickReview = (card) => {
                                            const el = card.querySelector(
                                                ".ProductRating_productRating__jjf7W [class*='fw-text-'], "
                                                + ".rating-total-count, .rating-count, .count"
                                            );
                                            const t = el ? norm(el.textContent) : "";
                                            const paren = t.match(/\(\s*([\d,]+)\s*\)/);
                                            if (paren) return paren[1].replace(/,/g, "");
                                            const digits = t.match(/[\d,]+/);
                                            return digits ? digits[0].replace(/,/g, "") : t;
                                        };
                                        const cards = Array.from(document.querySelectorAll(
                                            "li.ProductUnit_productUnit__Qd6sv, li.search-product, "
                                            + "ul#product-list > li, ul#productList li, li[data-product-id], "
                                            + "li[class*='ProductUnit'], li[class*='productUnit']"
                                        ));
                                        const isAd = (card) => {
                                            if (card.querySelector(
                                                ".search-product__ad-badge, .search-product__ad, .ad-badge-text"
                                            )) return true;
                                            if (norm(card.textContent).includes("광고")
                                                && !card.querySelector("[class*='RankMark_rank']")) return true;
                                            return false;
                                        };
                                        const extract = (card) => {
                                            const titleEl = card.querySelector(
                                                ".ProductUnit_productNameV2__cV9cw, .name, "
                                                + "a[class*='productName'], [class*='productName'], "
                                                + "dd.descriptions a, .product-name"
                                            );
                                            return {
                                                title: text(titleEl),
                                                price: pickPrice(card),
                                                shipping: pickShipping(card),
                                                review_count: pickReview(card),
                                                review_score: pickReviewScore(card),
                                                url: pickProductUrl(card),
                                            };
                                        };
                                        const rankFromCard = (card) => {
                                            const nodes = card.querySelectorAll("[class*='RankMark_rank']");
                                            for (let ri = 0; ri < nodes.length; ri++) {
                                                const el = nodes[ri];
                                                const cls = el.className || "";
                                                const blob = typeof cls === "string" ? cls : String(cls || "");
                                                const mWhole = blob.match(/RankMark_rank(\d+)/);
                                                if (mWhole) {
                                                    const rv = parseInt(mWhole[1], 10);
                                                    if (rv >= 1 && rv <= 10) return rv;
                                                }
                                                const parts = blob.split(/\s+/);
                                                for (let pj = 0; pj < parts.length; pj++) {
                                                    const mm = parts[pj].match(/^RankMark_rank(\d+)/);
                                                    if (mm) {
                                                        const rv2 = parseInt(mm[1], 10);
                                                        if (rv2 >= 1 && rv2 <= 10) return rv2;
                                                    }
                                                }
                                                const t = norm(el.textContent || "");
                                                if (/^\d{1,2}$/.test(t)) {
                                                    const rv3 = parseInt(t, 10);
                                                    if (rv3 >= 1 && rv3 <= 10) return rv3;
                                                }
                                            }
                                            return null;
                                        };
                                        const byRank = {};
                                        const seenUrlsRank = new Set();
                                        for (const card of cards) {
                                            const rk = rankFromCard(card);
                                            if (rk === null) continue;
                                            if (isAd(card)) continue;
                                            const row = extract(card);
                                            const tn = norm(row.title);
                                            if (tn.length < 4) continue;
                                            const u = norm(row.url);
                                            const dedupeKey = rk + "|" + u;
                                            if (u && seenUrlsRank.has(dedupeKey)) continue;
                                            if (u) seenUrlsRank.add(dedupeKey);
                                            if (!(rk in byRank)) {
                                                byRank[rk] = {
                                                    rank: rk,
                                                    title: row.title,
                                                    price: row.price,
                                                    shipping: row.shipping,
                                                    review_count: row.review_count,
                                                    review_score: row.review_score,
                                                    url: row.url,
                                                };
                                            }
                                        }
                                        let top10 = [];
                                        for (let r = 1; r <= 10; r++) {
                                            if (byRank[r]) top10.push(byRank[r]);
                                        }
                                        let organic_count = Object.keys(byRank).length;
                                        if (organic_count === 0) {
                                            const organicRows = [];
                                            const seenUrls = new Set();
                                            for (const card of cards) {
                                                if (isAd(card)) continue;
                                                const row = extract(card);
                                                const tn = norm(row.title);
                                                if (tn.length < 4) continue;
                                                const u = norm(row.url);
                                                if (u && seenUrls.has(u)) continue;
                                                if (u) seenUrls.add(u);
                                                organicRows.push(row);
                                            }
                                            organic_count = organicRows.length;
                                            top10 = organicRows.slice(0, 10).map((row, idx) => ({
                                                rank: idx + 1,
                                                title: row.title,
                                                price: row.price,
                                                shipping: row.shipping,
                                                review_count: row.review_count,
                                                review_score: row.review_score,
                                                url: row.url,
                                            }));
                                        }
                                        const sample = top10.slice(0, 5).map((row) => ({
                                            name: row.title,
                                            price: row.price,
                                            review_score: row.review_score,
                                            url: row.url,
                                        }));
                                        const html = document.documentElement && document.documentElement.outerHTML;
                                        const nextDataProbe = (() => {
                                            const el = document.getElementById("__NEXT_DATA__");
                                            const winHas =
                                                typeof window.__NEXT_DATA__ !== "undefined" &&
                                                window.__NEXT_DATA__ !== null;
                                            if (!el || !el.textContent) {
                                                return {
                                                    script_present: false,
                                                    window_present: winHas,
                                                };
                                            }
                                            try {
                                                const j = JSON.parse(el.textContent);
                                                const rootKeys =
                                                    j && typeof j === "object"
                                                        ? Object.keys(j).slice(0, 24)
                                                        : [];
                                                let propsKeys = [];
                                                if (j && j.props && typeof j.props === "object") {
                                                    propsKeys = Object.keys(j.props).slice(0, 24);
                                                }
                                                return {
                                                    script_present: true,
                                                    parse_ok: true,
                                                    root_keys: rootKeys,
                                                    props_keys: propsKeys,
                                                    window_present: winHas,
                                                };
                                            } catch (e) {
                                                return {
                                                    script_present: true,
                                                    parse_ok: false,
                                                    parse_err: String(e),
                                                    window_present: winHas,
                                                };
                                            }
                                        })();
                                        return {
                                            url: location.href,
                                            title: document.title || "",
                                            html_len: html ? html.length : 0,
                                            card_count: cards.length,
                                            organic_count: organic_count,
                                            top10: top10,
                                            sample: sample,
                                            next_data_probe: nextDataProbe,
                                            _probe_rev: "rankmark-nextdata-probe-20260203",
                                        };
                                    }"""
                                    probe: Optional[Dict[str, Any]] = None
                                    last_ev: Optional[Exception] = None
                                    for _probe_try in range(4):
                                        try:
                                            probe = page.evaluate(_probe_js)
                                            break
                                        except Exception as ev_e:
                                            last_ev = ev_e
                                            msg = str(ev_e).lower()
                                            if (
                                                "execution context was destroyed" in msg
                                                or "navigation" in msg
                                            ):
                                                page.wait_for_timeout(900 + _probe_try * 700)
                                                try:
                                                    page.wait_for_load_state(
                                                        "domcontentloaded", timeout=20000
                                                    )
                                                except Exception:
                                                    pass
                                                continue
                                            raise
                                    if probe is None:
                                        raise last_ev or RuntimeError("HTML probe evaluate failed")
                                    _t10 = list(probe.get("top10") or [])
                                    if len(_t10) < 10:
                                        safe_print(
                                            f"[SMOKE] 첫 probe 상품 {len(_t10)}개 — 지연 로드 대비 마우스 스크롤 후 probe 1회 재시도"
                                        )
                                        self._scroll_coupang_search_results_page(page, max_wheel_batches=10)
                                        page.wait_for_timeout(450)
                                        try:
                                            probe2 = page.evaluate(_probe_js)
                                            if isinstance(probe2, dict):
                                                t2 = list(probe2.get("top10") or [])
                                                if len(t2) > len(_t10):
                                                    probe = probe2
                                        except Exception as re_e:
                                            safe_print(f"[SMOKE] probe 재시도 생략: {re_e!r}")
                                    self._smoke_status_update(top10_items=list(probe.get("top10") or []))
                                    safe_print(
                                        "[SMOKE] HTML probe: "
                                        f"url={probe.get('url','')} "
                                        f"title={probe.get('title','')!r} "
                                        f"html_len={probe.get('html_len',0)} "
                                        f"card_count={probe.get('card_count',0)} "
                                        f"organic_count={probe.get('organic_count', 0)}"
                                    )
                                    safe_print(f"[SMOKE] HTML probe top10={probe.get('top10', [])!r}")
                                    safe_print(f"[SMOKE] HTML probe sample={probe.get('sample', [])!r}")
                                    safe_print(f"[SMOKE] next_data_probe={probe.get('next_data_probe')!r}")
                                    smoke_payload = {
                                        "saved_at": datetime.now().isoformat(timespec="seconds"),
                                        "keyword": search_kw,
                                        "source_type": "smoke",
                                        **probe,
                                    }
                                    self._sync_smoke_ranked_ui_cache_from_payload(search_kw, smoke_payload)
                                    _dump_smoke_search_html(str(page.content() or ""))
                                    detail_bundle = self._smoke_fetch_topn_sales(
                                        page, probe, keyword=search_kw
                                    )
                                    smoke_payload["detail_results"] = detail_bundle.get("items") or []
                                    smoke_payload["detail_limit"] = detail_bundle.get("detail_limit")
                                    smoke_payload["detail_pick_mode"] = detail_bundle.get(
                                        "detail_pick_mode"
                                    )
                                    smoke_payload["detail_target_ranks"] = (
                                        detail_bundle.get("target_ranks") or []
                                    )
                                    items = list(detail_bundle.get("items") or [])
                                    smoke_payload["rank1_detail"] = items[0] if items else {}
                                    _persist_smoke_extract_report_to_db(smoke_payload)
                                    _dump_smoke_extract_report(smoke_payload)
                                except Exception as hp_e:
                                    safe_print(f"[SMOKE] HTML probe 실패(무시): {hp_e!r}")
                                    smoke_payload = {
                                        "saved_at": datetime.now().isoformat(timespec="seconds"),
                                        "keyword": search_kw,
                                        "source_type": "smoke",
                                        "error": repr(hp_e),
                                        "top10": [],
                                        "card_count": None,
                                    }
                                    self._sync_smoke_ranked_ui_cache_from_payload(search_kw, smoke_payload)
                                    _persist_smoke_extract_report_to_db(smoke_payload)
                                    _dump_smoke_extract_report(smoke_payload)
                            except Exception as ce2:
                                safe_print(f"[SMOKE] 쿠팡 검색 자동 시연 단계 실패: {ce2!r}")
                        else:
                            safe_print(
                                f"[SMOKE] 쿠팡 링크 클릭 단계 건너뜀/실패 — 현 SERP 기준으로 진행: {last_pick_err!r}"
                            )
                    except Exception as ce:
                        safe_print(f"[SMOKE] 마우스 원형/쿠팡 클릭 단계 실패: {ce!r}")
                except Exception as se:
                    safe_print(f"[SMOKE] 구글 검색 단계 실패: {se!r}")

            try:
                ptitle = page.title()
                purl = page.url
            except Exception:
                ptitle = ""
                purl = ""
            self._smoke_status_update(
                phase="opened",
                page_url=purl,
                page_title=ptitle,
                opened_at=time.time(),
                hint="첫 로드 완료. 실행 단계를 계속 진행합니다.",
            )
            with self._io_lock:
                self._last_error = {}

            deadline = time.monotonic() + float(max_wait_seconds)
            poll = 0.5
            self._smoke_status_update(phase="holding")
            while time.monotonic() < deadline:
                if stop_event.is_set():
                    safe_print("[SMOKE] 사용자 강제 종료 신호 수신.")
                    self._smoke_status_update(hint="강제 종료 신호 수신, 브라우저를 닫는 중…")
                    break
                time.sleep(poll)
            if smoke_storage_state_path and not strict_clean:
                try:
                    Path(smoke_storage_state_path).parent.mkdir(parents=True, exist_ok=True)
                    context.storage_state(path=smoke_storage_state_path)
                    safe_print(f"[SMOKE] storage_state 저장: {smoke_storage_state_path}")
                except Exception as ss_w:
                    safe_print(f"[SMOKE] storage_state 저장 실패(무시): {ss_w!r}")
            safe_print("[SMOKE] 유지 시간 종료 또는 중지에 따라 브라우저를 닫습니다.")
        except Exception as e:
            failed = True
            safe_print(f"[SMOKE] Playwright Chromium 실패: {e!r}")
            self._smoke_status_update(phase="failed", error=str(e), closed_at=time.time())
            with self._io_lock:
                self._last_error = {"code": "SMOKE_CHROMIUM", "message": str(e)}
        finally:
            try:
                if browser is not None:
                    browser.close()
            except Exception:
                pass
            try:
                if pw is not None:
                    pw.stop()
            except Exception:
                pass
            if not failed:
                self._smoke_status_update(phase="closed", closed_at=time.time())
            with self._io_lock:
                if self._smoke_thread is threading.current_thread():
                    self._smoke_thread = None
                    self._smoke_stop_event = None

    def smoke_open_playwright_chromium_window(
        self,
        url: str = "https://www.google.com/",
        wait_seconds: float = 5.0,
    ) -> bool:
        """
        크롤러 persistent 세션과 별도로 Playwright 번들 Chromium을 별도 창으로 연다.
        Streamlit 요청을 막지 않도록 백그라운드 스레드에서 추출 후 최대 wait_seconds 만큼 유지했다가 닫는다.
        대시보드의 강제 종료 버튼은 stop_smoke_playwright_chromium_window() 로 즉시 닫을 수 있다.
        """
        return self.start_smoke_playwright_chromium_window(url=url, max_wait_seconds=wait_seconds)

    def start_smoke_playwright_chromium_window(
        self,
        url: str = "https://www.google.com/",
        max_wait_seconds: float = 5.0,
    ) -> bool:
        max_wait_seconds = max(5.0, float(max_wait_seconds))
        target = str(url).strip() or "https://www.google.com/"
        old_thr: Optional[threading.Thread] = None
        old_ev: Optional[threading.Event] = None
        with self._io_lock:
            old_thr = self._smoke_thread
            old_ev = self._smoke_stop_event
        if old_ev is not None:
            old_ev.set()
        if old_thr is not None:
            old_thr.join(timeout=20.0)

        self._terminate_smoke_subprocess_if_any()

        with self._io_lock:
            # 스모크 시작 시 이전 crawl_coupang 등에서 남은 PLAYWRIGHT_* 오류가 prep에 섞이지 않게 비운다.
            self._last_error = {}

        self._reset_smoke_ranked_ui_cache(str(os.environ.get("COUPANG_SMOKE_COUPANG_QUERY", "")).strip())

        self._smoke_status_update(
            phase="queued",
            target_url=target,
            headless=None,
            page_url="",
            page_title="",
            opened_at=None,
            closed_at=None,
            error="",
            hint="스모크 Chromium을 시작합니다.",
        )

        if CoupangCrawler._smoke_use_subprocess_launch():
            tmpd = tempfile.mkdtemp(prefix="modiba_pwsmoke_")
            stopf = os.path.join(tmpd, "stop.txt")
            script = os.path.abspath(__file__)
            cmd = [
                sys.executable,
                script,
                "--smoke-child",
                target,
                str(int(max_wait_seconds)),
                stopf,
            ]
            cwd = os.path.dirname(script)
            cflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=cwd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=cflags,
                )
            except OSError as exc:
                self._smoke_status_update(
                    phase="failed",
                    error=f"subprocess_spawn:{exc}",
                    closed_at=time.time(),
                    hint=str(exc),
                )
                shutil.rmtree(tmpd, ignore_errors=True)
                return False
            with self._io_lock:
                self._smoke_subproc = proc
                self._smoke_stop_file = stopf
                self._smoke_tmpdir = tmpd
                self._smoke_thread = None
                self._smoke_stop_event = None
            self._smoke_status_update(
                phase="windows_subprocess",
                headless=False,
                subprocess_pid=proc.pid,
                hint=(
                    "자식 프로세스에서 headed Chromium을 실행했습니다. 작업 표시줄에서 창을 확인하세요. "
                    "브라우저로 Railway 주소만 연 경우 창은 서버에만 뜨고 이 PC에는 보이지 않습니다."
                ),
            )
            return True

        with self._io_lock:
            self._smoke_stop_event = threading.Event()
            stop_ev = self._smoke_stop_event

        def runner() -> None:
            self._run_smoke_worker(target, max_wait_seconds, stop_ev)

        t = threading.Thread(target=runner, name="pw-smoke-chromium", daemon=True)
        with self._io_lock:
            self._smoke_thread = t
        t.start()
        return True

    def get_stats(self) -> Dict[str, int]:
        return dict(self._stats)

    def get_last_fetch_source(self) -> str:
        return str(self._last_fetch_source or "unknown")

    def get_last_error(self) -> Dict[str, str]:
        return dict(self._last_error)

    def get_last_bright_request_debug(self) -> Dict[str, Any]:
        return dict(self._last_bright_request_debug)

    def get_last_detail_fetch_debug(self) -> Dict[str, Any]:
        return dict(self._last_detail_fetch_debug)

    def close(self) -> None:
        try:
            self.stop_smoke_playwright_chromium_window(join_timeout=15.0)
        except Exception:
            pass
        with self._io_lock:
            if self._page is not None:
                try:
                    self._page.close()
                except Exception:
                    pass
                self._page = None
            if self._context is not None:
                try:
                    self._context.close()
                except Exception:
                    pass
                self._context = None
            if self._playwright is not None:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None


_shared_crawler: Optional[CoupangCrawler] = None


_REQUIRED_SHARED_CRAWLER_METHODS = (
    "get_smoke_ranked_ui_cache",
    "poll_smoke_until_coupang_probe_finished",
)


def _shared_crawler_is_stale(inst: Any, crawler_cls: type) -> bool:
    if inst is None:
        return False
    if type(inst) is not crawler_cls:
        return True
    for name in _REQUIRED_SHARED_CRAWLER_METHODS:
        if not callable(getattr(crawler_cls, name, None)):
            return True
    return False


def get_shared_crawler(*, force_refresh: bool = False, _internal_reload_done: bool = False) -> CoupangCrawler:
    """프로세스 전역 단일 크롤러. 스테일 인스턴스·구버전 클래스면 모듈을 reload 후 한 번만 재귀한다."""
    global _shared_crawler
    import importlib
    import sys

    mod = sys.modules.get(__name__)
    crawler_cls = getattr(mod, "CoupangCrawler", CoupangCrawler) if mod is not None else CoupangCrawler

    stale = bool(force_refresh)
    if _shared_crawler is not None:
        stale = stale or _shared_crawler_is_stale(_shared_crawler, crawler_cls)
    if stale:
        try:
            if _shared_crawler is not None:
                _shared_crawler.close()
        except Exception:
            pass
        _shared_crawler = None
        if mod is not None and not _internal_reload_done:
            importlib.reload(mod)
            return mod.get_shared_crawler(force_refresh=False, _internal_reload_done=True)

    if _shared_crawler is None:
        _shared_crawler = crawler_cls()
    return _shared_crawler


def poll_smoke_until_coupang_probe(*, timeout_seconds: float = 120.0) -> Tuple[bool, Dict[str, Any]]:
    """
    Streamlit·구 import 경로에서도 안전한 모듈 수준 진입점.
    항상 현재 `get_shared_crawler()` 인스턴스로 probe 완료까지 대기한다.
    """
    cc = get_shared_crawler()
    fn = getattr(cc, "poll_smoke_until_coupang_probe_finished", None)
    if not callable(fn):
        cc = get_shared_crawler(force_refresh=True)
        fn = getattr(cc, "poll_smoke_until_coupang_probe_finished", None)
    if not callable(fn):
        return cc.poll_smoke_startup_outcome(timeout_seconds=min(120.0, float(timeout_seconds)))
    return fn(timeout_seconds=timeout_seconds)


def crawl_coupang(keyword: str) -> Dict[str, float]:
    return get_shared_crawler().crawl_coupang(keyword)


def _shutdown() -> None:
    global _shared_crawler
    if _shared_crawler is not None:
        _shared_crawler.close()


atexit.register(_shutdown)

def save_to_excel(result_dict: Dict[str, Any]):
    if result_dict.get("top10_items"):
        try:
            import pandas as pd
            df = pd.DataFrame(result_dict["top10_items"])
            df.to_excel("results.xlsx", index=False)
            safe_print("[System] 결과를 results.xlsx 파일로 성공적으로 저장했습니다.")
        except ImportError:
            safe_print("[System] pandas 또는 openpyxl 모듈이 설치되어 있지 않아 엑셀 저장을 건너뜁니다.")


if __name__ == "__main__":
    if len(sys.argv) >= 5 and sys.argv[1] == "--smoke-child":
        _child_url = sys.argv[2]
        _child_sec = float(sys.argv[3])
        _child_stopf = sys.argv[4]
        _ensure_windows_proactor_policy()
        _smoke_crawler = CoupangCrawler()
        _smoke_ev = threading.Event()

        def _watch_smoke_stop_file() -> None:
            while not _smoke_ev.wait(0.35):
                try:
                    if os.path.isfile(_child_stopf):
                        _smoke_ev.set()
                        return
                except OSError:
                    pass

        threading.Thread(target=_watch_smoke_stop_file, daemon=True).start()
        _smoke_crawler._run_smoke_worker(_child_url, _child_sec, _smoke_ev)
        sys.exit(0)

    parser = argparse.ArgumentParser(description="Coupang crawler utility")
    parser.add_argument("--keyword", default="페이스 리프팅 밴드", help="검색 키워드")
    parser.add_argument(
        "--bootstrap-login",
        action="store_true",
        help="전용 프로필로 로그인 세션을 저장하는 1회 실행 모드",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=120,
        help="bootstrap-login 모드에서 로그인 대기 시간(초)",
    )
    parser.add_argument(
        "--open-search-ready",
        action="store_true",
        help="쿠팡 메인 접속 후 검색창 수동 입력 대기 모드",
    )
    parser.add_argument(
        "--open-google-ready",
        action="store_true",
        help="Google 홈 화면만 열어두고 수동 검색 대기 모드",
    )
    parser.add_argument(
        "--parse-url",
        default="",
        help="사용자가 전달한 쿠팡 검색결과 URL 파싱 모드",
    )
    parser.add_argument(
        "--open-home-ready",
        action="store_true",
        help="쿠팡 홈 접속 확인 후 수동 조작 대기 모드",
    )
    parser.add_argument(
        "--parse-local-html",
        default="",
        help="직접 저장한 로컬 HTML 파일을 파싱하는 모드",
    )
    args = parser.parse_args()

    crawler = get_shared_crawler()
    
    result_data = None

    if args.bootstrap_login:
        ok = crawler.bootstrap_login_session(wait_seconds=args.wait_seconds)
        safe_print({"bootstrap_login": bool(ok), "profile_dir": crawler._chrome_user_data_dir, "profile": crawler._chrome_profile})
    elif args.open_home_ready:
        ok = crawler.open_home_ready_session(wait_seconds=args.wait_seconds)
        safe_print({"open_home_ready": bool(ok), "profile_dir": crawler._chrome_user_data_dir, "profile": crawler._chrome_profile})
    elif args.open_google_ready:
        ok = crawler.open_google_ready_session(wait_seconds=args.wait_seconds)
        safe_print({"open_google_ready": bool(ok), "profile_dir": crawler._chrome_user_data_dir, "profile": crawler._chrome_profile})
    elif args.open_search_ready:
        ok = crawler.open_search_ready_session(wait_seconds=args.wait_seconds)
        safe_print({"open_search_ready": bool(ok), "profile_dir": crawler._chrome_user_data_dir, "profile": crawler._chrome_profile})
    elif args.parse_url:
        result_data = crawler.parse_coupang_search_url(args.parse_url)
        safe_print(result_data)
        safe_print(crawler.get_stats())
    elif args.parse_local_html:
        result_data = crawler.parse_local_html(args.parse_local_html)
        safe_print(result_data)
        safe_print(crawler.get_stats())
    else:
        result_data = crawler.crawl_coupang(args.keyword)
        safe_print(result_data)
        safe_print(crawler.get_stats())

    # 결과가 존재하면 엑셀로 저장 (pandas 필요)
    if result_data:
        save_to_excel(result_data)