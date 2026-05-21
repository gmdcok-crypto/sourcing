from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional


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
