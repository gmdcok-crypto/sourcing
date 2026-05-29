from __future__ import annotations

import json
from html import escape
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.services.user_pwa import UserPwaFeedService

router = APIRouter(tags=["user-pwa"])


USER_PWA_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>소싱 상품 결과</title>
  <meta name="theme-color" content="#0a0f1d" />
  <style>
    :root {
      --bg: #0a0f1d;
      --panel: #121a2f;
      --line: rgba(255,255,255,0.1);
      --text: #f5f7ff;
      --muted: #9aa8c7;
      --accent: #6ea8ff;
    }
    * { box-sizing: border-box; }
    html, body {
      margin: 0;
      padding: 0;
      min-height: 100%;
      background: linear-gradient(180deg, #060b16 0%, #0a0f1d 100%);
      color: var(--text);
      font-family: Inter, "Segoe UI", Arial, sans-serif;
    }
    body { padding: 24px 20px 48px; }
    .shell { max-width: 1800px; margin: 0 auto; }
    h1 {
      margin: 0 0 8px;
      font-size: 30px;
      font-weight: 800;
      letter-spacing: -0.03em;
    }
    .sub {
      margin: 0 0 20px;
      color: var(--muted);
      font-size: 14px;
    }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 12px 20px;
      align-items: end;
      margin-bottom: 16px;
      padding: 16px 18px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: var(--panel);
    }
    .field label {
      display: block;
      margin-bottom: 6px;
      font-size: 12px;
      color: var(--muted);
      font-weight: 600;
    }
    .field select {
      min-width: 260px;
      padding: 10px 12px;
      border-radius: 10px;
      border: 1px solid var(--line);
      background: #0f1528;
      color: var(--text);
      font-size: 14px;
    }
    .stats {
      font-size: 13px;
      color: var(--muted);
    }
    .stats strong { color: var(--text); }
    .table-wrap {
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: var(--panel);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 1200px;
      font-size: 13px;
    }
    thead th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #1a2440;
      color: #dbeafe;
      text-align: left;
      padding: 12px 10px;
      border-bottom: 1px solid var(--line);
      white-space: nowrap;
      font-weight: 700;
    }
    tbody td {
      padding: 10px;
      border-bottom: 1px solid rgba(255,255,255,0.06);
      vertical-align: top;
    }
    tbody tr:hover { background: rgba(110, 168, 255, 0.08); }
    .title-cell {
      max-width: 280px;
      line-height: 1.35;
      font-weight: 600;
    }
    .num { text-align: right; white-space: nowrap; }
    .link-btn {
      display: inline-block;
      padding: 6px 10px;
      border-radius: 8px;
      background: #2563eb;
      color: #fff;
      font-size: 12px;
      font-weight: 600;
      text-decoration: none;
    }
    .thumb {
      width: 48px;
      height: 48px;
      object-fit: cover;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: #0b1020;
    }
    .empty {
      padding: 48px 24px;
      text-align: center;
      color: var(--muted);
      line-height: 1.6;
    }
    .pill {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      background: rgba(110,168,255,0.15);
      color: #bfdbfe;
      font-size: 11px;
      font-weight: 700;
    }
  </style>
</head>
<body>
  <div class="shell">
    <h1>소싱 상품 결과</h1>
    <p class="sub">로컬 크롤링 R2/결과 파일 기준 · Streamlit 「상품 결과」 테이블과 동일 규칙</p>
    <div class="toolbar">
      <div class="field">
        <label for="theme-select">테마 (카테고리)</label>
        <select id="theme-select" aria-label="테마 선택"></select>
      </div>
      <div class="stats" id="stats"></div>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>키워드</th>
            <th>리뷰순</th>
            <th>검색순위</th>
            <th>상품명</th>
            <th>판매가격</th>
            <th>배송정책</th>
            <th>배송비</th>
            <th>리뷰수</th>
            <th>리뷰별점</th>
            <th>판매량</th>
            <th>쿠팡</th>
            <th>네이버</th>
            <th>AI</th>
            <th>링크</th>
          </tr>
        </thead>
        <tbody id="product-rows"></tbody>
      </table>
      <div class="empty" id="empty-state" hidden>선택한 테마에 표시할 상품이 없습니다.</div>
    </div>
  </div>
  <script id="product-data" type="application/json">__PRODUCT_DATA_JSON__</script>
  <script>
    const payload = JSON.parse(document.getElementById("product-data").textContent || "{}");
    const allProducts = Array.isArray(payload.products) ? payload.products : [];
    const themes = Array.isArray(payload.themes) ? payload.themes : [];
    const select = document.getElementById("theme-select");
    const tbody = document.getElementById("product-rows");
    const stats = document.getElementById("stats");
    const emptyState = document.getElementById("empty-state");

    function fmtNum(value) {
      if (value === null || value === undefined || value === "") return "-";
      const n = Number(value);
      if (Number.isFinite(n)) return n.toLocaleString("ko-KR");
      return String(value);
    }

    function fmtScore(value) {
      if (value === null || value === undefined || value === "") return "-";
      const n = Number(value);
      return Number.isFinite(n) ? n.toFixed(1) : "-";
    }

    function esc(value) {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function renderRows(themeName) {
      const rows = allProducts.filter((row) => row.theme_name === themeName);
      const keywords = new Set(rows.map((row) => row.keyword).filter(Boolean));
      stats.innerHTML =
        `테마 <strong>${themeName || "-"}</strong> · 상품 <strong>${rows.length}</strong>행 · 키워드 <strong>${keywords.size}</strong>개` +
        (payload.generated_at ? ` · 갱신 ${payload.generated_at}` : "");

      tbody.innerHTML = "";
      if (!rows.length) {
        emptyState.hidden = false;
        return;
      }
      emptyState.hidden = true;

      for (const row of rows) {
        const tr = document.createElement("tr");
        const link = row.product_url
          ? `<a class="link-btn" href="${row.product_url}" target="_blank" rel="noreferrer">열기</a>`
          : "-";
        const aiText = row.ai_score != null
          ? `${fmtScore(row.ai_score)}${row.ai_tier ? " (" + row.ai_tier + ")" : ""}`
          : "-";
        tr.innerHTML = `
          <td>${esc(row.keyword) || "-"}</td>
          <td class="num">${fmtNum(row.review_rank)}</td>
          <td class="num">${fmtNum(row.search_rank)}</td>
          <td class="title-cell">${esc(row.title) || "-"}</td>
          <td class="num">${row.price != null ? fmtNum(row.price) + "원" : "-"}</td>
          <td>${esc(row.delivery_type) || "-"}</td>
          <td class="num">${row.shipping_fee === 0 ? "무료" : fmtNum(row.shipping_fee)}</td>
          <td class="num">${fmtNum(row.review_count)}</td>
          <td class="num">${fmtNum(row.review_score)}</td>
          <td><span class="pill">${esc(row.monthly_sales) || "-"}</span></td>
          <td class="num">${fmtScore(row.coupang_score)}</td>
          <td class="num">${fmtScore(row.naver_score)}</td>
          <td class="num">${esc(aiText)}</td>
          <td>${link}</td>
        `;
        tbody.appendChild(tr);
      }
    }

    if (!themes.length) {
      select.innerHTML = '<option value="">데이터 없음</option>';
      stats.textContent = "로컬 크롤 결과가 없습니다. 배치 실행 후 R2 업로드를 확인하세요.";
      emptyState.hidden = false;
    } else {
      select.innerHTML = themes
        .map((t) => `<option value="${esc(t)}">${esc(t)}</option>`)
        .join("");
      const initial = payload.selected_theme && themes.includes(payload.selected_theme)
        ? payload.selected_theme
        : themes[0];
      select.value = initial;
      renderRows(initial);
      select.addEventListener("change", () => renderRows(select.value));
    }
  </script>
</body>
</html>
"""


def _format_score_value(value: Any) -> str:
    if value in (None, ""):
        return "-"
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "-"


@router.get("/api/user/feed")
async def get_user_feed() -> Dict[str, Any]:
    return UserPwaFeedService.build_product_browser()


@router.get("/api/user/products")
async def get_user_products(theme: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    return UserPwaFeedService.build_product_browser(theme_name=theme)


@router.get("/user", response_class=HTMLResponse)
async def user_console() -> HTMLResponse:
    payload = UserPwaFeedService.build_product_browser()
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = USER_PWA_HTML.replace("__PRODUCT_DATA_JSON__", data_json)
    return HTMLResponse(content=html)
