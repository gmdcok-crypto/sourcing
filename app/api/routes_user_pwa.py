import json
from html import escape
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

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

    .hero {
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 20px;
      align-items: stretch;
      margin-bottom: 36px;
    }

    .hero-main, .hero-side {
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(18, 26, 47, 0.95), rgba(10, 15, 29, 0.96));
      border-radius: 28px;
      box-shadow: var(--shadow);
    }

    .hero-main {
      padding: 28px;
      min-height: 260px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }

    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: #ffd7df;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 14px;
    }

    .title {
      margin: 0;
      font-size: 46px;
      line-height: 1.06;
      letter-spacing: -0.03em;
    }

    .subtitle {
      margin: 14px 0 0;
      max-width: 760px;
      font-size: 16px;
      line-height: 1.7;
      color: var(--muted);
    }

    .hero-meta {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 28px;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.04);
      color: #dce4ff;
      border-radius: 999px;
      padding: 10px 14px;
      font-size: 13px;
      font-weight: 600;
    }

    .hero-side {
      padding: 24px;
      display: grid;
      gap: 14px;
      align-content: start;
    }

    .stat-card {
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.03);
      border-radius: 20px;
      padding: 16px 18px;
    }

    .stat-label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
      margin-bottom: 8px;
    }

    .stat-value {
      font-size: 28px;
      font-weight: 800;
      letter-spacing: -0.03em;
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
      background:
        linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0)),
        linear-gradient(135deg, rgba(255, 77, 109, 0.18), rgba(110, 168, 255, 0.16));
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
      gap: 10px;
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
      .hero {
        grid-template-columns: 1fr;
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
    <section class="hero">
      <div class="hero-main">
        <div>
          <div class="eyebrow">PC First User PWA</div>
          <h1 class="title">테마별 키워드를 넷플릭스형 카드로 보여주는 사용자 화면</h1>
          <p class="subtitle">
            테마별로 상위 키워드 5개를 한 줄에 배치하고, 카드 호버 시 리뷰평가, 배송평가, 티어를 한 번에 확인할 수 있도록 구성했습니다.
            이후 로그인과 사용자별 URL 매핑을 얹기 쉬운 구조로 설계되어 있습니다.
          </p>
        </div>
        <div class="hero-meta">
          <span class="pill">한 줄 = 한 테마</span>
          <span class="pill">카드당 1개 키워드</span>
          <span class="pill">PC 우선 레이아웃</span>
        </div>
      </div>
      <aside class="hero-side">
        <div class="stat-card">
          <div class="stat-label">최근 소싱 Run</div>
          <div class="stat-value">__RUN_ID__</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">테마 수</div>
          <div class="stat-value">__THEME_COUNT__</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">키워드 카드 수</div>
          <div class="stat-value">__CARD_COUNT__</div>
        </div>
      </aside>
    </section>

    <main id="app">__THEME_ROWS__</main>
  </div>
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
          <button class="btn btn-secondary" type="button">{escape(str(card.get("group_name") or "-"))}</button>
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


@router.get("/api/user/feed")
async def get_user_feed() -> Dict[str, Any]:
    return UserPwaFeedService.build_feed()


@router.get("/user", response_class=HTMLResponse)
async def user_console() -> HTMLResponse:
    payload = UserPwaFeedService.build_feed()
    theme_count = len(payload.get("themes") or [])
    card_count = sum(len(theme.get("cards") or []) for theme in payload.get("themes") or [])
    html = USER_PWA_HTML
    html = html.replace("__RUN_ID__", escape(str(payload.get("run_id") or "-")))
    html = html.replace("__THEME_COUNT__", escape(str(theme_count)))
    html = html.replace("__CARD_COUNT__", escape(str(card_count)))
    html = html.replace("__THEME_ROWS__", _render_theme_rows(payload))
    return HTMLResponse(content=html)
