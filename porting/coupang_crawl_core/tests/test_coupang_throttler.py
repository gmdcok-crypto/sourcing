"""CoupangPartnersThrottler 단위 테스트.

원칙 (modiba-stability):
  - **절대로 실제 네트워크/Coupang API 를 호출하지 않는다.**
  - requests.get 는 monkeypatch 로 차단한다.
  - CoupangPartnersAPI.search_products 는 통째로 모킹한다.
  - 클래스 스코프 상태(_CACHE/_CALLS/_LAST_CALL_TS/_RATE_LIMITED/_RUN_*)는
    각 테스트 시작 시 리셋한다.

실행:
  pytest tests/test_coupang_throttler.py -v
"""
from __future__ import annotations

import os
import sys
import threading
import time
import unittest
from typing import Any, Callable, Dict, List
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from coupang_partners_api import (  # noqa: E402
    CoupangPartnersAPI,
    CoupangPartnersThrottler,
    _is_rate_limit_response,
    coupang_category_name_to_l1_l2,
    get_default_throttler,
)


def _reset_throttler_state() -> None:
    CoupangPartnersThrottler._CACHE.clear()
    CoupangPartnersThrottler._CALLS.clear()
    CoupangPartnersThrottler._LAST_CALL_TS = 0.0
    CoupangPartnersThrottler._RATE_LIMITED = False
    CoupangPartnersThrottler.reset_run_stats()


class _StubAPI(CoupangPartnersAPI):
    """네트워크 차단 + 호출 카운팅 스텁."""

    def __init__(self, responses: List[Dict[str, Any]] | None = None) -> None:
        self.access_key = "TEST_ACCESS"
        self.secret_key = "TEST_SECRET"
        self.base_url = "https://example.invalid"
        self._responses = list(responses or [])
        self._idx = 0
        self.call_keywords: List[str] = []

    def search_products(self, keyword: str, limit: int = 10, sub_id: str = "x") -> Dict[str, Any]:
        self.call_keywords.append(keyword)
        if self._responses and self._idx < len(self._responses):
            r = dict(self._responses[self._idx])
        else:
            r = {"ok": True, "rows": [], "count": 0, "status_code": 200}
        self._idx += 1
        return r


# 가짜 환경변수: 모든 테스트는 enabled 를 명시적으로 켠다.
def _env(**overrides: str) -> Dict[str, str]:
    base = {
        "COUPANG_API_ENABLED": "on",
        "COUPANG_API_RPH": "5",
        "COUPANG_API_MIN_INTERVAL_SEC": "0",  # 인터벌은 별도 테스트에서 설정
        "COUPANG_API_MAX_CALLS_PER_RUN": "5",
        "COUPANG_API_CACHE_TTL_HOURS": "48",
        "COUPANG_API_TOP_N": "5",
        "COUPANG_API_LOG_PATH": "",
        "COUPANG_ACCESS_KEY": "TEST",
        "COUPANG_SECRET_KEY": "TEST",
    }
    base.update(overrides)
    return base


class TestRateLimitDetector(unittest.TestCase):
    def test_429_status(self) -> None:
        self.assertTrue(_is_rate_limit_response({"status_code": 429}))

    def test_korean_message(self) -> None:
        self.assertTrue(_is_rate_limit_response({"body": "[{'rCode': 1, 'rMessage': '호출 횟수 초과'}]"}))

    def test_too_many_in_error(self) -> None:
        self.assertTrue(_is_rate_limit_response({"error": "http_429 too many"}))

    def test_normal_response(self) -> None:
        self.assertFalse(_is_rate_limit_response({"ok": True, "rows": []}))

    def test_other_error(self) -> None:
        self.assertFalse(_is_rate_limit_response({"ok": False, "error": "network_error"}))


class TestKillSwitch(unittest.TestCase):
    def setUp(self) -> None:
        _reset_throttler_state()

    def test_default_off_blocks_calls(self) -> None:
        with patch.dict(os.environ, _env(COUPANG_API_ENABLED=""), clear=False):
            os.environ.pop("COUPANG_API_ENABLED", None)
            stub = _StubAPI([{"ok": True, "rows": [{"price": 1000, "review_count": 10}], "count": 1, "status_code": 200}])
            th = CoupangPartnersThrottler(api=stub)
            rs = th.search_products("kw")
            self.assertTrue(rs.get("skipped"))
            self.assertEqual(rs.get("skip_reason"), "throttle_disabled")
            self.assertEqual(stub.call_keywords, [])

    def test_explicit_off(self) -> None:
        with patch.dict(os.environ, _env(COUPANG_API_ENABLED="off"), clear=False):
            stub = _StubAPI()
            th = CoupangPartnersThrottler(api=stub)
            rs = th.search_products("kw")
            self.assertTrue(rs.get("skipped"))
            self.assertEqual(rs.get("skip_reason"), "throttle_disabled")
            self.assertEqual(stub.call_keywords, [])

    def test_missing_credentials(self) -> None:
        with patch.dict(os.environ, _env(), clear=False):
            stub = _StubAPI()
            stub.access_key = ""
            stub.secret_key = ""
            th = CoupangPartnersThrottler(api=stub)
            rs = th.search_products("kw")
            self.assertTrue(rs.get("skipped"))
            self.assertEqual(rs.get("skip_reason"), "missing_credentials")


class TestRollingHourLimit(unittest.TestCase):
    def setUp(self) -> None:
        _reset_throttler_state()

    def test_rph_5_caps_calls(self) -> None:
        env = _env(COUPANG_API_RPH="5", COUPANG_API_MIN_INTERVAL_SEC="0", COUPANG_API_MAX_CALLS_PER_RUN="100")
        with patch.dict(os.environ, env, clear=False):
            stub = _StubAPI(
                [{"ok": True, "rows": [], "count": 0, "status_code": 200} for _ in range(20)]
            )
            th = CoupangPartnersThrottler(api=stub)
            results = []
            for i in range(10):
                results.append(th.search_products(f"kw_{i}"))
            actual_calls = sum(1 for r in results if not r.get("skipped"))
            skipped = [r for r in results if r.get("skipped")]
            self.assertEqual(actual_calls, 5)
            self.assertEqual(len(skipped), 5)
            self.assertTrue(all(r.get("skip_reason") == "rolling_hour_limit_reached" for r in skipped))
            self.assertEqual(len(stub.call_keywords), 5)

    def test_rph_hard_cap_10_even_if_env_higher(self) -> None:
        env = _env(COUPANG_API_RPH="999", COUPANG_API_MIN_INTERVAL_SEC="0", COUPANG_API_MAX_CALLS_PER_RUN="100")
        with patch.dict(os.environ, env, clear=False):
            stub = _StubAPI(
                [{"ok": True, "rows": [], "count": 0, "status_code": 200} for _ in range(30)]
            )
            th = CoupangPartnersThrottler(api=stub)
            results = []
            for i in range(11):
                results.append(th.search_products(f"kw_{i}"))
            actual_calls = sum(1 for r in results if not r.get("skipped"))
            skipped = [r for r in results if r.get("skipped")]
            self.assertEqual(actual_calls, 10)
            self.assertEqual(len(skipped), 1)
            self.assertEqual(skipped[0].get("skip_reason"), "rolling_hour_limit_reached")
            self.assertEqual(len(stub.call_keywords), 10)


class TestMinInterval(unittest.TestCase):
    def setUp(self) -> None:
        _reset_throttler_state()

    def test_interval_blocks_immediate_second_call(self) -> None:
        env = _env(COUPANG_API_RPH="100", COUPANG_API_MIN_INTERVAL_SEC="3600", COUPANG_API_MAX_CALLS_PER_RUN="10")
        with patch.dict(os.environ, env, clear=False):
            stub = _StubAPI([{"ok": True, "rows": [], "count": 0, "status_code": 200} for _ in range(5)])
            th = CoupangPartnersThrottler(api=stub)
            r1 = th.search_products("a")
            r2 = th.search_products("b")
            self.assertFalse(r1.get("skipped"))
            self.assertTrue(r2.get("skipped"))
            self.assertEqual(r2.get("skip_reason"), "min_interval_not_met")
            self.assertEqual(len(stub.call_keywords), 1)


class TestMaxCallsPerRun(unittest.TestCase):
    def setUp(self) -> None:
        _reset_throttler_state()

    def test_run_cap(self) -> None:
        env = _env(COUPANG_API_RPH="100", COUPANG_API_MIN_INTERVAL_SEC="0", COUPANG_API_MAX_CALLS_PER_RUN="3")
        with patch.dict(os.environ, env, clear=False):
            stub = _StubAPI([{"ok": True, "rows": [], "count": 0, "status_code": 200} for _ in range(10)])
            th = CoupangPartnersThrottler(api=stub)
            for i in range(6):
                th.search_products(f"kw_{i}")
            self.assertEqual(len(stub.call_keywords), 3)

    def test_reset_run_stats_allows_more(self) -> None:
        env = _env(COUPANG_API_RPH="100", COUPANG_API_MIN_INTERVAL_SEC="0", COUPANG_API_MAX_CALLS_PER_RUN="2")
        with patch.dict(os.environ, env, clear=False):
            stub = _StubAPI([{"ok": True, "rows": [], "count": 0, "status_code": 200} for _ in range(10)])
            th = CoupangPartnersThrottler(api=stub)
            for i in range(3):
                th.search_products(f"a_{i}")
            self.assertEqual(len(stub.call_keywords), 2)
            CoupangPartnersThrottler.reset_run_stats()
            for i in range(3):
                th.search_products(f"b_{i}")
            self.assertEqual(len(stub.call_keywords), 4)


class TestCache(unittest.TestCase):
    def setUp(self) -> None:
        _reset_throttler_state()

    def test_cached_hit_does_not_call_api(self) -> None:
        env = _env(COUPANG_API_RPH="100", COUPANG_API_MIN_INTERVAL_SEC="0", COUPANG_API_MAX_CALLS_PER_RUN="100")
        with patch.dict(os.environ, env, clear=False):
            stub = _StubAPI([
                {"ok": True, "rows": [{"price": 1000, "review_count": 5}], "count": 1, "status_code": 200},
            ])
            th = CoupangPartnersThrottler(api=stub)
            r1 = th.search_products("텀블러")
            r2 = th.search_products("텀블러")
            self.assertEqual(len(stub.call_keywords), 1)
            self.assertFalse(r1.get("cached"))
            self.assertTrue(r2.get("cached"))
            self.assertEqual(int(r2.get("count") or 0), 1)


class TestRateLimitLatch(unittest.TestCase):
    def setUp(self) -> None:
        _reset_throttler_state()

    def test_429_latches_and_blocks_all_following_calls(self) -> None:
        env = _env(COUPANG_API_RPH="100", COUPANG_API_MIN_INTERVAL_SEC="0", COUPANG_API_MAX_CALLS_PER_RUN="100")
        with patch.dict(os.environ, env, clear=False):
            stub = _StubAPI([
                {"ok": False, "status_code": 429, "error": "http_429", "rows": []},
                {"ok": True, "rows": [], "count": 0, "status_code": 200},
                {"ok": True, "rows": [], "count": 0, "status_code": 200},
            ])
            th = CoupangPartnersThrottler(api=stub)
            r1 = th.search_products("a")
            r2 = th.search_products("b")
            r3 = th.search_products("c")
            self.assertTrue(r1.get("rate_limited"))
            self.assertTrue(r2.get("skipped"))
            self.assertEqual(r2.get("skip_reason"), "rate_limit_latched")
            self.assertTrue(r3.get("skipped"))
            self.assertEqual(len(stub.call_keywords), 1)

    def test_korean_rate_limit_message_latches(self) -> None:
        env = _env(COUPANG_API_RPH="100", COUPANG_API_MIN_INTERVAL_SEC="0", COUPANG_API_MAX_CALLS_PER_RUN="100")
        with patch.dict(os.environ, env, clear=False):
            stub = _StubAPI([
                {"ok": False, "status_code": 200, "body": "[{'rCode': 1, 'rMessage': '호출 횟수 초과'}]", "rows": []},
                {"ok": True, "rows": [], "count": 0, "status_code": 200},
            ])
            th = CoupangPartnersThrottler(api=stub)
            r1 = th.search_products("a")
            r2 = th.search_products("b")
            self.assertTrue(r1.get("rate_limited"))
            self.assertTrue(r2.get("skipped"))
            self.assertEqual(len(stub.call_keywords), 1)


class TestEmptyKeyword(unittest.TestCase):
    def setUp(self) -> None:
        _reset_throttler_state()

    def test_blank_keyword_skipped_no_count(self) -> None:
        env = _env()
        with patch.dict(os.environ, env, clear=False):
            stub = _StubAPI()
            th = CoupangPartnersThrottler(api=stub)
            rs = th.search_products("   ")
            self.assertTrue(rs.get("skipped"))
            self.assertEqual(rs.get("skip_reason"), "empty_keyword")
            self.assertEqual(stub.call_keywords, [])
            stats = CoupangPartnersThrottler.get_stats()
            self.assertEqual(stats.get("run_call_count"), 0)


class TestNetworkBlocked(unittest.TestCase):
    """안전 가드: 어떤 시나리오에서도 requests.get 이 호출되지 않아야 한다."""

    def setUp(self) -> None:
        _reset_throttler_state()

    def test_no_real_http(self) -> None:
        env = _env()
        with patch.dict(os.environ, env, clear=False):
            with patch("coupang_partners_api.requests.get") as mock_get:
                stub = _StubAPI([{"ok": True, "rows": [], "count": 0, "status_code": 200}])
                th = CoupangPartnersThrottler(api=stub)
                th.search_products("kw")
                mock_get.assert_not_called()


class TestThreadSafety(unittest.TestCase):
    def setUp(self) -> None:
        _reset_throttler_state()

    def test_concurrent_calls_respect_rph(self) -> None:
        env = _env(
            COUPANG_API_RPH="5",
            COUPANG_API_MIN_INTERVAL_SEC="0",
            COUPANG_API_MAX_CALLS_PER_RUN="100",
        )
        with patch.dict(os.environ, env, clear=False):
            stub = _StubAPI([{"ok": True, "rows": [], "count": 0, "status_code": 200} for _ in range(50)])
            th = CoupangPartnersThrottler(api=stub)
            errors: List[str] = []

            def _worker(i: int) -> None:
                try:
                    th.search_products(f"kw_{i}")
                except Exception as e:
                    errors.append(str(e))

            threads = [threading.Thread(target=_worker, args=(i,)) for i in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(errors, [])
            self.assertEqual(len(stub.call_keywords), 5)


class TestSingleton(unittest.TestCase):
    def test_get_default_throttler_is_singleton(self) -> None:
        a = get_default_throttler()
        b = get_default_throttler()
        self.assertIs(a, b)


# ---------------------------------------------------------------------------
# Phase C-2 (2026-05-09): search_products 응답 필드 확장 + 점수식 v2
# ---------------------------------------------------------------------------


class TestCoupangCategoryNameSplit(unittest.TestCase):
    def test_empty(self) -> None:
        self.assertEqual(coupang_category_name_to_l1_l2(""), ("", ""))

    def test_single_label(self) -> None:
        self.assertEqual(coupang_category_name_to_l1_l2("생활용품"), ("생활용품", ""))

    def test_two_levels(self) -> None:
        self.assertEqual(
            coupang_category_name_to_l1_l2("생활용품 > 욕실용품"),
            ("생활용품", "욕실용품"),
        )

    def test_more_than_two_ignored(self) -> None:
        self.assertEqual(
            coupang_category_name_to_l1_l2("A > B > C > D"),
            ("A", "B"),
        )


class _RealParseAPI(CoupangPartnersAPI):
    """실제 search_products 파싱 로직을 재사용하기 위해 requests.get 만 모킹."""

    def __init__(self) -> None:
        self.access_key = "TEST_ACCESS"
        self.secret_key = "TEST_SECRET"
        self.base_url = "https://example.invalid"


def _build_fake_payload(num_products: int = 5) -> Dict[str, Any]:
    return {
        "rCode": "0",
        "rMessage": "게시글 작성 시 파트너스 활동 공시 안내",
        "data": {
            "landingUrl": "https://link.coupang.com/re/AFFSRP?lptag=AF...",
            "productData": [
                {
                    "productId": 1000 + i,
                    "productName": f"테스트 상품 {i+1}",
                    "productPrice": 10000 + i * 5000,
                    "productImage": f"https://img.example.invalid/{i+1}.jpg",
                    "productUrl": f"https://link.coupang.com/re/AFFSDP?pageKey={1000+i}",
                    "categoryName": "생활용품",
                    "keyword": "테스트키워드",
                    "rank": i + 1,
                    "isRocket": (i % 2 == 1),
                    "isFreeShipping": (i % 2 == 0),
                }
                for i in range(num_products)
            ],
        },
    }


class _FakeResponse:
    def __init__(self, payload: Dict[str, Any], status_code: int = 200, headers: Dict[str, str] | None = None) -> None:
        import json as _json
        self._payload = payload
        self.status_code = status_code
        self.headers = dict(headers or {"X-Trace-ID": "trace-abc", "X-Request-ID": "req-xyz"})
        self.text = _json.dumps(payload, ensure_ascii=False)

    def json(self) -> Dict[str, Any]:
        return self._payload


class TestSearchProductsExpandedFields(unittest.TestCase):
    """search_products 가 신규 5개 필드 + meta 를 정상 매핑하는지 검증."""

    def setUp(self) -> None:
        _reset_throttler_state()

    def test_new_fields_present_in_rows(self) -> None:
        payload = _build_fake_payload(num_products=3)
        api = _RealParseAPI()
        with patch("coupang_partners_api.requests.get",
                  return_value=_FakeResponse(payload, 200, {"X-Trace-ID": "trace-1", "X-Request-ID": "req-1"})):
            rs = api.search_products("테스트키워드", limit=3)

        self.assertTrue(rs["ok"])
        self.assertEqual(rs["count"], 3)
        legacy_keys = {"idx", "keyword", "source", "title", "price", "rating", "review_count", "product_url", "is_rocket"}
        new_keys = {"product_id", "product_image", "category_name", "category_l1", "category_l2", "rank", "is_free_shipping"}
        for row in rs["rows"]:
            for k in legacy_keys:
                self.assertIn(k, row, f"legacy key '{k}' missing")
            for k in new_keys:
                self.assertIn(k, row, f"new key '{k}' missing")

        first = rs["rows"][0]
        self.assertEqual(first["product_id"], 1000)
        self.assertEqual(first["category_name"], "생활용품")
        self.assertEqual(first["category_l1"], "생활용품")
        self.assertEqual(first["category_l2"], "")
        self.assertEqual(first["rank"], 1)
        self.assertEqual(first["is_free_shipping"], True)
        self.assertEqual(first["is_rocket"], False)
        self.assertIsNone(first["rating"])
        self.assertIsNone(first["review_count"])

    def test_meta_extracted(self) -> None:
        payload = _build_fake_payload(num_products=2)
        api = _RealParseAPI()
        with patch("coupang_partners_api.requests.get",
                  return_value=_FakeResponse(payload, 200, {"X-Trace-ID": "trace-2", "X-Request-ID": "req-2"})):
            rs = api.search_products("kw", limit=2)

        meta = rs.get("meta") or {}
        self.assertEqual(meta.get("rcode"), "0")
        self.assertIn("파트너스", meta.get("rmessage"))
        self.assertTrue(meta.get("landing_url").startswith("https://link.coupang.com/"))
        self.assertEqual(meta.get("traceid"), "trace-2")
        self.assertEqual(meta.get("requestid"), "req-2")

    def test_category_path_sets_l1_l2(self) -> None:
        payload = _build_fake_payload(num_products=1)
        payload["data"]["productData"][0]["categoryName"] = "주방용품 > 냄비 > 프라이팬"
        api = _RealParseAPI()
        with patch("coupang_partners_api.requests.get", return_value=_FakeResponse(payload, 200, {})):
            rs = api.search_products("kw", limit=1)
        row = rs["rows"][0]
        self.assertEqual(row["category_name"], "주방용품 > 냄비 > 프라이팬")
        self.assertEqual(row["category_l1"], "주방용품")
        self.assertEqual(row["category_l2"], "냄비")

    def test_empty_product_data(self) -> None:
        payload = {"rCode": "0", "rMessage": "ok", "data": {"landingUrl": "", "productData": []}}
        api = _RealParseAPI()
        with patch("coupang_partners_api.requests.get", return_value=_FakeResponse(payload, 200, {})):
            rs = api.search_products("kw", limit=5)
        self.assertTrue(rs["ok"])
        self.assertEqual(rs["count"], 0)
        self.assertEqual(rs["rows"], [])
        self.assertIn("meta", rs)


class TestScoringV2(unittest.TestCase):
    """_cp_api_signal_v2 컴포넌트 합산 검증."""

    def test_full_components_sum_to_100(self) -> None:
        from recommended_keyword_engine import _cp_api_signal_v2
        score = _cp_api_signal_v2(
            items=10, avg_price=27000,
            rocket_ratio=1.0, free_shipping_ratio=1.0,
            category_match_score=15.0,
        )
        self.assertEqual(score, 100.0)

    def test_zero_items_zero_score(self) -> None:
        from recommended_keyword_engine import _cp_api_signal_v2
        score = _cp_api_signal_v2(
            items=0, avg_price=0.0,
            rocket_ratio=0.0, free_shipping_ratio=0.0,
            category_match_score=0.0,
        )
        self.assertEqual(score, 0.0)

    def test_review_no_longer_required_for_high_score(self) -> None:
        from recommended_keyword_engine import _cp_api_signal_v2
        score = _cp_api_signal_v2(
            items=10, avg_price=30000,
            rocket_ratio=1.0, free_shipping_ratio=1.0,
            category_match_score=15.0,
        )
        self.assertGreater(score, 75.0)

    def test_category_match(self) -> None:
        from recommended_keyword_engine import _cp_api_category_match
        self.assertEqual(_cp_api_category_match("생활용품", "생활/건강"), 15.0)
        self.assertEqual(_cp_api_category_match("생활용품", "생활용품 > 욕실용품"), 15.0)
        self.assertEqual(_cp_api_category_match("생활용품", recommend_l1="유아동", recommend_l2="기저귀", recommend_l3="생활용품"), 15.0)
        self.assertEqual(_cp_api_category_match("생활용품", "패션의류"), 0.0)
        self.assertEqual(_cp_api_category_match("", "생활용품"), 0.0)
        self.assertEqual(_cp_api_category_match("생활용품", ""), 0.0)


class TestEnrichInjectsNewKeys(unittest.TestCase):
    """enrich_with_coupang_api_assist 가 신규 키를 row 에 주입하는지 검증."""

    def setUp(self) -> None:
        _reset_throttler_state()

    def test_enrich_injects_full_keyset(self) -> None:
        from recommended_keyword_engine import enrich_with_coupang_api_assist
        payload = _build_fake_payload(num_products=5)
        env = _env(
            COUPANG_API_RPH="100",
            COUPANG_API_MIN_INTERVAL_SEC="0",
            COUPANG_API_MAX_CALLS_PER_RUN="100",
            COUPANG_API_TOP_N="10",
        )
        with patch.dict(os.environ, env, clear=False):
            with patch("coupang_partners_api.requests.get",
                      return_value=_FakeResponse(payload, 200, {"X-Trace-ID": "trace-e", "X-Request-ID": "req-e"})):
                fresh_api = CoupangPartnersAPI()
                fresh_throttler = CoupangPartnersThrottler(api=fresh_api)
                rows = [{"keyword": "집들이화장지", "l1": "생활용품", "l2": "", "l3": ""}]
                rows, stats = enrich_with_coupang_api_assist(rows, throttler=fresh_throttler)

        r = rows[0]
        for k in ["cp_api_ok", "cp_api_items", "cp_api_avg_price",
                  "cp_api_review_sum", "cp_api_signal", "cp_api_error"]:
            self.assertIn(k, r)
        for k in ["cp_api_product_id_first", "cp_api_category_name",
                  "cp_api_rocket_ratio", "cp_api_free_shipping_ratio",
                  "cp_api_category_match_score",
                  "cp_api_meta_traceid", "cp_api_meta_requestid"]:
            self.assertIn(k, r, f"new key '{k}' missing in enriched row")
        self.assertTrue(r["cp_api_ok"])
        self.assertEqual(r["cp_api_items"], 5)
        self.assertEqual(r["cp_api_category_name"], "생활용품")
        self.assertEqual(r["cp_api_category_match_score"], 15.0)
        self.assertEqual(r["cp_api_meta_traceid"], "trace-e")
        self.assertEqual(r["cp_api_review_sum"], 0)
        # items=5 → 25 + price(20000평균=15) + rocket(2/5*10=4) + free(3/5*10=6) + cat(15) = 65
        self.assertAlmostEqual(r["cp_api_signal"], 65.0, places=1)
        self.assertEqual(r["cp_api_product_id_first"], "1000")


if __name__ == "__main__":
    unittest.main(verbosity=2)
