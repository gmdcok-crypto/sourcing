from __future__ import annotations

import json
from html import escape
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.services.china_1688_url import China1688UrlService
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
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 12px 16px;
      align-items: flex-end;
      margin-bottom: 16px;
      padding: 16px 18px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: var(--panel);
    }
    .score-cards {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      flex: 1;
      min-width: 280px;
      justify-content: flex-start;
    }
    .score-card {
      min-width: 100px;
      padding: 12px 14px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(30, 41, 72, 0.95), rgba(15, 21, 40, 0.98));
    }
    .score-card.is-empty { opacity: 0.55; }
    .score-card-label {
      display: block;
      font-size: 11px;
      font-weight: 700;
      color: var(--muted);
      margin-bottom: 6px;
      letter-spacing: 0.02em;
    }
    .score-card-value {
      display: block;
      font-size: 22px;
      font-weight: 800;
      letter-spacing: -0.02em;
      line-height: 1.1;
    }
    .score-card-value.sub {
      font-size: 12px;
      font-weight: 600;
      color: var(--muted);
      margin-top: 4px;
    }
    .score-card.naver .score-card-value { color: #4ade80; }
    .score-card.coupang .score-card-value { color: #60a5fa; }
    .score-card.ai .score-card-value { color: #f472b6; }
    .score-card.reviews .score-card-value { color: #fbbf24; }
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
    tbody tr {
      cursor: pointer;
    }
    tbody tr:hover { background: rgba(110, 168, 255, 0.08); }
    tbody tr.is-selected {
      background: rgba(110, 168, 255, 0.18);
      outline: 1px solid rgba(110, 168, 255, 0.45);
      outline-offset: -1px;
    }
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
    .btn-1688 {
      padding: 6px 12px;
      border: none;
      border-radius: 8px;
      background: linear-gradient(180deg, #ff7a18, #e65100);
      color: #fff;
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
      white-space: nowrap;
    }
    .btn-1688:disabled {
      opacity: 0.35;
      cursor: not-allowed;
    }
    .btn-1688.is-loading {
      opacity: 0.72;
      cursor: wait;
      min-width: 132px;
    }
    .toast-1688 {
      position: fixed;
      left: 50%;
      bottom: 24px;
      transform: translateX(-50%);
      z-index: 1100;
      max-width: min(92vw, 420px);
      padding: 12px 16px;
      border-radius: 12px;
      background: rgba(18, 26, 47, 0.96);
      border: 1px solid var(--line);
      color: var(--text);
      font-size: 13px;
      line-height: 1.45;
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.45);
    }
    .image-modal {
      position: fixed;
      inset: 0;
      z-index: 1000;
      display: grid;
      place-items: center;
      padding: 24px;
    }
    .image-modal[hidden] { display: none !important; }
    .image-modal-backdrop {
      position: absolute;
      inset: 0;
      background: rgba(0, 0, 0, 0.72);
    }
    .image-modal-panel {
      position: relative;
      z-index: 1;
      max-width: min(92vw, 720px);
      max-height: 90vh;
      padding: 16px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: #121a2f;
      box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55);
    }
    .image-modal-panel img {
      display: block;
      max-width: 100%;
      max-height: calc(90vh - 80px);
      margin: 0 auto;
      border-radius: 12px;
      object-fit: contain;
      background: #0b1020;
    }
    .image-modal-title {
      margin: 0 0 12px;
      font-size: 14px;
      font-weight: 600;
      color: var(--muted);
      line-height: 1.4;
      max-height: 3em;
      overflow: hidden;
    }
    .image-modal-close {
      position: absolute;
      top: 8px;
      right: 8px;
      width: 36px;
      height: 36px;
      border: none;
      border-radius: 999px;
      background: rgba(255,255,255,0.12);
      color: #fff;
      font-size: 22px;
      line-height: 1;
      cursor: pointer;
    }
  </style>
</head>
<body>
  <div class="shell">
    <h1>소싱 상품 결과</h1>
    <div class="toolbar">
      <div class="field">
        <label for="theme-select">테마 (카테고리)</label>
        <select id="theme-select" aria-label="테마 선택"></select>
      </div>
      <div class="score-cards" id="score-cards">
        <div class="score-card naver is-empty">
          <span class="score-card-label">네이버</span>
          <span class="score-card-value" id="card-naver">-</span>
        </div>
        <div class="score-card coupang is-empty">
          <span class="score-card-label">쿠팡</span>
          <span class="score-card-value" id="card-coupang">-</span>
        </div>
        <div class="score-card ai is-empty">
          <span class="score-card-label">AI</span>
          <span class="score-card-value" id="card-ai">-</span>
          <span class="score-card-value sub" id="card-ai-tier"></span>
        </div>
        <div class="score-card reviews is-empty">
          <span class="score-card-label">리뷰수</span>
          <span class="score-card-value" id="card-reviews">-</span>
        </div>
      </div>
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
            <th>이미지</th>
          </tr>
        </thead>
        <tbody id="product-rows"></tbody>
      </table>
      <div class="empty" id="empty-state" hidden>선택한 테마에 표시할 상품이 없습니다.</div>
    </div>
  </div>
  <div id="image-modal" class="image-modal" hidden>
    <div class="image-modal-backdrop" data-close-modal></div>
    <div class="image-modal-panel" role="dialog" aria-modal="true" aria-label="상품 이미지">
      <button type="button" class="image-modal-close" data-close-modal aria-label="닫기">×</button>
      <p class="image-modal-title" id="modal-title"></p>
      <img id="modal-image" alt="" />
    </div>
  </div>
  <script id="product-data" type="application/json">__PRODUCT_DATA_JSON__</script>
  <script>
    const payload = JSON.parse(document.getElementById("product-data").textContent || "{}");
    const allProducts = Array.isArray(payload.products) ? payload.products : [];
    const themes = Array.isArray(payload.themes) ? payload.themes : [];
    const china1688Configured = payload.china_1688_configured === true;
    const select = document.getElementById("theme-select");
    const tbody = document.getElementById("product-rows");
    const emptyState = document.getElementById("empty-state");
    const imageModal = document.getElementById("image-modal");
    const modalImage = document.getElementById("modal-image");
    const modalTitle = document.getElementById("modal-title");
    const cardNaver = document.getElementById("card-naver");
    const cardCoupang = document.getElementById("card-coupang");
    const cardAi = document.getElementById("card-ai");
    const cardAiTier = document.getElementById("card-ai-tier");
    const cardReviews = document.getElementById("card-reviews");
    const scoreCardEls = document.querySelectorAll(".score-card");
    let selectedTr = null;

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

    function isMobileClient() {
      if (window.matchMedia("(pointer: coarse)").matches) return true;
      if (navigator.maxTouchPoints > 0 && window.matchMedia("(max-width: 900px)").matches) {
        return true;
      }
      return /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || "");
    }

    function show1688Hint() {
      const existing = document.getElementById("toast-1688");
      if (existing) existing.remove();
      const toast = document.createElement("div");
      toast.id = "toast-1688";
      toast.className = "toast-1688";
      toast.textContent =
        "1688 링크를 열었습니다. 슬라이더(滑动验证) 인증이 나오면 직접 밀어주세요. 화면이 비어 있으면 새로고침 후 같은 상품에서 다시 눌러 주세요.";
      document.body.appendChild(toast);
      window.setTimeout(() => toast.remove(), 8000);
    }

    async function open1688Search(btn, imageUrl, title) {
      if (!imageUrl) return;
      if (!china1688Configured) {
        alert("1688 이미지 검색이 서버에 설정되지 않았습니다. (Bright Data 브라우저 WS)");
        return;
      }
      btn.disabled = true;
      btn.classList.add("is-loading");
      const prevLabel = btn.textContent;
      btn.textContent = "1688 생성 중…";

      try {
        const response = await fetch("/api/user/1688/search-url", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image_url: imageUrl }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.detail || data.error || "1688 URL 생성 실패");
        }
        if (data.search_url) {
          window.open(data.search_url, "_blank", "noopener,noreferrer");
          show1688Hint();
        } else {
          alert(data.error || "1688 URL을 만들지 못했습니다.");
        }
      } catch (error) {
        alert(error instanceof Error ? error.message : "1688 URL 생성 중 오류");
      } finally {
        btn.disabled = false;
        btn.classList.remove("is-loading");
        btn.textContent = prevLabel;
      }
    }

    function openImagePopup(imageUrl, title) {
      if (!imageUrl) return;
      modalImage.src = imageUrl;
      modalImage.alt = title || "상품 이미지";
      modalTitle.textContent = title || "";
      imageModal.hidden = false;
      document.body.style.overflow = "hidden";
    }

    function closeImagePopup() {
      imageModal.hidden = true;
      modalImage.removeAttribute("src");
      document.body.style.overflow = "";
    }

    imageModal.addEventListener("click", (event) => {
      if (event.target.closest("[data-close-modal]")) closeImagePopup();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !imageModal.hidden) closeImagePopup();
    });

    function clearScoreCards() {
      cardNaver.textContent = "-";
      cardCoupang.textContent = "-";
      cardAi.textContent = "-";
      cardAiTier.textContent = "";
      cardReviews.textContent = "-";
      scoreCardEls.forEach((el) => el.classList.add("is-empty"));
      if (selectedTr) {
        selectedTr.classList.remove("is-selected");
        selectedTr = null;
      }
    }

    function updateScoreCards(row) {
      if (!row) {
        clearScoreCards();
        return;
      }
      cardNaver.textContent = fmtScore(row.naver_score);
      cardCoupang.textContent = fmtScore(row.coupang_score);
      const aiScore = row.ai_score;
      if (aiScore != null && aiScore !== "") {
        cardAi.textContent = fmtScore(aiScore);
        cardAiTier.textContent = row.ai_tier ? String(row.ai_tier) : "";
      } else {
        cardAi.textContent = "-";
        cardAiTier.textContent = "";
      }
      cardReviews.textContent = fmtNum(row.review_count);
      scoreCardEls.forEach((el) => el.classList.remove("is-empty"));
    }

    function selectTableRow(tr, row) {
      if (selectedTr) selectedTr.classList.remove("is-selected");
      selectedTr = tr;
      tr.classList.add("is-selected");
      updateScoreCards(row);
    }

    function renderRows(themeName) {
      clearScoreCards();
      const rows = allProducts.filter((row) => row.theme_name === themeName);
      tbody.innerHTML = "";
      if (!rows.length) {
        emptyState.hidden = false;
        return;
      }
      emptyState.hidden = true;

      for (const row of rows) {
        const tr = document.createElement("tr");
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
          <td class="link-cell"></td>
          <td class="image-cell"></td>
        `;

        const linkCell = tr.querySelector(".link-cell");
        if (row.product_url) {
          const linkBtn = document.createElement("a");
          linkBtn.className = "link-btn";
          linkBtn.href = row.product_url;
          linkBtn.target = "_blank";
          linkBtn.rel = "noreferrer";
          linkBtn.textContent = "열기";
          linkCell.appendChild(linkBtn);
        } else {
          linkCell.textContent = "-";
        }

        const imageCell = tr.querySelector(".image-cell");
        const imgBtn = document.createElement("button");
        imgBtn.type = "button";
        imgBtn.className = "btn-1688";
        imgBtn.textContent = "1688";
        const imageUrl = String(row.image_url || "").trim();
        if (imageUrl) {
          imgBtn.addEventListener("click", (event) => {
            event.stopPropagation();
            if (isMobileClient()) {
              open1688Search(imgBtn, imageUrl, row.title || "");
            } else {
              openImagePopup(imageUrl, row.title || "");
            }
          });
        } else {
          imgBtn.disabled = true;
        }
        imageCell.appendChild(imgBtn);

        tr.addEventListener("click", (event) => {
          if (event.target.closest("a, button")) return;
          selectTableRow(tr, row);
        });

        tbody.appendChild(tr);
      }
    }

    if (!themes.length) {
      select.innerHTML = '<option value="">데이터 없음</option>';
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


class China1688SearchRequest(BaseModel):
    image_url: str = Field(min_length=1)


@router.post("/api/user/1688/search-url")
async def create_1688_search_url(body: China1688SearchRequest) -> Dict[str, Any]:
    if not China1688UrlService.is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Bright Data browser WS is not configured "
                "(BRIGHTDATA_BROWSER_WS or BRIGHTDATA_BROWSER_WS_1688)"
            ),
        )

    result = await China1688UrlService.generate_url(body.image_url)
    if result.status != "URL_OK" or not result.search_url:
        raise HTTPException(
            status_code=502,
            detail=result.error or f"1688 URL generation failed ({result.status})",
        )

    return {
        "status": result.status,
        "search_url": result.search_url,
        "image_id": result.image_id,
        "fetch_source": result.fetch_source,
        "browser_country": result.browser_country,
    }


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
    payload["china_1688_configured"] = China1688UrlService.is_configured()
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = USER_PWA_HTML.replace("__PRODUCT_DATA_JSON__", data_json)
    return HTMLResponse(content=html)
