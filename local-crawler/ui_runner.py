from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from config import LocalCrawlerSettings, get_settings
from railway_client import RailwayKeywordClient
from services.coupang_entry_scoring import CoupangEntryScoringEngine
from services.gemini_trend_scoring import GeminiTrendScoringService, load_trend_config
from services.naver_keyword_scoring import compute_naver_final_score

LOCAL_ROOT = Path(__file__).resolve().parent
PORTING_DB_PATH = LOCAL_ROOT.parent / "porting" / "coupang_crawl_core" / "db.py"
OUTPUT_DIR = LOCAL_ROOT / "output"
CRAWL_LOG_DIR = OUTPUT_DIR / "crawl_logs"
SMOKE_DIR = LOCAL_ROOT.parent / "porting" / "coupang_crawl_core" / ".smoke"
STATE_PATH = OUTPUT_DIR / "ui_state.json"
RESULTS_PATH = OUTPUT_DIR / "ui_results.json"
STOP_PATH = OUTPUT_DIR / "ui_stop_requested.flag"

_STATE_LOCK = threading.Lock()
_RUNNER_THREAD: Optional[threading.Thread] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _write_json(path: Path, payload: Any) -> None:
    _ensure_output_dir()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _r2_is_configured(settings: LocalCrawlerSettings) -> bool:
    return all(
        [
            settings.r2_account_id,
            settings.r2_access_key_id,
            settings.r2_secret_access_key,
            settings.r2_bucket_name,
        ]
    )


def _build_r2_client(settings: LocalCrawlerSettings):
    endpoint_url = f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def _build_r2_result_key(*, run_id: Optional[str], job_id: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_run_id = str(run_id or "no-run-id").strip() or "no-run-id"
    safe_job_id = str(job_id or "no-job-id").strip() or "no-job-id"
    return f"crawling/coupang/local-ui-results/{safe_run_id}/{timestamp}-{safe_job_id}.json"


def _upload_results_to_r2(
    *,
    settings: LocalCrawlerSettings,
    run_id: Optional[str],
    job_id: str,
    payload: Dict[str, Any],
) -> str:
    if not _r2_is_configured(settings):
        return ""
    key = _build_r2_result_key(run_id=run_id, job_id=job_id)
    client = _build_r2_client(settings)
    try:
        client.put_object(
            Bucket=settings.r2_bucket_name,
            Key=key,
            Body=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
    except (BotoCoreError, ClientError):
        return ""
    return key


def _load_coupang_snapshot_helpers():
    if not PORTING_DB_PATH.is_file():
        return None, None
    import importlib.util

    spec = importlib.util.spec_from_file_location("local_coupang_porting_db", PORTING_DB_PATH)
    if spec is None or spec.loader is None:
        return None, None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    build_payload = getattr(module, "build_recommend_engine_coupang_snapshot_payload", None)
    insert_snapshot = getattr(module, "insert_coupang_search_snapshot", None)
    if not callable(build_payload) or not callable(insert_snapshot):
        return None, None
    return build_payload, insert_snapshot


def _sync_keyword_result_to_db(
    *,
    settings: LocalCrawlerSettings,
    keyword: str,
    crawl_result: Dict[str, Any],
) -> bool:
    build_payload, insert_snapshot = _load_coupang_snapshot_helpers()
    if build_payload is None or insert_snapshot is None:
        return False

    db_url = (
        settings.mysql_url
        or settings.mysql_public_url
        or settings.mariadb_public_url
        or os.environ.get("MYSQL_URL")
        or os.environ.get("MYSQL_PUBLIC_URL")
        or os.environ.get("MARIADB_PUBLIC_URL")
    )
    if not db_url:
        return False

    previous_env = {
        "MYSQL_URL": os.environ.get("MYSQL_URL"),
        "MYSQL_PUBLIC_URL": os.environ.get("MYSQL_PUBLIC_URL"),
        "MARIADB_PUBLIC_URL": os.environ.get("MARIADB_PUBLIC_URL"),
    }
    os.environ["MYSQL_URL"] = db_url
    os.environ["MYSQL_PUBLIC_URL"] = db_url
    os.environ["MARIADB_PUBLIC_URL"] = db_url
    try:
        payload = crawl_result.get("payload") or {}
        result = payload.get("result") or {}
        snapshot_payload = build_payload(keyword=keyword, crawl_data=result)
        if not snapshot_payload:
            return False
        inserted = insert_snapshot(snapshot_payload)
        return bool(inserted)
    except Exception:
        return False
    finally:
        for env_key, env_value in previous_env.items():
            if env_value is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = env_value


def _default_state() -> Dict[str, Any]:
    settings = get_settings()
    return {
        "job_id": None,
        "status": "idle",
        "message": "대기중",
        "run_id": None,
        "current_keyword": "",
        "current_index": 0,
        "total_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "last_error": "",
        "last_run_at": None,
        "started_at": None,
        "finished_at": None,
        "bright_data_enabled": str(settings.coupang_bright_request or "off").strip().lower() in {"1", "true", "on", "yes"},
        "result_locations": {
            "local_file": str(RESULTS_PATH),
            "r2_key": "",
        },
        "logs": [],
    }


def get_ui_state() -> Dict[str, Any]:
    state = _read_json(STATE_PATH, _default_state())
    if not isinstance(state, dict):
        return _default_state()
    merged = _default_state()
    merged.update(state)
    return merged


def get_ui_results() -> Dict[str, Any]:
    payload = _read_json(RESULTS_PATH, {"job_id": None, "items": [], "keyword_scores": []})
    if not isinstance(payload, dict):
        return {"job_id": None, "items": [], "keyword_scores": []}
    payload.setdefault("items", [])
    payload.setdefault("keyword_scores", [])
    return payload


def _append_log(state: Dict[str, Any], message: str, *, level: str = "info") -> None:
    logs = list(state.get("logs") or [])
    logs.append(
        {
            "timestamp": _now_iso(),
            "level": level,
            "message": str(message),
        }
    )
    state["logs"] = logs[-200:]


def _update_state(**updates: Any) -> Dict[str, Any]:
    with _STATE_LOCK:
        state = get_ui_state()
        state.update(updates)
        _write_json(STATE_PATH, state)
        return state


def _reset_results(job_id: str) -> None:
    _write_json(
        RESULTS_PATH,
        {
            "job_id": job_id,
            "generated_at": _now_iso(),
            "items": [],
            "keyword_scores": [],
        },
    )


_SCORING_ENGINE = CoupangEntryScoringEngine()


def _gemini_trend_enabled(settings: LocalCrawlerSettings) -> bool:
    if not str(settings.gemini_api_key or "").strip():
        return False
    return bool(settings.gemini_trend_auto_on_crawl)


def _gemini_trend_service() -> GeminiTrendScoringService:
    settings = get_settings()
    config = load_trend_config()
    config["model"] = str(settings.gemini_trend_model or config.get("model") or "gemini-2.5-flash")
    config["reference_month"] = str(
        settings.gemini_trend_reference_month or config.get("reference_month") or ""
    )
    return GeminiTrendScoringService(api_key=str(settings.gemini_api_key or ""), config=config)


def score_keyword_ai_trend(keyword: str) -> Dict[str, Any]:
    return _gemini_trend_service().verify_keyword_trend_score(keyword)


def refresh_gemini_trend_scores(*, keywords: Optional[List[str]] = None) -> Dict[str, Any]:
    service = _gemini_trend_service()
    if not service.is_configured():
        return {
            "updated": 0,
            "errors": ["GEMINI_API_KEY가 설정되지 않았습니다."],
        }

    payload = get_ui_results()
    existing = list(payload.get("keyword_scores") or [])
    target_keywords = keywords or [str(row.get("keyword") or "").strip() for row in existing]
    target_keywords = [keyword for keyword in target_keywords if keyword]

    errors: List[str] = []
    updated = 0
    score_map = {str(row.get("keyword") or "").strip(): dict(row) for row in existing}

    delay_sec = max(0.0, float((service.config or {}).get("keyword_delay_sec") or 1.5))
    for index, keyword in enumerate(target_keywords):
        if index > 0 and delay_sec > 0:
            time.sleep(delay_sec)
        ai_payload = service.verify_keyword_trend_score(keyword)
        row = score_map.get(keyword) or {"keyword": keyword}
        row.update(ai_payload)
        row["ai_scored_at"] = _now_iso()
        score_map[keyword] = row
        if ai_payload.get("ai_scoring_ready"):
            updated += 1
        else:
            errors.append(f"{keyword}: {ai_payload.get('ai_scoring_error') or 'failed'}")

    payload["keyword_scores"] = list(score_map.values())
    payload["generated_at"] = _now_iso()
    _write_json(RESULTS_PATH, payload)
    return {"updated": updated, "errors": errors}


def _collect_keyword_top10_items(keyword: str) -> List[Dict[str, Any]]:
    payload = get_ui_results()
    rows = [
        row
        for row in (payload.get("items") or [])
        if str(row.get("keyword") or "").strip() == keyword
    ]
    rows.sort(key=lambda row: int(row.get("rank") or 999))
    top10: List[Dict[str, Any]] = []
    for row in rows:
        if row.get("rank") is None:
            continue
        top10.append(
            {
                "rank": row.get("rank"),
                "title": row.get("title") or "",
                "price": row.get("price"),
                "review_count": row.get("review_count"),
                "rating": row.get("review_score"),
                "delivery_type": row.get("delivery_type") or "",
            }
        )
        if len(top10) >= 10:
            break
    return top10


def _upsert_keyword_score(keyword_row: Dict[str, Any]) -> Dict[str, Any]:
    keyword = str(keyword_row.get("keyword") or "").strip()
    if not keyword:
        return {}

    top10_items = _collect_keyword_top10_items(keyword)
    score_payload = _SCORING_ENGINE.score_keyword(
        keyword,
        top10_items,
        metadata={
            "group_name": keyword_row.get("group_name") or "",
            "theme_name": keyword_row.get("theme_name") or "",
            "theme_detail": keyword_row.get("theme_detail") or "",
        },
    )
    score_payload["coupang_score"] = score_payload.get("final_score")
    score_payload["naver_score"] = compute_naver_final_score(keyword_row)
    settings = get_settings()
    if _gemini_trend_enabled(settings):
        score_payload.update(score_keyword_ai_trend(keyword))
        score_payload["ai_scored_at"] = _now_iso()
    score_payload["scored_at"] = _now_iso()

    payload = get_ui_results()
    scores = [
        row
        for row in (payload.get("keyword_scores") or [])
        if str(row.get("keyword") or "").strip() != keyword
    ]
    scores.append(score_payload)
    payload["keyword_scores"] = scores
    payload["generated_at"] = _now_iso()
    _write_json(RESULTS_PATH, payload)
    return score_payload


def _append_result_row(row: Dict[str, Any]) -> None:
    payload = get_ui_results()
    items = list(payload.get("items") or [])
    items.append(row)
    payload["generated_at"] = _now_iso()
    payload["items"] = items
    _write_json(RESULTS_PATH, payload)


def fetch_batch_keywords(*, limit: Optional[int] = None) -> Dict[str, Any]:
    settings = get_settings()
    client = RailwayKeywordClient(settings)
    return client.fetch_keywords(limit=limit)


def request_stop() -> Dict[str, Any]:
    _ensure_output_dir()
    STOP_PATH.write_text("stop", encoding="utf-8")
    state = _update_state(message="안전 중지 요청됨")
    _append_log(state, "안전 중지 요청이 접수되었습니다.", level="warning")
    _write_json(STATE_PATH, state)
    return state


def _build_process_env(keyword: str) -> Dict[str, str]:
    env = os.environ.copy()
    env["MANUAL_KEYWORD"] = keyword
    # Keep the browser visible during batch runs to reduce detection versus strict headless mode.
    env["COUPANG_HEADLESS"] = "0"
    # Use the BlueOcean-style path: require Google -> Coupang entry before parsing.
    env["COUPANG_FORCE_GOOGLE_ENTRY"] = "1"
    # Keep the local crawler focused on the Google-entry Playwright path instead of Bright-first shortcuts.
    env["COUPANG_BRIGHT_REQUEST"] = "off"
    return env


def _smoke_json_path_for_keyword(keyword: str) -> Path:
    slug = re.sub(r"[^\w가-힣]+", "_", str(keyword or "").strip()).strip("_")[:80]
    if slug:
        per_kw = SMOKE_DIR / f"last_smoke_extract_{slug}.json"
        if per_kw.is_file():
            return per_kw
    return SMOKE_DIR / "last_smoke_extract.json"


def _summarize_smoke_sales_from_artifacts(keyword: str) -> str:
    """smoke JSON(detail_results) 기준 판매량 수집 요약 — UI 로그용."""
    for path in (_smoke_json_path_for_keyword(keyword), SMOKE_DIR / "last_smoke_extract.json"):
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        saved_kw = str(payload.get("keyword") or "").strip()
        if keyword and saved_kw and saved_kw != keyword:
            continue
        rows = list(payload.get("detail_results") or [])
        if not rows:
            return "판매량: detail_results 없음(JSON 초안만 읽었을 수 있음)"
        filled = [
            r for r in rows if str(r.get("monthly_sales") or "").strip() not in {"", "0개"}
        ]
        samples = [
            f"rank{r.get('rank')}={r.get('monthly_sales')}"
            for r in filled[:3]
            if isinstance(r, dict)
        ]
        tail = f" ({', '.join(samples)})" if samples else ""
        return f"판매량 수집 {len(filled)}/{len(rows)}{tail}"
    return "판매량: smoke JSON 없음"


def _write_crawl_log(keyword: str, crawl_result: Dict[str, Any]) -> Path:
    """ported_coupang stdout/stderr → output/crawl_logs/ (Streamlit 로그는 요약만)."""
    CRAWL_LOG_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^\w가-힣]+", "_", str(keyword or "").strip()).strip("_")[:80] or "keyword"
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    path = CRAWL_LOG_DIR / f"{slug}_{stamp}.log"
    stdout = str(crawl_result.get("stdout") or "")
    stderr = str(crawl_result.get("stderr") or "")
    smoke_summary = _summarize_smoke_sales_from_artifacts(keyword)
    lines = [
        f"# keyword={keyword}",
        f"# returncode={crawl_result.get('returncode')}",
        f"# {smoke_summary}",
        "",
        "=== stdout ===",
        stdout,
        "",
        "=== stderr ===",
        stderr,
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _run_single_keyword(keyword_row: Dict[str, Any]) -> Dict[str, Any]:
    keyword = str(keyword_row.get("keyword") or "").strip()
    command = [sys.executable, str(LOCAL_ROOT / "ported_coupang.py"), "--keyword", keyword]
    process = subprocess.run(
        command,
        cwd=str(LOCAL_ROOT),
        env=_build_process_env(keyword),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    payload = _read_json(LOCAL_ROOT / "output" / "ported_last_result.json", {})
    result = {
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "payload": payload if isinstance(payload, dict) else {},
    }
    try:
        log_path = _write_crawl_log(keyword, result)
        result["log_path"] = str(log_path)
    except Exception:
        pass
    return result


def _monthly_sales_for_storage(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text == "0개":
        return ""
    return text


def _review_count_for_sort(value: Any) -> int:
    if value in (None, ""):
        return -1
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return -1


def _top_items_by_reviews(items: List[Dict[str, Any]], *, limit: int = 5) -> List[Dict[str, Any]]:
    ordered = sorted(
        [dict(x) for x in items if isinstance(x, dict)],
        key=lambda row: (-_review_count_for_sort(row.get("review_count")), int(row.get("rank") or 999)),
    )
    picked = ordered[: max(1, limit)]
    for idx, row in enumerate(picked, start=1):
        row["review_rank_in_keyword"] = idx
    return picked


def _flatten_result_rows(keyword_row: Dict[str, Any], crawl_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = crawl_result.get("payload", {}).get("result") or {}
    stats = crawl_result.get("payload", {}).get("stats") or {}
    last_fetch_source = crawl_result.get("payload", {}).get("last_fetch_source") or ""
    top10_items = _top_items_by_reviews(list(result.get("top10_items") or []), limit=5)
    rows: List[Dict[str, Any]] = []
    for item in top10_items:
        rows.append(
            {
                "keyword": keyword_row.get("keyword") or "",
                "group_name": keyword_row.get("group_name") or "",
                "theme_name": keyword_row.get("theme_name") or "",
                "theme_detail": keyword_row.get("theme_detail") or "",
                "rank": item.get("rank"),
                "title": item.get("title") or "",
                "image_url": item.get("image_url") or "",
                "price": item.get("price"),
                "review_count": item.get("review_count"),
                "review_score": item.get("review_score"),
                "delivery_type": item.get("delivery_type") or "",
                "shipping_fee": item.get("shipping_fee"),
                "product_url": item.get("product_url") or item.get("url") or "",
                "category": item.get("category") or "",
                "coupon_applied": item.get("coupon_applied"),
                "seller_info": item.get("seller_info") or "",
                "product_id": item.get("product_id") or "",
                "option_count": item.get("option_count"),
                "origin_country": item.get("origin_country") or "",
                "model_name": item.get("model_name") or "",
                "monthly_sales": _monthly_sales_for_storage(item.get("monthly_sales")),
                "detail_fetch_ok": item.get("detail_fetch_ok"),
                "detail_parse_filled_count": item.get("detail_parse_filled_count"),
                "fetch_source": result.get("fetch_source") or last_fetch_source,
                "reason_code": result.get("reason_code") or "",
                "product_count": result.get("product_count"),
                "avg_price": result.get("avg_price"),
                "avg_reviews": result.get("avg_reviews"),
                "bright_ok": stats.get("bright_ok"),
                "bright_error": stats.get("bright_error"),
                "playwright_ok": stats.get("playwright_ok"),
                "requests_ok": stats.get("requests_ok"),
            }
        )
    return rows


def _runner_main(*, retry_failed_only: bool = False, limit: Optional[int] = None) -> None:
    settings = get_settings()
    state = get_ui_state()
    job_id = state.get("job_id") or uuid.uuid4().hex[:12]
    try:
        keyword_payload = fetch_batch_keywords(limit=limit)
        keyword_rows = list(keyword_payload.get("keywords") or [])
        run_id = keyword_payload.get("run_id")

        if retry_failed_only:
            previous = get_ui_results()
            failed_keywords = {
                str(item.get("keyword") or "").strip()
                for item in previous.get("items") or []
                if str(item.get("reason_code") or "").strip() not in {"OK", ""}
            }
            keyword_rows = [
                row for row in keyword_rows if str(row.get("keyword") or "").strip() in failed_keywords
            ]

        fresh_state = _default_state()
        fresh_state.update(
            {
                "job_id": job_id,
                "status": "running",
                "message": "배치 실행 중",
                "run_id": run_id,
                "current_keyword": "",
                "current_index": 0,
                "total_count": len(keyword_rows),
                "success_count": 0,
                "failure_count": 0,
                "last_error": "",
                "started_at": _now_iso(),
                "finished_at": None,
                "last_run_at": _now_iso(),
                "bright_data_enabled": str(settings.coupang_bright_request or "off").strip().lower() in {"1", "true", "on", "yes"},
                "result_locations": {
                    "local_file": str(RESULTS_PATH),
                    "r2_key": "",
                },
                "logs": [],
            }
        )
        _append_log(fresh_state, f"배치 시작: {len(keyword_rows)}개 키워드", level="info")
        _write_json(STATE_PATH, fresh_state)
        _reset_results(job_id)

        if not keyword_rows:
            _append_log(fresh_state, "실행할 final keywords가 없습니다.", level="warning")
            fresh_state["status"] = "idle"
            fresh_state["message"] = "실행할 final keywords가 없습니다."
            fresh_state["finished_at"] = _now_iso()
            _write_json(STATE_PATH, fresh_state)
            return

        for index, keyword_row in enumerate(keyword_rows, start=1):
            state = get_ui_state()
            if STOP_PATH.exists():
                _append_log(state, "안전 중지 요청을 확인했습니다. 현재 작업까지 마치고 종료합니다.", level="warning")
                STOP_PATH.unlink(missing_ok=True)
                state["status"] = "stopped"
                state["message"] = "사용자 요청으로 안전 중지됨"
                state["finished_at"] = _now_iso()
                _write_json(STATE_PATH, state)
                return

            keyword = str(keyword_row.get("keyword") or "").strip()
            state.update(
                {
                    "current_keyword": keyword,
                    "current_index": index,
                    "message": f"{keyword} 크롤링 중",
                    "last_run_at": _now_iso(),
                }
            )
            _append_log(state, f"[{index}/{len(keyword_rows)}] {keyword} 실행", level="info")
            _write_json(STATE_PATH, state)

            crawl_result = _run_single_keyword(keyword_row)
            payload = crawl_result.get("payload") or {}
            result = payload.get("result") or {}
            success = (
                crawl_result.get("returncode") == 0
                and str(result.get("reason_code") or "") == "OK"
            )
            rows = _flatten_result_rows(keyword_row, crawl_result)
            if rows:
                for row in rows:
                    _append_result_row(row)
            else:
                _append_result_row(
                    {
                        "keyword": keyword,
                        "group_name": keyword_row.get("group_name") or "",
                        "theme_name": keyword_row.get("theme_name") or "",
                        "theme_detail": keyword_row.get("theme_detail") or "",
                        "rank": None,
                        "title": "",
                        "image_url": "",
                        "price": None,
                        "review_count": None,
                        "review_score": None,
                        "delivery_type": "",
                        "shipping_fee": None,
                        "product_url": "",
                        "category": "",
                        "coupon_applied": False,
                        "seller_info": "",
                        "product_id": "",
                        "option_count": None,
                        "origin_country": "",
                        "model_name": "",
                        "detail_fetch_ok": None,
                        "detail_parse_filled_count": 0,
                        "fetch_source": payload.get("last_fetch_source") or "",
                        "reason_code": result.get("reason_code") or f"EXIT_{crawl_result.get('returncode')}",
                        "product_count": result.get("product_count"),
                        "avg_price": result.get("avg_price"),
                        "avg_reviews": result.get("avg_reviews"),
                        "bright_ok": (payload.get("stats") or {}).get("bright_ok"),
                        "bright_error": (payload.get("stats") or {}).get("bright_error"),
                        "playwright_ok": (payload.get("stats") or {}).get("playwright_ok"),
                        "requests_ok": (payload.get("stats") or {}).get("requests_ok"),
                    }
                )

            state = get_ui_state()
            if success:
                settings = get_settings()
                if _gemini_trend_enabled(settings):
                    state["message"] = f"{keyword} Gemini 트렌드 검증 중"
                    _write_json(STATE_PATH, state)
                score_payload = _upsert_keyword_score(keyword_row)
                state["success_count"] = int(state.get("success_count") or 0) + 1
                coupang_score = score_payload.get("coupang_score")
                naver_score = score_payload.get("naver_score")
                ai_score = score_payload.get("ai_score")
                ai_tier = score_payload.get("ai_tier")
                completion_parts = [
                    f"{keyword} 완료",
                    f"쿠팡 {coupang_score}",
                    f"네이버 {naver_score}",
                ]
                if ai_score is not None:
                    completion_parts.append(f"AI {ai_score} ({ai_tier or '-'})")
                elif _gemini_trend_enabled(get_settings()):
                    completion_parts.append(
                        f"AI 실패: {score_payload.get('ai_scoring_error') or '-'}"
                    )
                sales_note = _summarize_smoke_sales_from_artifacts(keyword)
                log_path = str(crawl_result.get("log_path") or "")
                if log_path:
                    completion_parts.append(sales_note)
                    completion_parts.append(f"로그 {log_path}")
                else:
                    completion_parts.append(sales_note)
                _append_log(state, " — ".join(completion_parts), level="success")
                synced = _sync_keyword_result_to_db(
                    settings=settings,
                    keyword=keyword,
                    crawl_result=crawl_result,
                )
                if synced:
                    _append_log(state, f"{keyword} Railway DB 반영 완료", level="success")
                else:
                    _append_log(state, f"{keyword} Railway DB 반영 스킵", level="warning")
            else:
                state["failure_count"] = int(state.get("failure_count") or 0) + 1
                stderr = str(crawl_result.get("stderr") or "").strip()
                last_error = stderr or str(payload.get("last_error") or "") or "크롤링 실패"
                state["last_error"] = last_error[:1000]
                _append_log(state, f"{keyword} 실패: {state['last_error']}", level="error")

            state["last_run_at"] = _now_iso()
            state["result_locations"] = {
                "local_file": str(RESULTS_PATH),
                "r2_key": "",
            }
            _write_json(STATE_PATH, state)
            time.sleep(0.2)

        state = get_ui_state()
        state["status"] = "completed"
        state["message"] = "배치 완료"
        state["finished_at"] = _now_iso()
        results_payload = get_ui_results()
        r2_key = _upload_results_to_r2(
            settings=settings,
            run_id=run_id,
            job_id=job_id,
            payload=results_payload,
        )
        state["result_locations"] = {
            "local_file": str(RESULTS_PATH),
            "r2_key": r2_key,
        }
        if r2_key:
            _append_log(state, f"R2 업로드 완료: {r2_key}", level="success")
        else:
            _append_log(state, "R2 업로드를 건너뛰었거나 실패했습니다.", level="warning")
        _append_log(state, "배치 실행이 완료되었습니다.", level="success")
        _write_json(STATE_PATH, state)
    except Exception as exc:
        state = get_ui_state()
        state["status"] = "failed"
        state["message"] = "배치 실행 실패"
        state["last_error"] = str(exc)
        state["finished_at"] = _now_iso()
        _append_log(state, f"배치 실패: {exc}", level="error")
        _write_json(STATE_PATH, state)


def start_batch_run(*, retry_failed_only: bool = False, limit: Optional[int] = None) -> Dict[str, Any]:
    global _RUNNER_THREAD
    state = get_ui_state()
    if _RUNNER_THREAD is not None and _RUNNER_THREAD.is_alive():
        return state
    STOP_PATH.unlink(missing_ok=True)
    job_id = uuid.uuid4().hex[:12]
    fresh_state = _default_state()
    fresh_state.update(
        {
            "job_id": job_id,
            "status": "starting",
            "message": "배치 시작 준비 중",
            "run_id": state.get("run_id"),
            "current_keyword": "",
            "current_index": 0,
            "total_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "last_error": "",
            "started_at": _now_iso(),
            "finished_at": None,
            "last_run_at": _now_iso(),
            "logs": [],
        }
    )
    _append_log(
        fresh_state,
        "실패건 재실행 준비" if retry_failed_only else "배치 시작 준비",
        level="info",
    )
    _write_json(STATE_PATH, fresh_state)
    _reset_results(job_id)
    _RUNNER_THREAD = threading.Thread(
        target=_runner_main,
        kwargs={"retry_failed_only": retry_failed_only, "limit": limit},
        daemon=True,
    )
    _RUNNER_THREAD.start()
    return get_ui_state()
