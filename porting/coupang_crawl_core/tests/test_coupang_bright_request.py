"""P4: Bright /request env gating and retry (no live HTTP)."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from coupang_crawler import CoupangCrawler, _coupang_bright_request_enabled


@pytest.fixture(autouse=True)
def _clear_bright_env() -> None:
    for k in (
        "COUPANG_BRIGHT_REQUEST",
        "BRIGHTDATA_API_TOKEN",
        "BRIGHTDATA_REQUEST_ZONE",
        "BRIGHTDATA_REQUEST_RETRIES",
    ):
        os.environ.pop(k, None)
    yield
    for k in (
        "COUPANG_BRIGHT_REQUEST",
        "BRIGHTDATA_API_TOKEN",
        "BRIGHTDATA_REQUEST_ZONE",
        "BRIGHTDATA_REQUEST_RETRIES",
    ):
        os.environ.pop(k, None)


def test_bright_request_enabled_default_on() -> None:
    assert _coupang_bright_request_enabled() is True


def test_bright_request_enabled_empty_means_on() -> None:
    os.environ["COUPANG_BRIGHT_REQUEST"] = "  "
    assert _coupang_bright_request_enabled() is True


@pytest.mark.parametrize("raw", ["off", "OFF", "0", "false", "no", "n"])
def test_bright_request_enabled_off_variants(raw: str) -> None:
    os.environ["COUPANG_BRIGHT_REQUEST"] = raw
    assert _coupang_bright_request_enabled() is False


def test_bright_request_fetch_retries_then_ok() -> None:
    os.environ["BRIGHTDATA_API_TOKEN"] = "t"
    os.environ["BRIGHTDATA_REQUEST_ZONE"] = "z"
    os.environ["BRIGHTDATA_REQUEST_RETRIES"] = "1"
    bad = MagicMock()
    bad.status_code = 503
    bad.text = ""
    good = MagicMock()
    good.status_code = 200
    good.text = "<html><div>ok</div></html>"
    good.json.side_effect = ValueError("not json")
    cc = CoupangCrawler()
    with patch("coupang_crawler.requests.post", side_effect=[bad, good]) as post:
        html = cc._bright_request_fetch_html("https://example.com/")
    assert html is not None
    assert "<html" in html
    assert post.call_count == 2
    assert cc.get_stats()["bright_error"] == 0


def test_bright_request_fetch_no_retry_on_400() -> None:
    os.environ["BRIGHTDATA_API_TOKEN"] = "t"
    os.environ["BRIGHTDATA_REQUEST_ZONE"] = "z"
    os.environ["BRIGHTDATA_REQUEST_RETRIES"] = "2"
    bad = MagicMock()
    bad.status_code = 400
    bad.text = "nope"
    cc = CoupangCrawler()
    with patch("coupang_crawler.requests.post", return_value=bad) as post:
        html = cc._bright_request_fetch_html("https://example.com/")
    assert html is None
    assert post.call_count == 1
    assert cc.get_stats()["bright_error"] == 1
