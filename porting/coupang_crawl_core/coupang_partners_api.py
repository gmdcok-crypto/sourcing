from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests


def coupang_category_name_to_l1_l2(category_name: str) -> Tuple[str, str]:
    """
    파트너스 상품 검색 응답의 `categoryName`을 1·2차 이름으로 분리한다.

    - 단일 라벨만 오는 경우(예: \"생활용품\"): (그 문자열, \"\").
    - 경로 형태(예: \"생활용품 > 욕실용품\"): 구분자 `>` 기준 앞 두 구간만 사용, 나머지는 무시.
    """
    raw = str(category_name or "").strip()
    if not raw:
        return "", ""
    parts = [p.strip() for p in raw.split(">") if str(p).strip()]
    if not parts:
        return "", ""
    l1 = parts[0]
    l2 = parts[1] if len(parts) > 1 else ""
    return l1, l2


class CoupangPartnersAPI:
    def __init__(self, access_key: Optional[str] = None, secret_key: Optional[str] = None) -> None:
        self.access_key = str(
            access_key
            or os.getenv("COUPANG_PARTNERS_ACCESS_KEY")
            or os.getenv("COUPANG_ACCESS_KEY", "")
        ).strip()
        self.secret_key = str(
            secret_key
            or os.getenv("COUPANG_PARTNERS_SECRET_KEY")
            or os.getenv("COUPANG_SECRET_KEY", "")
        ).strip()
        self.base_url = "https://api-gateway.coupang.com"

    def is_configured(self) -> bool:
        return bool(self.access_key and self.secret_key)

    def _auth_header(self, method: str, path: str, query: str) -> Dict[str, str]:
        signed_date = datetime.now(timezone.utc).strftime("%y%m%dT%H%M%SZ")
        message = f"{signed_date}{method.upper()}{path}{query}"
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        authorization = (
            "CEA algorithm=HmacSHA256, "
            f"access-key={self.access_key}, "
            f"signed-date={signed_date}, "
            f"signature={signature}"
        )
        return {"Authorization": authorization, "Content-Type": "application/json"}

    def search_products(self, keyword: str, limit: int = 10, sub_id: str = "modiba-blueocean") -> Dict[str, Any]:
        kw = str(keyword or "").strip()
        if not kw:
            return {"ok": False, "error": "empty_keyword", "rows": []}
        if not self.is_configured():
            return {"ok": False, "error": "missing_credentials", "rows": []}

        path = "/v2/providers/affiliate_open_api/apis/openapi/v1/products/search"
        # 문서: 상품 검색 limit 최대 10건/요청. Rate limit 별도(예: 1분당 50회 호출).
        params = {"keyword": kw, "limit": max(1, min(int(limit), 10)), "subId": sub_id}
        query = urlencode(params)
        headers = self._auth_header("GET", path, query)
        url = f"{self.base_url}{path}?{query}"

        try:
            resp = requests.get(url, headers=headers, timeout=20)
        except Exception as e:
            return {"ok": False, "error": f"network_error:{e}", "rows": []}

        if resp.status_code != 200:
            return {
                "ok": False,
                "status_code": int(resp.status_code),
                "error": f"http_{resp.status_code}",
                "body": resp.text[:400],
                "rows": [],
            }

        try:
            payload = resp.json()
        except Exception:
            return {"ok": False, "error": "invalid_json", "rows": []}

        data_block = (payload or {}).get("data") or {}
        product_data = data_block.get("productData") or []
        rows: List[Dict[str, Any]] = []
        for idx, p in enumerate(product_data, start=1):
            cat_raw = str(p.get("categoryName") or "")
            c_l1, c_l2 = coupang_category_name_to_l1_l2(cat_raw)
            rows.append(
                {
                    "idx": idx,
                    "keyword": kw,
                    "source": "api",
                    "title": str(p.get("productName") or ""),
                    "price": int(p.get("productPrice") or 0) if str(p.get("productPrice") or "").isdigit() else p.get("productPrice"),
                    # rating / review_count: Coupang Partners API 가 제공하지 않는 필드.
                    # None 으로 보존하여 Hybrid 크롤러가 채울 자리로 둔다.
                    "rating": p.get("rating"),
                    "review_count": p.get("reviewCount"),
                    "product_url": str(p.get("productUrl") or ""),
                    "is_rocket": bool(p.get("isRocket")) if p.get("isRocket") is not None else None,
                    # 신규 5개 필드 (실제 응답에 항상 포함)
                    "product_id": p.get("productId"),
                    "product_image": str(p.get("productImage") or ""),
                    "category_name": cat_raw,
                    "category_l1": c_l1,
                    "category_l2": c_l2,
                    "rank": int(p.get("rank") or idx),
                    "is_free_shipping": bool(p.get("isFreeShipping")) if p.get("isFreeShipping") is not None else None,
                }
            )
        # 응답 메타: rate-limit 분기 / 디버깅 / UI 노출용
        meta = {
            "rcode": str(payload.get("rCode") or "") if isinstance(payload, dict) else "",
            "rmessage": str(payload.get("rMessage") or "") if isinstance(payload, dict) else "",
            "landing_url": str(data_block.get("landingUrl") or "") if isinstance(data_block, dict) else "",
            "traceid": str(resp.headers.get("X-Trace-ID") or resp.headers.get("x-trace-id") or ""),
            "requestid": str(resp.headers.get("X-Request-ID") or resp.headers.get("x-request-id") or ""),
        }
        return {
            "ok": True,
            "rows": rows,
            "count": len(rows),
            "status_code": 200,
            "meta": meta,
        }

    def best_products_by_category(
        self,
        category_id: int,
        limit: int = 20,
        sub_id: str = "modiba-blueocean",
    ) -> Dict[str, Any]:
        cid = int(category_id or 0)
        if cid <= 0:
            return {"ok": False, "error": "invalid_category_id", "rows": []}
        if not self.is_configured():
            return {"ok": False, "error": "missing_credentials", "rows": []}

        path = f"/v2/providers/affiliate_open_api/apis/openapi/v1/products/bestcategories/{cid}"
        # 문서: bestcategories limit 기본 20, 최대 100
        params = {"limit": max(1, min(int(limit), 100)), "subId": sub_id}
        query = urlencode(params)
        headers = self._auth_header("GET", path, query)
        url = f"{self.base_url}{path}?{query}"

        try:
            resp = requests.get(url, headers=headers, timeout=20)
        except Exception as e:
            return {"ok": False, "error": f"network_error:{e}", "rows": []}

        if resp.status_code != 200:
            return {
                "ok": False,
                "status_code": int(resp.status_code),
                "error": f"http_{resp.status_code}",
                "body": resp.text[:400],
                "rows": [],
            }

        try:
            payload = resp.json()
        except Exception:
            return {"ok": False, "error": "invalid_json", "rows": []}

        data_raw = (payload or {}).get("data")
        # NOTE:
        # bestcategories 응답은 category_id/시점에 따라 data가
        # - list(product)
        # - dict(productData=[...])
        # 둘 다 올 수 있어 포맷을 유연하게 처리한다.
        if isinstance(data_raw, dict):
            product_data = data_raw.get("productData") or []
        elif isinstance(data_raw, list):
            product_data = data_raw
        else:
            product_data = []

        rcode = str((payload or {}).get("rCode") or "").strip()
        rmessage = str((payload or {}).get("rMessage") or "").strip()
        if rcode and rcode not in ("0",):
            return {
                "ok": False,
                "status_code": int(resp.status_code),
                "error": f"api_rcode_{rcode}",
                "body": rmessage[:400],
                "rows": [],
                "meta": {
                    "rcode": rcode,
                    "rmessage": rmessage,
                    "traceid": str(resp.headers.get("X-Trace-ID") or resp.headers.get("x-trace-id") or ""),
                    "requestid": str(resp.headers.get("X-Request-ID") or resp.headers.get("x-request-id") or ""),
                    "category_id": cid,
                },
            }

        rows: List[Dict[str, Any]] = []
        for idx, p in enumerate(product_data, start=1):
            cat_raw = str(p.get("categoryName") or "")
            c_l1, c_l2 = coupang_category_name_to_l1_l2(cat_raw)
            rows.append(
                {
                    "idx": idx,
                    "keyword": f"category:{cid}",
                    "source": "api_category_best",
                    "title": str(p.get("productName") or ""),
                    "price": int(p.get("productPrice") or 0) if str(p.get("productPrice") or "").isdigit() else p.get("productPrice"),
                    "rating": p.get("rating"),
                    "review_count": p.get("reviewCount"),
                    "product_url": str(p.get("productUrl") or ""),
                    "is_rocket": bool(p.get("isRocket")) if p.get("isRocket") is not None else None,
                    "product_id": p.get("productId"),
                    "product_image": str(p.get("productImage") or ""),
                    "category_name": cat_raw,
                    "category_l1": c_l1,
                    "category_l2": c_l2,
                    "rank": int(p.get("rank") or idx),
                    "is_free_shipping": bool(p.get("isFreeShipping")) if p.get("isFreeShipping") is not None else None,
                    "category_id": cid,
                }
            )
        meta = {
            "rcode": rcode,
            "rmessage": rmessage,
            "traceid": str(resp.headers.get("X-Trace-ID") or resp.headers.get("x-trace-id") or ""),
            "requestid": str(resp.headers.get("X-Request-ID") or resp.headers.get("x-request-id") or ""),
            "category_id": cid,
        }
        return {
            "ok": True,
            "rows": rows,
            "count": len(rows),
            "status_code": 200,
            "meta": meta,
        }

    def goldbox_products(
        self,
        limit: int = 20,
        sub_id: str = "modiba-blueocean",
    ) -> Dict[str, Any]:
        """
        GET .../products/goldbox — 문서상 매일 오전 갱신 특가 피드.
        응답 data 형식은 bestcategories 와 유사하게 list 또는 dict(productData) 가능성 있음.
        """
        if not self.is_configured():
            return {"ok": False, "error": "missing_credentials", "rows": []}

        path = "/v2/providers/affiliate_open_api/apis/openapi/v1/products/goldbox"
        params = {"limit": max(1, min(int(limit), 100)), "subId": sub_id}
        query = urlencode(params)
        headers = self._auth_header("GET", path, query)
        url = f"{self.base_url}{path}?{query}"

        try:
            resp = requests.get(url, headers=headers, timeout=20)
        except Exception as e:
            return {"ok": False, "error": f"network_error:{e}", "rows": []}

        if resp.status_code != 200:
            return {
                "ok": False,
                "status_code": int(resp.status_code),
                "error": f"http_{resp.status_code}",
                "body": resp.text[:400],
                "rows": [],
            }

        try:
            payload = resp.json()
        except Exception:
            return {"ok": False, "error": "invalid_json", "rows": []}

        data_raw = (payload or {}).get("data")
        if isinstance(data_raw, dict):
            product_data = data_raw.get("productData") or []
        elif isinstance(data_raw, list):
            product_data = data_raw
        else:
            product_data = []

        rcode = str((payload or {}).get("rCode") or "").strip()
        rmessage = str((payload or {}).get("rMessage") or "").strip()
        if rcode and rcode not in ("0",):
            return {
                "ok": False,
                "status_code": int(resp.status_code),
                "error": f"api_rcode_{rcode}",
                "body": rmessage[:400],
                "rows": [],
                "meta": {
                    "rcode": rcode,
                    "rmessage": rmessage,
                    "traceid": str(resp.headers.get("X-Trace-ID") or resp.headers.get("x-trace-id") or ""),
                    "requestid": str(resp.headers.get("X-Request-ID") or resp.headers.get("x-request-id") or ""),
                    "feed": "goldbox",
                },
            }

        rows: List[Dict[str, Any]] = []
        for idx, p in enumerate(product_data, start=1):
            cat_raw = str(p.get("categoryName") or "")
            c_l1, c_l2 = coupang_category_name_to_l1_l2(cat_raw)
            rows.append(
                {
                    "idx": idx,
                    "keyword": "goldbox",
                    "source": "api_goldbox",
                    "title": str(p.get("productName") or ""),
                    "price": int(p.get("productPrice") or 0)
                    if str(p.get("productPrice") or "").isdigit()
                    else p.get("productPrice"),
                    "rating": p.get("rating"),
                    "review_count": p.get("reviewCount"),
                    "product_url": str(p.get("productUrl") or ""),
                    "is_rocket": bool(p.get("isRocket")) if p.get("isRocket") is not None else None,
                    "product_id": p.get("productId"),
                    "product_image": str(p.get("productImage") or ""),
                    "category_name": cat_raw,
                    "category_l1": c_l1,
                    "category_l2": c_l2,
                    "rank": int(p.get("rank") or idx),
                    "is_free_shipping": bool(p.get("isFreeShipping")) if p.get("isFreeShipping") is not None else None,
                    "category_id": None,
                }
            )
        meta = {
            "rcode": rcode,
            "rmessage": rmessage,
            "traceid": str(resp.headers.get("X-Trace-ID") or resp.headers.get("x-trace-id") or ""),
            "requestid": str(resp.headers.get("X-Request-ID") or resp.headers.get("x-request-id") or ""),
            "feed": "goldbox",
        }
        return {
            "ok": True,
            "rows": rows,
            "count": len(rows),
            "status_code": 200,
            "meta": meta,
        }


# ---------------------------------------------------------------------------
# Throttler (Phase C: Coupang API stabilization)
# ---------------------------------------------------------------------------
# 정책 요약 (사용자 합의 2026-05-08):
#   - Master kill switch: COUPANG_API_ENABLED (기본 'off'). 명시적으로 'on'일 때만 호출.
#   - Rolling 60-min window 호출 한도: COUPANG_API_RPH (기본 5)
#   - 호출 간 최소 간격: COUPANG_API_MIN_INTERVAL_SEC (기본 720s = 12분)
#   - 1회 실행당 최대 호출: COUPANG_API_MAX_CALLS_PER_RUN (기본 5)
#   - 캐시 TTL: COUPANG_API_CACHE_TTL_HOURS (기본 48시간)
#   - HTTP 429 / 응답 본문에 '호출 횟수 초과' 류 감지 → 즉시 latch, 프로세스 살아있는
#     동안 모든 추가 호출 차단 (수동 reset 또는 프로세스 재기동 전까지)
#   - 응답 dict shape는 기존 search_products()의 strict superset.
# 절대 변경 금지: 기존 CoupangPartnersAPI 의 시그니처 / 응답 키.

_KST = timezone(timedelta(hours=9))
_COUPANG_API_HARD_MAX_RPH = 10


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on", "y")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(float(raw))
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _is_rate_limit_response(result: Dict[str, Any]) -> bool:
    """쿠팡 측 호출 횟수 초과 / 레이트 리밋 응답을 감지."""
    if not isinstance(result, dict):
        return False
    sc = result.get("status_code")
    if sc == 429:
        return True
    err = str(result.get("error") or "").lower()
    body = str(result.get("body") or "").lower()
    blob = f"{err}|{body}"
    keywords = (
        "rate limit",
        "too many",
        "throttle",
        "호출 횟수 초과",
        "호출횟수 초과",
        "quota",
        "exceed",
    )
    return any(k in blob for k in keywords)


class CoupangPartnersThrottler:
    """
    스레드 안전한 쿠팡 파트너스 API 게이트.

    - 기존 CoupangPartnersAPI 를 합성(composition)으로 감싼다.
    - search_products(keyword, limit, sub_id) 시그니처 호환.
    - 응답은 기존 shape의 상위 호환:
        성공:  {"ok": True, "rows": [...], "count": N, "status_code": 200,
                "cached": bool, "rate_limited": False}
        스킵:  {"ok": False, "rows": [], "skipped": True,
                "skip_reason": "<reason>", "rate_limited": <bool>}
        실패:  기존 dict + {"cached": False, "rate_limited": <bool>}
    """

    _CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
    _CALLS: List[float] = []
    _LAST_CALL_TS: float = 0.0
    _RATE_LIMITED: bool = False
    _LOCK = threading.RLock()
    _RUN_CALLS: int = 0
    _RUN_CACHED: int = 0
    _RUN_SKIPPED: int = 0

    def __init__(
        self,
        api: Optional[CoupangPartnersAPI] = None,
        *,
        log_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self._api = api or CoupangPartnersAPI()
        self._log_cb = log_callback

    @staticmethod
    def _read_cfg() -> Dict[str, Any]:
        requested_rph = max(1, _env_int("COUPANG_API_RPH", 5))
        return {
            "enabled": _env_bool("COUPANG_API_ENABLED", default=False),
            # 안전장치: 환경변수 실수로 크게 잡아도 절대 10/h를 넘기지 않는다.
            "max_per_hour": min(requested_rph, _COUPANG_API_HARD_MAX_RPH),
            "min_interval_sec": max(0.0, _env_float("COUPANG_API_MIN_INTERVAL_SEC", 720.0)),
            "max_calls_per_run": max(1, _env_int("COUPANG_API_MAX_CALLS_PER_RUN", 5)),
            "cache_ttl_sec": max(60, _env_int("COUPANG_API_CACHE_TTL_HOURS", 48) * 3600),
            "log_path": os.getenv("COUPANG_API_LOG_PATH", "").strip(),
        }

    def is_configured(self) -> bool:
        return self._api.is_configured()

    @classmethod
    def reset_run_stats(cls) -> None:
        with cls._LOCK:
            cls._RUN_CALLS = 0
            cls._RUN_CACHED = 0
            cls._RUN_SKIPPED = 0

    @classmethod
    def reset_rate_limit_latch(cls) -> None:
        """수동 복구용. 운영 중에는 사용하지 말 것 (프로세스 재기동이 안전)."""
        with cls._LOCK:
            cls._RATE_LIMITED = False

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        cfg = cls._read_cfg()
        with cls._LOCK:
            now = time.time()
            cls._CALLS = [t for t in cls._CALLS if now - t < 3600]
            min_iv = float(cfg["min_interval_sec"])
            wait_next = 0.0
            if cls._LAST_CALL_TS > 0:
                wait_next = max(0.0, min_iv - (now - cls._LAST_CALL_TS))
            return {
                "enabled": bool(cfg["enabled"]),
                "rate_limited": bool(cls._RATE_LIMITED),
                "current_rph": int(len(cls._CALLS)),
                "max_rph": int(cfg["max_per_hour"]),
                "min_interval_sec": float(cfg["min_interval_sec"]),
                "seconds_until_next_call": round(wait_next, 1),
                "max_calls_per_run": int(cfg["max_calls_per_run"]),
                "cache_size": int(len(cls._CACHE)),
                "run_call_count": int(cls._RUN_CALLS),
                "run_cached_hit_count": int(cls._RUN_CACHED),
                "run_skipped_count": int(cls._RUN_SKIPPED),
                "last_call_kst": (
                    datetime.fromtimestamp(cls._LAST_CALL_TS, tz=_KST).strftime("%Y-%m-%d %H:%M:%S KST")
                    if cls._LAST_CALL_TS > 0
                    else ""
                ),
            }

    @classmethod
    def _skip_payload(cls, reason: str, cfg: Dict[str, Any], now: float) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "ok": False,
            "rows": [],
            "skipped": True,
            "skip_reason": reason,
            "cached": False,
            "rate_limited": cls._RATE_LIMITED,
        }
        if reason == "min_interval_not_met":
            ws = max(0.0, float(cfg["min_interval_sec"]) - (now - cls._LAST_CALL_TS))
            out["wait_seconds"] = round(ws, 1)
            out["min_interval_sec_config"] = float(cfg["min_interval_sec"])
        return out

    def _emit(self, event: str, **kw: Any) -> None:
        payload = {
            "event": event,
            "ts_kst": datetime.now(_KST).strftime("%Y-%m-%d %H:%M:%S KST"),
            "ts_epoch": int(time.time()),
            **kw,
        }
        if self._log_cb is not None:
            try:
                self._log_cb(dict(payload))
            except Exception:
                pass
        log_path = os.getenv("COUPANG_API_LOG_PATH", "").strip()
        if log_path:
            try:
                os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
            except Exception:
                pass

    @staticmethod
    def _cache_key(keyword: str) -> str:
        return "".join(str(keyword or "").split()).lower()

    def _gate(self, cfg: Dict[str, Any]) -> Tuple[bool, str]:
        if not cfg["enabled"]:
            return False, "throttle_disabled"
        if not self._api.is_configured():
            return False, "missing_credentials"
        if CoupangPartnersThrottler._RATE_LIMITED:
            return False, "rate_limit_latched"
        if CoupangPartnersThrottler._RUN_CALLS >= cfg["max_calls_per_run"]:
            return False, "max_calls_per_run_reached"
        now = time.time()
        if now - CoupangPartnersThrottler._LAST_CALL_TS < cfg["min_interval_sec"]:
            return False, "min_interval_not_met"
        CoupangPartnersThrottler._CALLS = [
            t for t in CoupangPartnersThrottler._CALLS if now - t < 3600
        ]
        if len(CoupangPartnersThrottler._CALLS) >= cfg["max_per_hour"]:
            return False, "rolling_hour_limit_reached"
        return True, ""

    def search_products(
        self,
        keyword: str,
        limit: int = 10,
        sub_id: str = "modiba-blueocean",
    ) -> Dict[str, Any]:
        kw = str(keyword or "").strip()
        if not kw:
            return {
                "ok": False,
                "rows": [],
                "error": "empty_keyword",
                "skipped": True,
                "skip_reason": "empty_keyword",
                "cached": False,
                "rate_limited": False,
            }

        cfg = self._read_cfg()
        cache_key = self._cache_key(kw)

        with CoupangPartnersThrottler._LOCK:
            cached = CoupangPartnersThrottler._CACHE.get(cache_key)
            now = time.time()
            if cached and (now - cached[0]) < cfg["cache_ttl_sec"]:
                CoupangPartnersThrottler._RUN_CACHED += 1
                stats_snapshot = {
                    "current_rph": len(
                        [t for t in CoupangPartnersThrottler._CALLS if now - t < 3600]
                    ),
                }
                self._emit("cached_hit", keyword=kw, **stats_snapshot)
                result = dict(cached[1])
                result["cached"] = True
                result["rate_limited"] = False
                return result

            allowed, reason = self._gate(cfg)
            if not allowed:
                CoupangPartnersThrottler._RUN_SKIPPED += 1
                self._emit(
                    "call_skipped",
                    keyword=kw,
                    reason=reason,
                    current_rph=len(
                        [t for t in CoupangPartnersThrottler._CALLS if now - t < 3600]
                    ),
                    rate_limited=CoupangPartnersThrottler._RATE_LIMITED,
                )
                return CoupangPartnersThrottler._skip_payload(reason, cfg, now)

            call_ts = time.time()
            CoupangPartnersThrottler._LAST_CALL_TS = call_ts
            CoupangPartnersThrottler._CALLS.append(call_ts)
            CoupangPartnersThrottler._RUN_CALLS += 1
            current_count = len(CoupangPartnersThrottler._CALLS)
            current_run = CoupangPartnersThrottler._RUN_CALLS

        self._emit(
            "api_call_start",
            keyword=kw,
            current_rph=current_count,
            run_call_count=current_run,
        )
        result = self._api.search_products(kw, limit=limit, sub_id=sub_id)

        with CoupangPartnersThrottler._LOCK:
            if _is_rate_limit_response(result):
                CoupangPartnersThrottler._RATE_LIMITED = True
                self._emit(
                    "rate_limit_detected",
                    keyword=kw,
                    status_code=result.get("status_code"),
                    error=result.get("error"),
                )
                result = dict(result)
                result["cached"] = False
                result["rate_limited"] = True
                return result

            if result.get("ok"):
                CoupangPartnersThrottler._CACHE[cache_key] = (time.time(), dict(result))
                self._emit(
                    "api_call_ok",
                    keyword=kw,
                    items=int(result.get("count") or 0),
                )
            else:
                self._emit(
                    "api_call_fail",
                    keyword=kw,
                    error=result.get("error"),
                    status_code=result.get("status_code"),
                )

            result = dict(result)
            result["cached"] = False
            result["rate_limited"] = False
            return result

    def best_products_by_category(
        self,
        category_id: int,
        limit: int = 20,
        sub_id: str = "modiba-blueocean",
    ) -> Dict[str, Any]:
        cid = int(category_id or 0)
        if cid <= 0:
            return {
                "ok": False,
                "rows": [],
                "error": "invalid_category_id",
                "skipped": True,
                "skip_reason": "invalid_category_id",
                "cached": False,
                "rate_limited": False,
            }

        cfg = self._read_cfg()
        cache_key = f"catbest:{cid}:{max(1, min(int(limit), 100))}"
        with CoupangPartnersThrottler._LOCK:
            cached = CoupangPartnersThrottler._CACHE.get(cache_key)
            now = time.time()
            if cached and (now - cached[0]) < cfg["cache_ttl_sec"]:
                CoupangPartnersThrottler._RUN_CACHED += 1
                result = dict(cached[1])
                result["cached"] = True
                result["rate_limited"] = False
                return result
            allowed, reason = self._gate(cfg)
            if not allowed:
                CoupangPartnersThrottler._RUN_SKIPPED += 1
                return CoupangPartnersThrottler._skip_payload(reason, cfg, now)
            call_ts = time.time()
            CoupangPartnersThrottler._LAST_CALL_TS = call_ts
            CoupangPartnersThrottler._CALLS.append(call_ts)
            CoupangPartnersThrottler._RUN_CALLS += 1

        result = self._api.best_products_by_category(cid, limit=limit, sub_id=sub_id)
        with CoupangPartnersThrottler._LOCK:
            if _is_rate_limit_response(result):
                CoupangPartnersThrottler._RATE_LIMITED = True
                result = dict(result)
                result["cached"] = False
                result["rate_limited"] = True
                return result
            if result.get("ok"):
                CoupangPartnersThrottler._CACHE[cache_key] = (time.time(), dict(result))
            result = dict(result)
            result["cached"] = False
            result["rate_limited"] = False
            return result

    def goldbox_products(
        self,
        limit: int = 20,
        sub_id: str = "modiba-blueocean",
    ) -> Dict[str, Any]:
        cfg = self._read_cfg()
        cache_key = f"goldbox:{max(1, min(int(limit), 100))}"
        with CoupangPartnersThrottler._LOCK:
            cached = CoupangPartnersThrottler._CACHE.get(cache_key)
            now = time.time()
            if cached and (now - cached[0]) < cfg["cache_ttl_sec"]:
                CoupangPartnersThrottler._RUN_CACHED += 1
                result = dict(cached[1])
                result["cached"] = True
                result["rate_limited"] = False
                return result
            allowed, reason = self._gate(cfg)
            if not allowed:
                CoupangPartnersThrottler._RUN_SKIPPED += 1
                return CoupangPartnersThrottler._skip_payload(reason, cfg, now)
            call_ts = time.time()
            CoupangPartnersThrottler._LAST_CALL_TS = call_ts
            CoupangPartnersThrottler._CALLS.append(call_ts)
            CoupangPartnersThrottler._RUN_CALLS += 1

        result = self._api.goldbox_products(limit=limit, sub_id=sub_id)
        with CoupangPartnersThrottler._LOCK:
            if _is_rate_limit_response(result):
                CoupangPartnersThrottler._RATE_LIMITED = True
                result = dict(result)
                result["cached"] = False
                result["rate_limited"] = True
                return result
            if result.get("ok"):
                CoupangPartnersThrottler._CACHE[cache_key] = (time.time(), dict(result))
            result = dict(result)
            result["cached"] = False
            result["rate_limited"] = False
            return result


_DEFAULT_THROTTLER: Optional[CoupangPartnersThrottler] = None
_DEFAULT_THROTTLER_LOCK = threading.Lock()


def get_default_throttler() -> CoupangPartnersThrottler:
    """프로세스 단일 throttler 싱글톤. 모든 호출 사이트가 동일 인스턴스를 공유해야
    rolling-window/카운터/캐시가 일관되게 적용된다."""
    global _DEFAULT_THROTTLER
    if _DEFAULT_THROTTLER is not None:
        return _DEFAULT_THROTTLER
    with _DEFAULT_THROTTLER_LOCK:
        if _DEFAULT_THROTTLER is None:
            _DEFAULT_THROTTLER = CoupangPartnersThrottler()
        return _DEFAULT_THROTTLER
