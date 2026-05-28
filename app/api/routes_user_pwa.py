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
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: var(--radius);
      background: linear-gradient(180deg, rgba(19, 27, 48, 0.98), rgba(10, 15, 28, 1));
      overflow: hidden;
      box-shadow: 0 20px 40px rgba(0,0,0,0.34);
      transform-origin: center;
      transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
    }

    .card-media-wrap {
      position: relative;
      display: block;
    }

    @media (hover: none) {
      .card-media-wrap {
        cursor: pointer;
        -webkit-tap-highlight-color: transparent;
      }
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
      pointer-events: none;
      background: linear-gradient(
        180deg,
        rgba(5, 9, 18, 0.02) 0%,
        rgba(5, 9, 18, 0.08) 40%,
        rgba(5, 9, 18, 0.88) 100%
      );
    }

    .card-keyword {
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      z-index: 2;
      margin: 0;
      padding: 42px 16px 14px;
      font-size: 22px;
      font-weight: 800;
      letter-spacing: -0.03em;
      line-height: 1.2;
      color: #f8fbff;
      text-shadow: 0 2px 12px rgba(0, 0, 0, 0.55);
      pointer-events: none;
    }

    @media (hover: none) {
      .card-media-wrap::after {
        content: "탭하여 상세";
        position: absolute;
        right: 12px;
        top: 12px;
        z-index: 3;
        padding: 5px 9px;
        border-radius: 999px;
        background: rgba(10, 15, 28, 0.72);
        border: 1px solid rgba(255,255,255,0.12);
        color: #c7d2fe;
        font-size: 11px;
        font-weight: 700;
        pointer-events: none;
      }

      .card.is-revealed .card-media-wrap::after {
        content: "닫기";
      }
    }

    .card-details {
      max-height: 0;
      opacity: 0;
      overflow: hidden;
      padding: 0 16px;
      pointer-events: none;
      transition:
        max-height 0.32s ease,
        opacity 0.22s ease,
        padding 0.22s ease;
    }

    @media (hover: hover) {
      .card:has(.card-media-wrap:hover) .card-details,
      .card:hover .card-details {
        max-height: 520px;
        opacity: 1;
        padding: 14px 16px 18px;
        pointer-events: auto;
      }

      .card:has(.card-media-wrap:hover),
      .card:hover {
        transform: translateY(-10px) scale(1.035);
        box-shadow: 0 36px 64px rgba(0,0,0,0.5);
        border-color: rgba(255,255,255,0.16);
        z-index: 4;
      }

      .card:has(.card-media-wrap:hover) .media img,
      .card:hover .media img {
        transform: scale(1.08);
        filter: saturate(1.06);
      }
    }

    @media (hover: none) {
      .card.is-revealed .card-details {
        max-height: 520px;
        opacity: 1;
        padding: 14px 16px 18px;
        pointer-events: auto;
      }

      .card.is-revealed {
        transform: translateY(-6px);
        box-shadow: 0 28px 52px rgba(0,0,0,0.46);
        border-color: rgba(255,255,255,0.14);
        z-index: 4;
      }
    }

    .card-scores {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 14px;
    }

    .score-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 11px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.1);
      background: rgba(255,255,255,0.05);
      font-size: 12px;
      line-height: 1;
      color: #c7d2fe;
    }

    .score-pill strong {
      color: #f8fbff;
      font-size: 14px;
      font-weight: 800;
      letter-spacing: -0.02em;
    }

    .score-pill.ai-error {
      border-radius: 12px;
      max-width: 100%;
      white-space: normal;
      line-height: 1.35;
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
    function initCardReveal() {
      const cards = Array.from(document.querySelectorAll("article.card"));
      const touchQuery = window.matchMedia("(hover: none)");

      function closeAll(except) {
        cards.forEach((card) => {
          if (card !== except) card.classList.remove("is-revealed");
        });
      }

      cards.forEach((card) => {
        const mediaWrap = card.querySelector(".card-media-wrap");
        if (!mediaWrap) return;

        mediaWrap.addEventListener("click", (event) => {
          if (!touchQuery.matches) return;
          event.preventDefault();
          const wasRevealed = card.classList.contains("is-revealed");
          closeAll(card);
          if (!wasRevealed) card.classList.add("is-revealed");
        });
      });

      document.addEventListener("click", (event) => {
        if (!touchQuery.matches) return;
        if (event.target.closest("article.card")) return;
        closeAll(null);
      });
    }

    initCardReveal();
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


def _format_ai_score_display(card: Dict[str, Any]) -> str:
    ai_score = card.get("ai_score")
    if ai_score not in (None, ""):
        text = _format_score_value(ai_score)
        tier = str(card.get("ai_tier") or "").strip()
        return f"{text} ({tier})" if tier else text
    error = str(card.get("ai_scoring_error") or "").strip()
    if error:
        return error[:36]
    return "-"


def _render_card_scores(card: Dict[str, Any]) -> str:
    coupang_text = escape(_format_score_value(card.get("coupang_score")))
    naver_text = escape(_format_score_value(card.get("naver_score")))
    ai_raw = _format_ai_score_display(card)
    ai_error = card.get("ai_score") in (None, "") and bool(str(card.get("ai_scoring_error") or "").strip())
    ai_text = escape(ai_raw)
    if ai_error:
        ai_markup = f'<span class="score-pill ai-error">AI {ai_text}</span>'
    else:
        ai_markup = f'<span class="score-pill">AI <strong>{ai_text}</strong></span>'
    return f"""
        <div class="card-scores">
          <span class="score-pill">네이버 <strong>{naver_text}</strong></span>
          <span class="score-pill">쿠팡 <strong>{coupang_text}</strong></span>
          {ai_markup}
        </div>
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
    keyword = escape(str(card.get("keyword") or ""))
    product_url = escape(str(card.get("top_product_url") or "#"))

    return f"""
    <article class="card">
      <div class="card-media-wrap" role="button" tabindex="0" aria-label="{keyword} 상세 보기">
        <div class="media">
          {image_markup}
          <div class="media-overlay"></div>
        </div>
        <h3 class="card-keyword">{keyword}</h3>
      </div>
      <div class="card-details">
        {_render_card_scores(card)}
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
    html = USER_PWA_HTML
    html = html.replace("__THEME_ROWS__", _render_theme_rows(payload))
    return HTMLResponse(content=html)
