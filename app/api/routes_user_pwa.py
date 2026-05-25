from html import escape
from typing import Any, Dict
from urllib.parse import quote, urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
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
  <title>소싱 사용자 화면</title>
  <meta name="theme-color" content="#0a0f1d" />
  <style>
    :root {
      --bg: #0a0f1d;
      --bg-soft: #10172b;
      --card: #121a2f;
      --line: rgba(255,255,255,0.08);
      --text: #f5f7ff;
      --muted: #9aa8c7;
      --accent: #ff4d6d;
      --accent-2: #6ea8ff;
      --shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
      --radius: 22px;
    }

    * { box-sizing: border-box; }
    html, body {
      margin: 0;
      padding: 0;
      background:
        radial-gradient(circle at top right, rgba(255, 77, 109, 0.18), transparent 28%),
        radial-gradient(circle at top left, rgba(110, 168, 255, 0.16), transparent 30%),
        linear-gradient(180deg, #060b16 0%, #0a0f1d 42%, #09111d 100%);
      color: var(--text);
      font-family: Inter, "Segoe UI", Arial, sans-serif;
      min-height: 100%;
    }

    body { padding: 28px 32px 72px; }
    a { color: inherit; text-decoration: none; }

    .shell {
      max-width: 1600px;
      margin: 0 auto;
    }

    .page-title {
      margin: 0 0 20px;
      font-size: 34px;
      font-weight: 800;
      letter-spacing: -0.03em;
      color: #f8fbff;
    }

    .theme-section {
      margin-bottom: 34px;
    }

    .theme-header {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }

    .theme-title {
      margin: 0;
      font-size: 26px;
      font-weight: 800;
      letter-spacing: -0.02em;
    }

    .theme-detail {
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
    }

    .row-track {
      display: grid;
      grid-template-columns: repeat(5, minmax(240px, 1fr));
      gap: 18px;
      overflow-x: auto;
      padding: 12px 4px 30px;
      scrollbar-width: thin;
    }

    .row-track::-webkit-scrollbar {
      height: 10px;
    }

    .row-track::-webkit-scrollbar-thumb {
      background: rgba(255,255,255,0.14);
      border-radius: 999px;
    }

    .card {
      position: relative;
      min-height: 340px;
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: var(--radius);
      background: linear-gradient(180deg, rgba(19, 27, 48, 0.98), rgba(10, 15, 28, 1));
      overflow: hidden;
      box-shadow: 0 20px 40px rgba(0,0,0,0.34);
      transform-origin: center;
      transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
    }

    .card:hover {
      transform: translateY(-10px) scale(1.035);
      box-shadow: 0 36px 64px rgba(0,0,0,0.5);
      border-color: rgba(255,255,255,0.16);
      z-index: 4;
    }

    .media {
      position: relative;
      aspect-ratio: 1 / 1.08;
      background: #ffffff;
      overflow: hidden;
    }

    .media img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      object-position: center;
      display: block;
      padding: 10px;
      transition: transform 0.28s ease, filter 0.28s ease;
    }

    .card:hover .media img {
      transform: scale(1.08);
      filter: saturate(1.06);
    }

    .media-empty {
      width: 100%;
      height: 100%;
      display: grid;
      place-items: center;
      color: rgba(255,255,255,0.68);
      font-weight: 700;
      font-size: 18px;
      letter-spacing: 0.04em;
    }

    .media-overlay {
      position: absolute;
      inset: 0;
      background: linear-gradient(180deg, rgba(5, 9, 18, 0.02) 0%, rgba(5, 9, 18, 0.06) 25%, rgba(5, 9, 18, 0.78) 100%);
    }

    .card-body {
      padding: 16px 16px 18px;
    }

    .card-keyword {
      font-size: 22px;
      font-weight: 800;
      letter-spacing: -0.03em;
      margin: 0 0 8px;
    }

    .card-title {
      font-size: 13px;
      line-height: 1.55;
      color: #dce4ff;
      min-height: 40px;
      margin-bottom: 14px;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .top-line {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }

    .chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 10px;
      border: 1px solid rgba(255,255,255,0.08);
      background: rgba(255,255,255,0.04);
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      color: #eef2ff;
    }

    .chip.tier-premium { background: rgba(255, 215, 87, 0.16); color: #ffe694; }
    .chip.tier-diamond { background: rgba(95, 196, 255, 0.14); color: #9edfff; }
    .chip.tier-gold { background: rgba(255, 190, 92, 0.16); color: #ffd28c; }
    .chip.tier-raw_gem { background: rgba(102, 224, 162, 0.14); color: #92e8b6; }
    .chip.tier-unknown { background: rgba(255,255,255,0.08); color: #e8ecff; }

    .metric-list {
      display: grid;
      gap: 12px;
    }

    .metric-row {
      display: grid;
      grid-template-columns: 92px 1fr;
      gap: 10px;
      align-items: start;
    }

    .metric-label {
      font-size: 12px;
      font-weight: 700;
      color: var(--muted);
      padding-top: 1px;
    }

    .metric-value {
      font-size: 13px;
      line-height: 1.6;
      color: #f2f5ff;
    }

    .delivery-list {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }

    .delivery-pill {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      border-radius: 999px;
      padding: 6px 9px;
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.08);
      font-size: 11px;
      color: #dfe7ff;
      white-space: nowrap;
    }

    .actions {
      margin-top: 16px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 108px;
      padding: 10px 14px;
      border-radius: 12px;
      border: 1px solid transparent;
      font-weight: 700;
      font-size: 13px;
      cursor: pointer;
      transition: all 0.18s ease;
    }

    .btn-primary {
      background: linear-gradient(135deg, var(--accent), #ff7d5f);
      color: white;
      box-shadow: 0 14px 28px rgba(255, 77, 109, 0.28);
    }

    .btn-secondary {
      background: rgba(255,255,255,0.04);
      border-color: rgba(255,255,255,0.08);
      color: #eef2ff;
    }

    .btn-1688 {
      background: linear-gradient(135deg, #ff8a00, #ffb347);
      color: #1a1208;
      box-shadow: 0 14px 28px rgba(255, 138, 0, 0.22);
    }

    .btn-1688:disabled {
      opacity: 0.72;
      cursor: wait;
      transform: none;
    }

    .btn-1688.is-loading {
      min-width: 132px;
    }

    .btn-1688-drag {
      background: linear-gradient(135deg, #47c087, #7ddea8);
      color: #082116;
      box-shadow: 0 14px 28px rgba(71, 192, 135, 0.22);
      min-width: 96px;
    }

    .toast-1688 {
      position: fixed;
      left: 50%;
      bottom: 28px;
      transform: translateX(-50%);
      max-width: min(92vw, 560px);
      padding: 14px 18px;
      border-radius: 14px;
      border: 1px solid rgba(255, 180, 80, 0.35);
      background: rgba(18, 14, 8, 0.94);
      color: #ffe8c7;
      font-size: 13px;
      line-height: 1.55;
      box-shadow: 0 18px 40px rgba(0, 0, 0, 0.45);
      z-index: 20;
      animation: toast-in 0.2s ease;
    }

    @keyframes toast-in {
      from { opacity: 0; transform: translateX(-50%) translateY(8px); }
      to { opacity: 1; transform: translateX(-50%) translateY(0); }
    }

    .empty {
      border: 1px dashed rgba(255,255,255,0.14);
      border-radius: 24px;
      padding: 48px 28px;
      color: var(--muted);
      text-align: center;
      background: rgba(255,255,255,0.02);
    }

    @media (max-width: 1360px) {
      .row-track {
        grid-template-columns: repeat(5, 260px);
      }
    }

    @media (max-width: 980px) {
      body {
        padding: 20px 20px 56px;
      }
      .title {
        font-size: 38px;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <h1 class="page-title">소싱 Ai</h1>
    <main id="app">__THEME_ROWS__</main>
  </div>
  <script>
    const ALIBABA_1688_UPLOAD_URL = "https://s.1688.com/youyuan/index.htm";

    function show1688Hint() {
      const existing = document.getElementById("toast-1688");
      if (existing) existing.remove();

      const toast = document.createElement("div");
      toast.id = "toast-1688";
      toast.className = "toast-1688";
      toast.textContent =
        "1688 탭이 열렸습니다. 슬라이더(滑动验证) 인증이 나오면 직접 밀어주세요. 한국에서 열면 자주 나오며, 한 번 통과하면 같은 탭에서는 다시 안 나올 수 있습니다.";
      document.body.appendChild(toast);
      window.setTimeout(() => toast.remove(), 8000);
    }

    function showDragGuideToast() {
      const existing = document.getElementById("toast-1688");
      if (existing) existing.remove();

      const toast = document.createElement("div");
      toast.id = "toast-1688";
      toast.className = "toast-1688";
      toast.textContent =
        "왼쪽 작은 「이미지」 창에서 사진을 1688 업로드 칸으로 드래그하세요. PWA는 가리지 않습니다.";
      document.body.appendChild(toast);
      window.setTimeout(() => toast.remove(), 9000);
    }

    function buildDragHelperUrl(imageUrl, keyword) {
      const params = new URLSearchParams({
        url: imageUrl,
        keyword: keyword || "",
      });
      return `/user/1688-drag-image?${params.toString()}`;
    }

    let dragPopupWindow = null;

    function openDragPopup(imageUrl, keyword) {
      const url = buildDragHelperUrl(imageUrl, keyword);
      const features = [
        "popup=yes",
        "width=340",
        "height=420",
        "left=24",
        "top=72",
        "resizable=yes",
        "scrollbars=no",
        "toolbar=no",
        "menubar=no",
        "location=no",
        "status=no",
      ].join(",");

      if (dragPopupWindow && !dragPopupWindow.closed) {
        dragPopupWindow.location.href = url;
        dragPopupWindow.focus();
        return;
      }

      dragPopupWindow = window.open(url, "pwa1688DragImage", features);
      if (dragPopupWindow) {
        dragPopupWindow.focus();
      }
    }

    function open1688Drag(btn) {
      const imageUrl = (btn.dataset.imageUrl || "").trim();
      const keyword = (btn.dataset.keyword || "").trim();
      if (!imageUrl) {
        alert("쿠팡 이미지 URL이 없습니다.");
        return;
      }

      window.open(ALIBABA_1688_UPLOAD_URL, "_blank", "noopener,noreferrer");
      openDragPopup(imageUrl, keyword);
      showDragGuideToast();
    }

    async function open1688Search(btn) {
      const imageUrl = (btn.dataset.imageUrl || "").trim();
      if (!imageUrl) {
        alert("쿠팡 이미지 URL이 없습니다.");
        return;
      }

      const originalLabel = btn.textContent;
      btn.disabled = true;
      btn.classList.add("is-loading");
      btn.textContent = "1688 생성 중…";

      try {
        const response = await fetch("/api/user/1688/search-url", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image_url: imageUrl }),
        });
        const data = await response.json();
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
        btn.textContent = originalLabel;
      }
    }

    document.querySelectorAll(".btn-1688").forEach((btn) => {
      btn.addEventListener("click", () => open1688Search(btn));
    });

    document.querySelectorAll(".btn-1688-drag").forEach((btn) => {
      btn.addEventListener("click", () => open1688Drag(btn));
    });
  </script>
</body>
</html>
"""


DRAG_IMAGE_HELPER_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=340, initial-scale=1.0" />
  <title>1688 드래그</title>
  <style>
    * { box-sizing: border-box; }
    html, body {
      margin: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: #f8fafc;
      color: #111827;
      font-family: Inter, "Segoe UI", Arial, sans-serif;
    }
    body {
      display: flex;
      flex-direction: column;
      padding: 12px;
      gap: 10px;
    }
    .title {
      margin: 0;
      font-size: 15px;
      font-weight: 800;
      line-height: 1.35;
    }
    .sub {
      margin: 0;
      font-size: 11px;
      line-height: 1.5;
      color: #6b7280;
    }
    .frame {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      border: 2px dashed #34a56f;
      border-radius: 14px;
      background: #ffffff;
      padding: 10px;
      min-height: 0;
    }
    img {
      max-width: 100%;
      max-height: 210px;
      object-fit: contain;
      cursor: grab;
      user-select: none;
    }
    img:active { cursor: grabbing; }
    .hint {
      margin-top: 8px;
      font-size: 11px;
      font-weight: 700;
      color: #166534;
      text-align: center;
      line-height: 1.45;
    }
    .loading {
      color: #6b7280;
      font-size: 13px;
    }
    .actions {
      display: flex;
      gap: 8px;
      justify-content: center;
      flex-wrap: wrap;
    }
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 8px 10px;
      border-radius: 8px;
      border: 1px solid #d1d5db;
      background: #ffffff;
      color: #111827;
      font-size: 11px;
      font-weight: 700;
      text-decoration: none;
      cursor: pointer;
    }
    .btn-primary {
      background: #34a56f;
      border-color: #34a56f;
      color: #ffffff;
    }
  </style>
</head>
<body>
  <h1 class="title">__KEYWORD__</h1>
  <p class="sub">작은 창을 1688 옆에 두고, 아래 이미지를 업로드 칸으로 드래그하세요.</p>
  <div class="frame">
    <div class="loading" id="loading">불러오는 중…</div>
    <img id="drag-image" alt="상품 이미지" draggable="false" hidden />
    <div class="hint" id="hint" hidden>1688 「上传图片」 점선 영역에 드롭</div>
  </div>
  <div class="actions">
    <a class="btn btn-primary" href="https://s.1688.com/youyuan/index.htm" target="_blank" rel="noreferrer">1688</a>
    <a class="btn" id="download-link" href="#" download hidden>저장</a>
  </div>
  <script>
    const PROXY_URL = "__PROXY_URL__";

    function setSmallDragImage(event, img) {
      const size = 88;
      const canvas = document.createElement("canvas");
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext("2d");
      if (!ctx || !img.naturalWidth) return;
      const ratio = Math.min(size / img.naturalWidth, size / img.naturalHeight);
      const width = img.naturalWidth * ratio;
      const height = img.naturalHeight * ratio;
      ctx.drawImage(img, (size - width) / 2, (size - height) / 2, width, height);
      event.dataTransfer.setDragImage(canvas, size / 2, size / 2);
    }

    async function boot() {
      const img = document.getElementById("drag-image");
      const loading = document.getElementById("loading");
      const hint = document.getElementById("hint");
      const downloadLink = document.getElementById("download-link");

      try {
        const response = await fetch(PROXY_URL);
        if (!response.ok) throw new Error("이미지 로드 실패");
        const blob = await response.blob();
        const objectUrl = URL.createObjectURL(blob);
        img.src = objectUrl;
        img.onload = () => {
          img.hidden = false;
          img.draggable = true;
          loading.hidden = true;
          hint.hidden = false;
          downloadLink.href = objectUrl;
          downloadLink.download = "__FILENAME__";
          downloadLink.hidden = false;
        };
        img.addEventListener("dragstart", (event) => {
          if (!event.dataTransfer) return;
          event.dataTransfer.effectAllowed = "copy";
          event.dataTransfer.setData("text/plain", "coupang-product-image");
          setSmallDragImage(event, img);
        });
      } catch (error) {
        loading.textContent = error instanceof Error ? error.message : "이미지 준비 실패";
      }
    }

    boot();
  </script>
</body>
</html>
"""


def _render_delivery_mix(items: Any) -> str:
    values = list(items or [])
    if not values:
        return '<span class="delivery-pill">데이터 없음</span>'
    return "".join(
        f'<span class="delivery-pill">{escape(str(item.get("label") or "-"))} {int(item.get("ratio") or 0)}%</span>'
        for item in values
    )


def _render_card(card: Dict[str, Any]) -> str:
    image_url = str(card.get("top_product_image_url") or "").strip()
    image_markup = (
        f'<img src="{escape(image_url)}" alt="{escape(str(card.get("keyword") or ""))}" loading="lazy" />'
        if image_url
        else '<div class="media-empty">NO IMAGE</div>'
    )
    price_value = card.get("top_product_price")
    price_text = f"{int(price_value):,}원" if isinstance(price_value, int) and price_value > 0 else "-"
    review_avg = card.get("review_count_average")
    review_avg_text = f"{int(review_avg):,}" if isinstance(review_avg, int) else "데이터 없음"
    tier_key = escape(str(card.get("tier_key") or "unknown"))
    tier_label = escape(str(card.get("tier_label") or "⚪ 미검증"))
    tier_reason = escape(str(card.get("tier_reason") or "데이터 없음"))
    top_title = escape(str(card.get("top_product_title") or "상위 상품 데이터 없음"))
    keyword = escape(str(card.get("keyword") or ""))
    product_url = escape(str(card.get("top_product_url") or "#"))
    raw_image_url = escape(image_url)

    return f"""
    <article class="card">
      <div class="media">
        {image_markup}
        <div class="media-overlay"></div>
      </div>
      <div class="card-body">
        <h3 class="card-keyword">{keyword}</h3>
        <div class="card-title">{top_title}</div>
        <div class="top-line">
          <span class="chip tier-{tier_key}">{tier_label}</span>
          <span class="chip">1위 {price_text}</span>
        </div>
        <div class="metric-list">
          <div class="metric-row">
            <div class="metric-label">리뷰평가</div>
            <div class="metric-value">평균 리뷰수 {review_avg_text}</div>
          </div>
          <div class="metric-row">
            <div class="metric-label">배송평가</div>
            <div class="metric-value">
              <div class="delivery-list">{_render_delivery_mix(card.get("delivery_mix"))}</div>
            </div>
          </div>
          <div class="metric-row">
            <div class="metric-label">등급</div>
            <div class="metric-value">{tier_reason}</div>
          </div>
        </div>
        <div class="actions">
          <a class="btn btn-primary" href="{product_url}" target="_blank" rel="noreferrer">상품 보기</a>
          <button
            class="btn btn-1688-drag"
            type="button"
            data-image-url="{raw_image_url}"
            data-keyword="{keyword}"
            {"disabled" if not image_url else ""}
          >1688 드래그</button>
          <button
            class="btn btn-1688"
            type="button"
            data-image-url="{raw_image_url}"
            data-keyword="{keyword}"
            {"disabled" if not image_url else ""}
          >1688 图搜</button>
        </div>
      </div>
    </article>
    """


def _render_theme_rows(payload: Dict[str, Any]) -> str:
    themes = list(payload.get("themes") or [])
    if not themes:
        return """
        <section class="empty">
          아직 사용자 화면에 표시할 테마 데이터가 없습니다.<br />
          먼저 키워드 소싱과 쿠팡 결과가 준비되면 이 화면이 채워집니다.
        </section>
        """

    chunks = []
    for theme in themes:
        cards = "".join(_render_card(card) for card in list(theme.get("cards") or []))
        chunks.append(
            f"""
            <section class="theme-section">
              <div class="theme-header">
                <div>
                  <h2 class="theme-title">{escape(str(theme.get("theme_name") or ""))}</h2>
                  <div class="theme-detail">{escape(str(theme.get("theme_detail") or ""))}</div>
                </div>
              </div>
              <div class="row-track">{cards}</div>
            </section>
            """
        )
    return "".join(chunks)


class China1688SearchRequest(BaseModel):
    image_url: str = Field(min_length=1)


def _is_allowed_product_image_url(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    return host.endswith("coupangcdn.com") or host.endswith("coupang.com")


@router.get("/api/user/image-proxy")
async def proxy_product_image(
    url: str = Query(..., min_length=8),
) -> Response:
    image_url = str(url or "").strip()
    if not _is_allowed_product_image_url(image_url):
        raise HTTPException(status_code=400, detail="unsupported image url")

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(image_url)
            response.raise_for_status()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"image_download_failed: {exc}",
        ) from exc

    content_type = response.headers.get("content-type") or "image/jpeg"
    if not content_type.startswith("image/"):
        content_type = "image/jpeg"

    return Response(
        content=response.content,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.post("/api/user/1688/search-url")
async def create_1688_search_url(body: China1688SearchRequest) -> Dict[str, Any]:
    if not China1688UrlService.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Bright Data browser WS is not configured (BRIGHTDATA_BROWSER_WS or BRIGHTDATA_BROWSER_WS_1688)",
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


@router.get("/api/user/feed")
async def get_user_feed() -> Dict[str, Any]:
    return UserPwaFeedService.build_feed()


@router.get("/user/1688-drag-image", response_class=HTMLResponse)
async def drag_image_helper(
    url: str = Query(..., min_length=8),
    keyword: str = Query(""),
) -> HTMLResponse:
    image_url = str(url or "").strip()
    if not _is_allowed_product_image_url(image_url):
        raise HTTPException(status_code=400, detail="unsupported image url")

    safe_keyword = escape(str(keyword or "").strip() or "1688 드래그용 이미지")
    safe_filename = (
        str(keyword or "coupang")
        .strip()
        .replace(" ", "_")
        .encode("ascii", "ignore")
        .decode("ascii")[:40]
        or "coupang"
    )
    proxy_url = f"/api/user/image-proxy?url={quote(image_url, safe='')}"
    html = DRAG_IMAGE_HELPER_HTML
    html = html.replace("__KEYWORD__", safe_keyword)
    html = html.replace("__PROXY_URL__", proxy_url)
    html = html.replace("__FILENAME__", f"{safe_filename}.jpg")
    return HTMLResponse(content=html)


@router.get("/user", response_class=HTMLResponse)
async def user_console() -> HTMLResponse:
    payload = UserPwaFeedService.build_feed()
    html = USER_PWA_HTML
    html = html.replace("__THEME_ROWS__", _render_theme_rows(payload))
    return HTMLResponse(content=html)
