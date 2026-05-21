from __future__ import annotations

import json
import os
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


LOCAL_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = LOCAL_ROOT / "output"
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
    payload = _read_json(RESULTS_PATH, {"job_id": None, "items": []})
    if not isinstance(payload, dict):
        return {"job_id": None, "items": []}
    payload.setdefault("items", [])
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
        },
    )


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
    return env


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
    return {
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "payload": payload if isinstance(payload, dict) else {},
    }


def _flatten_result_rows(keyword_row: Dict[str, Any], crawl_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = crawl_result.get("payload", {}).get("result") or {}
    stats = crawl_result.get("payload", {}).get("stats") or {}
    last_fetch_source = crawl_result.get("payload", {}).get("last_fetch_source") or ""
    top10_items = list(result.get("top10_items") or [])
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
                        "detail_fetch_ok": False,
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
                state["success_count"] = int(state.get("success_count") or 0) + 1
                _append_log(state, f"{keyword} 완료", level="success")
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
    _update_state(
        job_id=job_id,
        status="starting",
        message="배치 시작 준비 중",
        started_at=_now_iso(),
        finished_at=None,
        last_error="",
        current_keyword="",
        current_index=0,
        success_count=0,
        failure_count=0,
    )
    _RUNNER_THREAD = threading.Thread(
        target=_runner_main,
        kwargs={"retry_failed_only": retry_failed_only, "limit": limit},
        daemon=True,
    )
    _RUNNER_THREAD.start()
    return get_ui_state()
