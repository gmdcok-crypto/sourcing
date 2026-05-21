from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from config import get_settings
from ui_runner import (
    fetch_batch_keywords,
    get_ui_results,
    get_ui_state,
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
        </style>
        """,
        unsafe_allow_html=True,
    )


def _format_timestamp(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "-"
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
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


def _result_dataframe(items: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for item in items:
        rows.append(
            {
                "keyword": item.get("keyword"),
                "rank": item.get("rank"),
                "image_url": item.get("image_url"),
                "title": item.get("title"),
                "price": item.get("price"),
                "review_count": item.get("review_count"),
                "review_score": item.get("review_score"),
                "delivery_type": item.get("delivery_type"),
                "shipping_fee": item.get("shipping_fee"),
                "product_url": item.get("product_url"),
                "reason_code": item.get("reason_code"),
                "fetch_source": item.get("fetch_source"),
            }
        )
    return pd.DataFrame(rows)


def _auto_refresh_when_active(status: str, refresh_seconds: int) -> None:
    if status not in {"starting", "running"}:
        return
    delay_ms = max(1, int(refresh_seconds or 5)) * 1000
    components.html(
        f"""
        <script>
        setTimeout(function() {{
            window.parent.location.reload();
        }}, {delay_ms});
        </script>
        """,
        height=0,
    )


def main() -> None:
    settings = get_settings()
    state = get_ui_state()
    results = get_ui_results()
    _apply_dark_theme()
    _auto_refresh_when_active(str(state.get("status") or ""), int(settings.ui_refresh_seconds))

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
        st.subheader("Environment")
        st.write(f"Railway API: `{settings.railway_api_base_url}`")
        st.write(f"Bright Data Request: `{'on' if state.get('bright_data_enabled') else 'off'}`")
        st.write(f"결과 파일: `{state.get('result_locations', {}).get('local_file') or '-'}`")

        if st.button("새로고침", use_container_width=True):
            st.rerun()

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

    st.markdown("### 실행 상태")
    st.write(f"메시지: `{state.get('message') or '-'}`")
    st.write(f"마지막 에러: `{state.get('last_error') or '-'}`")
    st.write(f"시작 시각: `{_format_timestamp(state.get('started_at'))}`")
    st.write(f"종료 시각: `{_format_timestamp(state.get('finished_at'))}`")

    st.markdown("### 배치 대상 미리보기")
    try:
        keyword_payload = fetch_batch_keywords(limit=int(keyword_limit))
        preview_rows = keyword_payload.get("keywords") or []
        if preview_rows:
            st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
        else:
            st.info("불러올 final keywords가 없습니다.")
    except Exception as exc:
        st.warning(f"키워드 조회 실패: {exc}")

    st.markdown("### 상품 결과 테이블")
    result_items = list(results.get("items") or [])
    if result_items:
        df = _result_dataframe(result_items)
        st.dataframe(df, use_container_width=True, hide_index=True)
        csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "CSV 다운로드",
            data=csv_bytes,
            file_name="local-crawler-results.csv",
            mime="text/csv",
        )
    else:
        st.info("아직 표시할 상품 결과가 없습니다.")

    st.markdown("### 로그")
    st.text_area(
        "실시간 로그",
        value=_logs_to_lines(list(state.get("logs") or [])),
        height=260,
    )


if __name__ == "__main__":
    main()
