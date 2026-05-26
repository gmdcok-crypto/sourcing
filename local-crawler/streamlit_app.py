from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import boto3
from botocore.exceptions import BotoCoreError, ClientError

from config import get_settings
from services.naver_keyword_scoring import compute_naver_final_score
from ui_runner import (
    fetch_batch_keywords,
    get_ui_results,
    get_ui_state,
    refresh_gemini_trend_scores,
    request_stop,
    start_batch_run,
)


st.set_page_config(page_title="Local Crawler Console", layout="wide")


def _apply_dark_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: #0f1117;
            color: #e5e7eb;
        }
        [data-testid="stSidebar"] {
            background: #151924;
            border-right: 1px solid #2a3040;
        }
        [data-testid="stHeader"] {
            background: rgba(15, 17, 23, 0.9);
        }
        h1, h2, h3, p, label, div, span {
            color: #e5e7eb;
        }
        [data-testid="stMetric"] {
            background: #171b26;
            border: 1px solid #2b3243;
            border-radius: 12px;
            padding: 14px;
        }
        [data-testid="stMetricLabel"],
        [data-testid="stMetricValue"] {
            color: #f3f4f6;
        }
        .stButton > button,
        .stDownloadButton > button {
            background: #2563eb;
            color: #ffffff;
            border: 1px solid #2563eb;
            border-radius: 10px;
        }
        .stButton > button:hover,
        .stDownloadButton > button:hover {
            background: #1d4ed8;
            border-color: #1d4ed8;
            color: #ffffff;
        }
        .stNumberInput input,
        .stTextArea textarea {
            background: #111827 !important;
            color: #f9fafb !important;
            border: 1px solid #374151 !important;
        }
        [data-testid="stDataFrame"],
        [data-testid="stTable"] {
            background: #111827;
            border: 1px solid #2b3243;
            border-radius: 12px;
        }
        [data-testid="stAlert"] {
            background: #171b26;
            color: #e5e7eb;
            border: 1px solid #2b3243;
        }
        [data-testid="stCodeBlock"] {
            background: #111827;
            border: 1px solid #2b3243;
            border-radius: 12px;
        }
        [data-testid="stCodeBlock"] pre,
        [data-testid="stCodeBlock"] code {
            background: #111827 !important;
            color: #e5e7eb !important;
            border: none !important;
        }
        .crawler-log-box {
            background: #111827;
            color: #e5e7eb;
            border: 1px solid #2b3243;
            border-radius: 12px;
            padding: 14px 16px;
            max-height: 260px;
            overflow: auto;
            font-size: 12px;
            line-height: 1.6;
            white-space: pre-wrap;
            word-break: break-word;
            margin: 0;
            font-family: Consolas, "Courier New", monospace;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


KST = ZoneInfo("Asia/Seoul")


def _format_timestamp(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "-"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return raw


def _logs_to_lines(logs: List[Dict[str, Any]]) -> str:
    lines = []
    for row in logs[-80:]:
        timestamp = _format_timestamp(row.get("timestamp"))
        level = str(row.get("level") or "info").upper()
        message = str(row.get("message") or "")
        lines.append(f"[{timestamp}] [{level}] {message}")
    return "\n".join(lines)


def _render_dark_log_box(log_text: str) -> None:
    st.markdown(
        f'<pre class="crawler-log-box">{escape(log_text)}</pre>',
        unsafe_allow_html=True,
    )


def _to_display_int(value: Any) -> Any:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return value


def _normalize_shipping_fee_display(value: Any) -> Any:
    text = str(value or "").strip()
    if not text:
        return None
    if "무료배송" in text:
        return 0
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        try:
            return int(digits)
        except ValueError:
            return text
    return text


def _result_dataframe(items: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for item in items:
        rows.append(
            {
                "키워드": item.get("keyword"),
                "순위": item.get("rank"),
                "상품명": item.get("title"),
                "판매가격": _to_display_int(item.get("price")),
                "쿠폰적용": "Y" if item.get("coupon_applied") else "N",
                "배송정책": item.get("delivery_type"),
                "배송비": _normalize_shipping_fee_display(item.get("shipping_fee")),
                "리뷰수": _to_display_int(item.get("review_count")),
                "리뷰별점": _to_display_int(item.get("review_score")),
                "상품링크": item.get("product_url"),
                "대표이미지": item.get("image_url"),
                "쿠팡상품번호": item.get("product_id"),
                "상태코드": item.get("reason_code"),
                "수집방식": item.get("fetch_source"),
            }
        )
    df = pd.DataFrame(rows)
    for column in ("판매가격", "배송비", "리뷰수", "리뷰별점"):
        if column in df.columns:
            df[column] = pd.array(df[column], dtype="Int64")
    return df


def _preview_dataframe(items: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for item in items:
        rows.append(
            {
                "키워드": item.get("keyword"),
                "그룹명": item.get("group_name"),
                "테마명": item.get("theme_name"),
                "경로": item.get("theme_detail"),
                "조회수": _to_display_int(item.get("monthly_mobile_searches")),
                "클릭율": _to_display_int(item.get("monthly_mobile_ctr")),
                "경쟁률": item.get("competition_level"),
                "광고노출": _to_display_int(item.get("monthly_exposure_ads")),
                "상품수": _to_display_int(item.get("product_count")),
            }
        )
    df = pd.DataFrame(rows)
    for column in ("조회수", "클릭율", "광고노출", "상품수"):
        if column in df.columns:
            df[column] = pd.array(df[column], dtype="Int64")
    return df


def _style_dark_dataframe(df: pd.DataFrame) -> Any:
    return (
        df.style.set_properties(
            **{
                "background-color": "#111827",
                "color": "#f3f4f6",
                "border-color": "#2b3243",
            }
        )
        .set_table_styles(
            [
                {
                    "selector": "th",
                    "props": [
                        ("background-color", "#1f2937"),
                        ("color", "#f9fafb"),
                        ("border", "1px solid #374151"),
                        ("font-weight", "700"),
                    ],
                },
                {
                    "selector": "td",
                    "props": [
                        ("border", "1px solid #2b3243"),
                    ],
                },
                {
                    "selector": "table",
                    "props": [
                        ("background-color", "#111827"),
                        ("color", "#f3f4f6"),
                        ("border-collapse", "collapse"),
                    ],
                },
            ]
        )
    )


def _render_status_panel(state: Dict[str, Any]) -> None:
    status = str(state.get("status") or "idle").upper()
    status_color = {
        "COMPLETED": "#16a34a",
        "RUNNING": "#2563eb",
        "STARTING": "#d97706",
        "FAILED": "#dc2626",
        "STOPPED": "#eab308",
        "IDLE": "#6b7280",
    }.get(status, "#6b7280")
    status_background = {
        "COMPLETED": "rgba(22, 163, 74, 0.14)",
        "RUNNING": "rgba(37, 99, 235, 0.14)",
        "STARTING": "rgba(217, 119, 6, 0.14)",
        "FAILED": "rgba(220, 38, 38, 0.14)",
        "STOPPED": "rgba(234, 179, 8, 0.14)",
        "IDLE": "rgba(107, 114, 128, 0.14)",
    }.get(status, "rgba(107, 114, 128, 0.14)")

    st.markdown("### 실행 상태")
    st.markdown(
        f"""
        <div style="
            border: 1px solid #2b3243;
            background: #171b26;
            border-radius: 14px;
            padding: 16px;
            margin-bottom: 14px;
        ">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
                <span style="
                    display:inline-block;
                    padding:4px 10px;
                    border-radius:999px;
                    background:{status_background};
                    color:{status_color};
                    font-size:12px;
                    font-weight:700;
                ">{status}</span>
                <span style="font-size:18px; font-weight:700; color:#f9fafb;">{state.get('message') or '-'}</span>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
                <div style="background:#111827; border:1px solid #2b3243; border-radius:10px; padding:12px;">
                    <div style="font-size:12px; color:#9ca3af;">현재 키워드</div>
                    <div style="font-size:15px; color:#f3f4f6; font-weight:600;">{state.get('current_keyword') or '-'}</div>
                </div>
                <div style="background:#111827; border:1px solid #2b3243; border-radius:10px; padding:12px;">
                    <div style="font-size:12px; color:#9ca3af;">마지막 에러</div>
                    <div style="font-size:15px; color:#f3f4f6; font-weight:600;">{state.get('last_error') or '-'}</div>
                </div>
                <div style="background:#111827; border:1px solid #2b3243; border-radius:10px; padding:12px;">
                    <div style="font-size:12px; color:#9ca3af;">시작 시각</div>
                    <div style="font-size:15px; color:#f3f4f6; font-weight:600;">{_format_timestamp(state.get('started_at'))}</div>
                </div>
                <div style="background:#111827; border:1px solid #2b3243; border-radius:10px; padding:12px;">
                    <div style="font-size:12px; color:#9ca3af;">종료 시각</div>
                    <div style="font-size:15px; color:#f3f4f6; font-weight:600;">{_format_timestamp(state.get('finished_at'))}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_env_badge(label: str, is_ok: bool, detail: str) -> None:
    tone = "#16a34a" if is_ok else "#dc2626"
    background = "rgba(22, 163, 74, 0.14)" if is_ok else "rgba(220, 38, 38, 0.14)"
    st.markdown(
        f"""
        <div style="
            border: 1px solid #2b3243;
            background: #171b26;
            border-radius: 12px;
            padding: 12px 14px;
            margin-bottom: 10px;
        ">
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
                <span style="
                    display:inline-block;
                    padding:2px 8px;
                    border-radius:999px;
                    background:{background};
                    color:{tone};
                    font-size:12px;
                    font-weight:700;
                ">{'READY' if is_ok else 'CHECK'}</span>
                <span style="font-size:14px; font-weight:700; color:#f3f4f6;">{label}</span>
            </div>
            <div style="font-size:12px; color:#9ca3af; word-break:break-all;">{detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=30, show_spinner=False)
def _check_r2_connection(
    account_id: str,
    access_key_id: str,
    secret_access_key: str,
    bucket_name: str,
) -> Dict[str, str]:
    if not all([account_id, access_key_id, secret_access_key, bucket_name]):
        return {"ok": "false", "detail": "R2 환경변수가 아직 모두 채워지지 않았습니다."}

    endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name="auto",
    )
    try:
        client.head_bucket(Bucket=bucket_name)
        return {"ok": "true", "detail": f"{bucket_name} 버킷 연결 확인됨"}
    except (BotoCoreError, ClientError) as exc:
        return {"ok": "false", "detail": str(exc)}


def _render_environment_panel(settings: Any, state: Dict[str, Any]) -> None:
    bright_request_on = bool(state.get("bright_data_enabled"))
    result_locations = state.get("result_locations") or {}
    local_result_file = str(result_locations.get("local_file") or "-")
    r2_key = str(result_locations.get("r2_key") or "").strip()
    r2_ready = all(
        [
            str(settings.r2_account_id or "").strip(),
            str(settings.r2_access_key_id or "").strip(),
            str(settings.r2_secret_access_key or "").strip(),
            str(settings.r2_bucket_name or "").strip(),
        ]
    )
    r2_connection = _check_r2_connection(
        str(settings.r2_account_id or "").strip(),
        str(settings.r2_access_key_id or "").strip(),
        str(settings.r2_secret_access_key or "").strip(),
        str(settings.r2_bucket_name or "").strip(),
    )
    r2_connected = r2_connection.get("ok") == "true"
    r2_connection_detail = r2_connection.get("detail") or ""

    st.subheader("Environment")
    col_a, col_b = st.columns(2)
    col_a.metric("실행 모드", "Bright Request" if bright_request_on else "Playwright")
    col_b.metric("결과 저장", "R2 + Local" if r2_key else ("R2 Ready + Local" if r2_ready else "Local"))

    _render_env_badge(
        "Railway API",
        bool(str(settings.railway_api_base_url or "").strip()),
        str(settings.railway_api_base_url or "설정 필요"),
    )
    _render_env_badge(
        "Crawler Endpoint",
        bool(str(settings.crawler_keywords_endpoint or "").strip()),
        str(settings.crawler_keywords_endpoint or "설정 필요"),
    )
    _render_env_badge(
        "Bright Data Token",
        bool(str(settings.brightdata_api_token or "").strip()),
        "토큰 설정됨" if str(settings.brightdata_api_token or "").strip() else "BRIGHTDATA_API_TOKEN 필요",
    )
    _render_env_badge(
        "Bright Data Zone",
        bool(str(settings.brightdata_request_zone or "").strip()),
        str(settings.brightdata_request_zone or "BRIGHTDATA_REQUEST_ZONE 필요"),
    )
    _render_env_badge(
        "Local Result File",
        bool(local_result_file and local_result_file != "-"),
        local_result_file,
    )
    _render_env_badge(
        "R2 Connection",
        r2_connected,
        r2_connection_detail or ("연결 확인 전" if r2_ready else "R2 설정 필요"),
    )
    _render_env_badge(
        "R2 Key",
        bool(r2_key),
        r2_key or ("연결은 준비되었지만 아직 업로드된 결과가 없습니다." if r2_ready else "현재는 로컬 파일 저장만 사용 중"),
    )


def _format_ai_score_cell(item: Dict[str, Any]) -> str:
    if not item.get("ai_scoring_ready"):
        error = str(item.get("ai_scoring_error") or "").strip()
        return error[:40] if error else "-"
    score = item.get("ai_score")
    tier = str(item.get("ai_tier") or "").strip()
    if score in (None, ""):
        return "-"
    score_text = _format_score_cell(score)
    return f"{score_text} ({tier})" if tier else score_text


def _format_score_cell(value: Any) -> str:
    if value in (None, ""):
        return "-"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "-"
    rounded = round(numeric, 1)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.1f}"


def _enrich_keyword_scores(scores: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    keyword_lookup: Dict[str, Dict[str, Any]] = {}
    try:
        payload = fetch_batch_keywords(limit=200)
        for row in payload.get("keywords") or []:
            keyword = str(row.get("keyword") or "").strip()
            if keyword:
                keyword_lookup[keyword] = row
    except Exception:
        keyword_lookup = {}

    enriched: List[Dict[str, Any]] = []
    for row in scores:
        merged = dict(row)
        if merged.get("naver_score") is None:
            source_row = keyword_lookup.get(str(merged.get("keyword") or "").strip())
            if source_row:
                merged["naver_score"] = compute_naver_final_score(source_row)
        enriched.append(merged)
    return enriched


def _entry_score_dataframe(scores: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for item in sorted(scores, key=lambda row: str(row.get("keyword") or "")):
        keyword = str(item.get("keyword") or "").strip()
        if not keyword:
            continue
        coupang_score = item.get("coupang_score")
        if coupang_score is None:
            coupang_score = item.get("final_score")
        rows.append(
            {
                "키워드명": keyword,
                "쿠팡점수": _format_score_cell(coupang_score),
                "네이버점수": _format_score_cell(item.get("naver_score")),
                "AI점수": _format_ai_score_cell(item),
            }
        )
    return pd.DataFrame(rows)


@st.fragment(run_every=timedelta(seconds=1.5))
def _render_live_runtime() -> None:
    """Streamlit fragment — 진행 지표·상태·로그 주기 갱신."""
    state = get_ui_state()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("실행 상태", str(state.get("status") or "idle"))
    col2.metric("현재 키워드", str(state.get("current_keyword") or "-"))
    col3.metric("진행", f"{int(state.get('current_index') or 0)} / {int(state.get('total_count') or 0)}")
    col4.metric("마지막 실행", _format_timestamp(state.get("last_run_at")))

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("성공", int(state.get("success_count") or 0))
    col6.metric("실패", int(state.get("failure_count") or 0))
    col7.metric("Bright Data", "ON" if state.get("bright_data_enabled") else "OFF")
    col8.metric("결과 저장", "R2 / Local" if state.get("result_locations", {}).get("r2_key") else "Local")

    _render_status_panel(state)

    st.markdown("### 로그")
    log_text = _logs_to_lines(list(state.get("logs") or []))
    if log_text.strip():
        _render_dark_log_box(log_text)
    else:
        st.caption("로그 수집 중…")


@st.fragment(run_every=timedelta(seconds=1.5))
def _render_product_results() -> None:
    state = get_ui_state()
    results = get_ui_results()
    st.markdown("### 상품 결과 테이블")
    result_items = list(results.get("items") or [])
    if result_items:
        df = _result_dataframe(result_items)
        st.dataframe(
            _style_dark_dataframe(df),
            use_container_width=True,
            hide_index=True,
        )
        csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "CSV 다운로드",
            data=csv_bytes,
            file_name="local-crawler-results.csv",
            mime="text/csv",
            key=f"csv-download-{state.get('job_id') or 'idle'}",
        )
    else:
        st.info("아직 표시할 상품 결과가 없습니다.")


@st.fragment(run_every=timedelta(seconds=1.5))
def _render_entry_scoring_tab() -> None:
    results = get_ui_results()
    scores = _enrich_keyword_scores(list(results.get("keyword_scores") or []))
    if not scores:
        st.info("크롤링이 완료된 키워드가 있으면 점수 테이블이 표시됩니다.")
        return

    settings = get_settings()
    gemini_ready = bool(str(settings.gemini_api_key or "").strip())
    if not gemini_ready:
        st.warning(
            "AI점수 사용 시 `local-crawler/.env`에 **GEMINI_API_KEY** 를 설정하세요. "
            "(Google AI Studio API 키, Google Search Grounding 과금 발생)"
        )
    else:
        st.caption(f"Gemini 모델: {settings.gemini_trend_model} · 기준월: {settings.gemini_trend_reference_month}")

    action_col1, action_col2 = st.columns([1, 3])
    with action_col1:
        if st.button("Gemini 트렌드 검증", type="primary", disabled=not gemini_ready):
            with st.spinner("Gemini + Google Search 분석 중…"):
                result = refresh_gemini_trend_scores()
            updated = int(result.get("updated") or 0)
            errors = list(result.get("errors") or [])
            if updated:
                st.success(f"AI점수 {updated}건 갱신")
            if errors:
                st.warning("일부 실패: " + " / ".join(errors[:3]))
            st.rerun()

    st.markdown("### 시장 진입 점수")
    score_df = _entry_score_dataframe(scores)
    if score_df.empty:
        st.info("표시할 키워드 점수가 없습니다.")
        return

    st.dataframe(
        _style_dark_dataframe(score_df),
        use_container_width=True,
        hide_index=True,
    )
    csv_bytes = score_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "점수 CSV 다운로드",
        data=csv_bytes,
        file_name="market-entry-scores.csv",
        mime="text/csv",
        key=f"score-csv-{results.get('job_id') or 'idle'}",
    )


def main() -> None:
    settings = get_settings()
    _apply_dark_theme()

    st.title("Local Crawler Console")
    st.caption("로컬 PC에서 final keywords 배치를 실행하고 상태, 로그, 상품 결과를 확인합니다.")

    with st.sidebar:
        st.subheader("Batch Control")
        keyword_limit = st.number_input(
            "가져올 키워드 수",
            min_value=1,
            max_value=100,
            value=int(settings.crawler_keywords_limit),
            step=1,
        )
        st.caption("배치 실행은 headless로 동작합니다. 브라우저 확인은 준비 모드를 사용하세요.")
        if st.button("배치 시작", use_container_width=True, type="primary"):
            start_batch_run(limit=int(keyword_limit))
            st.rerun()
        if st.button("실패건 재실행", use_container_width=True):
            start_batch_run(limit=int(keyword_limit), retry_failed_only=True)
            st.rerun()
        if st.button("안전 중지", use_container_width=True):
            request_stop()
            st.rerun()

        st.divider()
        _render_environment_panel(settings, get_ui_state())

        st.caption("실행 중 진행·로그·상품 결과는 약 1.5초마다 자동 갱신됩니다.")

    tab_batch, tab_products, tab_scoring = st.tabs(
        ["1. 배치 실행", "2. 상품 결과", "3. 시장 진입 점수"]
    )

    with tab_batch:
        st.markdown("### 배치 대상 미리보기")
        try:
            keyword_payload = fetch_batch_keywords(limit=int(keyword_limit))
            preview_rows = keyword_payload.get("keywords") or []
            if preview_rows:
                preview_df = _preview_dataframe(preview_rows)
                st.dataframe(
                    _style_dark_dataframe(preview_df),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("불러올 final keywords가 없습니다.")
        except Exception as exc:
            st.warning(f"키워드 조회 실패: {exc}")

        _render_live_runtime()

    with tab_products:
        _render_product_results()

    with tab_scoring:
        st.caption(
            "쿠팡점수·네이버점수: 크롤/소싱 데이터 기반 · AI점수: Gemini+Google Search 트렌드 (100점)"
        )
        _render_entry_scoring_tab()


if __name__ == "__main__":
    main()
