from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["admin"])


ADMIN_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>소싱 관리자 콘솔</title>
  <style>
    :root {
      --bg: #0b1020;
      --bg-soft: #11182d;
      --bg-card: rgba(19, 27, 46, 0.92);
      --bg-card-strong: #121a31;
      --line: rgba(255, 255, 255, 0.08);
      --line-strong: rgba(255, 255, 255, 0.14);
      --text: #eef2ff;
      --muted: #8f9bb7;
      --primary: #7c9cff;
      --primary-soft: rgba(124, 156, 255, 0.14);
      --success: #2ecc71;
      --warning: #f5b84c;
      --danger: #ff6b6b;
      --cyan: #48d3ff;
      --purple: #b388ff;
      --radius-xl: 24px;
      --radius-lg: 18px;
      --radius-md: 14px;
      --shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
    }

    * {
      box-sizing: border-box;
    }

    html, body {
      margin: 0;
      padding: 0;
      background:
        radial-gradient(circle at top left, rgba(124, 156, 255, 0.16), transparent 26%),
        radial-gradient(circle at top right, rgba(72, 211, 255, 0.12), transparent 20%),
        linear-gradient(180deg, #09101d 0%, #0b1020 100%);
      color: var(--text);
      font-family: Inter, "Segoe UI", Arial, sans-serif;
      min-height: 100%;
    }

    a {
      color: inherit;
      text-decoration: none;
    }

    .layout {
      display: grid;
      grid-template-columns: 280px 1fr;
      min-height: 100vh;
    }

    .sidebar {
      position: sticky;
      top: 0;
      height: 100vh;
      padding: 28px 20px;
      border-right: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(10, 14, 27, 0.96), rgba(8, 12, 24, 0.92));
      backdrop-filter: blur(18px);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
      margin-bottom: 28px;
      padding: 6px 6px 18px;
      border-bottom: 1px solid var(--line);
    }

    .brand-badge {
      width: 44px;
      height: 44px;
      border-radius: 14px;
      display: grid;
      place-items: center;
      background: linear-gradient(135deg, var(--primary), #536dfe);
      box-shadow: 0 12px 30px rgba(83, 109, 254, 0.34);
      font-weight: 800;
    }

    .brand-title {
      font-size: 18px;
      font-weight: 700;
      margin: 0;
    }

    .brand-subtitle {
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 12px;
    }

    .nav-group {
      margin-top: 26px;
    }

    .nav-label {
      margin: 0 0 10px 12px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }

    .nav-item {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 13px 14px;
      border: 1px solid transparent;
      border-radius: 14px;
      color: #dce4ff;
      margin-bottom: 8px;
      transition: all 0.18s ease;
    }

    .nav-item:hover,
    .nav-item.active {
      background: var(--primary-soft);
      border-color: rgba(124, 156, 255, 0.24);
      color: #ffffff;
    }

    .nav-icon {
      width: 28px;
      height: 28px;
      border-radius: 10px;
      display: grid;
      place-items: center;
      background: rgba(255, 255, 255, 0.05);
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }

    .nav-item.active .nav-icon {
      background: rgba(124, 156, 255, 0.22);
      color: #ffffff;
    }

    .sidebar-footer {
      margin-top: 26px;
      padding: 18px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(19, 27, 46, 0.9), rgba(15, 22, 39, 0.88));
    }

    .footer-title {
      margin: 0 0 6px;
      font-size: 14px;
      font-weight: 700;
    }

    .footer-copy {
      margin: 0 0 14px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.6;
    }

    .footer-button {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 12px;
      padding: 10px 12px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--line);
      font-size: 12px;
      color: #f6f8ff;
    }

    .content {
      padding: 26px;
    }

    .topbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 20px;
      margin-bottom: 24px;
    }

    .topbar-copy h1 {
      margin: 0 0 8px;
      font-size: 30px;
      font-weight: 800;
      letter-spacing: -0.03em;
    }

    .topbar-copy p {
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }

    .topbar-actions {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }

    .search {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 280px;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(14, 20, 35, 0.82);
    }

    .search input {
      width: 100%;
      border: 0;
      outline: none;
      background: transparent;
      color: var(--text);
      font-size: 14px;
    }

    .btn {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px 16px;
      background: rgba(17, 24, 45, 0.88);
      color: var(--text);
      font-weight: 600;
      font-size: 13px;
      cursor: pointer;
      transition: all 0.18s ease;
    }

    .btn:hover {
      border-color: var(--line-strong);
      transform: translateY(-1px);
    }

    .btn.primary {
      background: linear-gradient(135deg, var(--primary), #5877ff);
      border-color: rgba(124, 156, 255, 0.42);
      color: white;
      box-shadow: 0 16px 40px rgba(88, 119, 255, 0.3);
    }

    .hero {
      display: grid;
      grid-template-columns: 1.45fr 0.85fr;
      gap: 18px;
      margin-bottom: 18px;
    }

    .card {
      background: linear-gradient(180deg, rgba(18, 26, 49, 0.95), rgba(14, 21, 39, 0.94));
      border: 1px solid var(--line);
      border-radius: var(--radius-xl);
      box-shadow: var(--shadow);
    }

    .hero-main {
      padding: 28px;
      position: relative;
      overflow: hidden;
    }

    .hero-main::after {
      content: "";
      position: absolute;
      inset: auto -60px -60px auto;
      width: 220px;
      height: 220px;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(124, 156, 255, 0.3), transparent 64%);
    }

    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(124, 156, 255, 0.12);
      color: #dfe7ff;
      font-size: 12px;
      font-weight: 700;
      margin-bottom: 16px;
      border: 1px solid rgba(124, 156, 255, 0.18);
    }

    .hero-main h2 {
      margin: 0 0 12px;
      font-size: 34px;
      line-height: 1.15;
      letter-spacing: -0.04em;
      max-width: 760px;
    }

    .hero-main p {
      margin: 0 0 22px;
      max-width: 760px;
      font-size: 15px;
      line-height: 1.75;
      color: var(--muted);
    }

    .hero-actions {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }

    .hero-side {
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }

    .section-title {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin: 0 0 16px;
    }

    .section-title h3,
    .section-title h2 {
      margin: 0;
      font-size: 17px;
      letter-spacing: -0.02em;
    }

    .section-title p {
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 12px;
    }

    .section-link {
      color: #d8e3ff;
      font-size: 12px;
      font-weight: 700;
    }

    .health-list {
      display: grid;
      gap: 12px;
    }

    .health-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 14px 16px;
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--line);
    }

    .health-name {
      margin: 0 0 5px;
      font-size: 13px;
      font-weight: 700;
    }

    .health-copy {
      margin: 0;
      color: var(--muted);
      font-size: 12px;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 7px 10px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.02em;
      white-space: nowrap;
    }

    .pill.success {
      color: #cbffde;
      background: rgba(46, 204, 113, 0.12);
      border: 1px solid rgba(46, 204, 113, 0.22);
    }

    .pill.warning {
      color: #ffe8b0;
      background: rgba(245, 184, 76, 0.12);
      border: 1px solid rgba(245, 184, 76, 0.22);
    }

    .pill.danger {
      color: #ffd0d0;
      background: rgba(255, 107, 107, 0.12);
      border: 1px solid rgba(255, 107, 107, 0.22);
    }

    .metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
      margin-bottom: 18px;
    }

    .metric-card {
      padding: 20px;
    }

    .metric-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }

    .metric-label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }

    .metric-icon {
      width: 42px;
      height: 42px;
      border-radius: 14px;
      display: grid;
      place-items: center;
      background: rgba(255, 255, 255, 0.05);
      color: #dfe7ff;
      font-size: 13px;
      font-weight: 800;
    }

    .metric-value {
      margin: 0;
      font-size: 32px;
      font-weight: 800;
      letter-spacing: -0.04em;
    }

    .metric-meta {
      margin-top: 10px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      color: var(--muted);
      font-size: 12px;
    }

    .delta.up {
      color: #8ef0b5;
    }

    .delta.down {
      color: #ffb2b2;
    }

    .grid-2 {
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 18px;
      margin-bottom: 18px;
    }

    .panel {
      padding: 22px;
    }

    .bars {
      display: grid;
      gap: 14px;
      margin-top: 18px;
    }

    .bar-row {
      display: grid;
      grid-template-columns: 150px 1fr 60px;
      gap: 14px;
      align-items: center;
    }

    .bar-label {
      color: #dfe7ff;
      font-size: 13px;
      font-weight: 600;
    }

    .bar-track {
      width: 100%;
      height: 11px;
      background: rgba(255, 255, 255, 0.06);
      border-radius: 999px;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.04);
    }

    .bar-fill {
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--primary), var(--cyan));
    }

    .bar-value {
      color: var(--muted);
      font-size: 12px;
      text-align: right;
    }

    .alert-list {
      display: grid;
      gap: 12px;
      margin-top: 18px;
    }

    .alert-item {
      padding: 16px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.03);
    }

    .alert-item strong {
      display: block;
      margin-bottom: 6px;
      font-size: 13px;
    }

    .alert-item p {
      margin: 0 0 10px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.65;
    }

    .alert-meta {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      color: var(--muted);
      font-size: 11px;
    }

    .grid-3 {
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 18px;
      margin-bottom: 18px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
    }

    th {
      color: var(--muted);
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      text-align: left;
      padding: 0 0 14px;
      border-bottom: 1px solid var(--line);
    }

    td {
      padding: 16px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      vertical-align: middle;
      font-size: 13px;
    }

    tr:last-child td {
      border-bottom: 0;
    }

    .product {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .thumb {
      width: 48px;
      height: 48px;
      border-radius: 14px;
      display: grid;
      place-items: center;
      background: linear-gradient(135deg, rgba(124, 156, 255, 0.22), rgba(72, 211, 255, 0.14));
      border: 1px solid rgba(124, 156, 255, 0.18);
      color: #eef4ff;
      font-weight: 800;
      flex: none;
    }

    .product-title {
      margin: 0 0 6px;
      font-size: 13px;
      font-weight: 700;
      line-height: 1.4;
    }

    .product-meta {
      margin: 0;
      color: var(--muted);
      font-size: 12px;
    }

    .score {
      font-weight: 800;
      letter-spacing: -0.03em;
    }

    .score.high {
      color: #a6c0ff;
    }

    .score.mid {
      color: #ffe0a3;
    }

    .mini-stat-list {
      display: grid;
      gap: 12px;
      margin-top: 18px;
    }

    .mini-stat {
      padding: 16px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.03);
    }

    .mini-stat-top {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 12px;
    }

    .mini-stat-title {
      margin: 0;
      font-size: 13px;
      font-weight: 700;
    }

    .mini-stat-copy {
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 12px;
    }

    .mini-stat-value {
      font-size: 24px;
      font-weight: 800;
      letter-spacing: -0.04em;
    }

    .progress {
      width: 100%;
      height: 10px;
      background: rgba(255, 255, 255, 0.06);
      border-radius: 999px;
      overflow: hidden;
    }

    .progress > span {
      display: block;
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--purple), var(--primary));
    }

    .split {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
    }

    .footer-note {
      margin-top: 18px;
      color: var(--muted);
      font-size: 12px;
      text-align: right;
    }

    @media (max-width: 1360px) {
      .metrics {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .hero,
      .grid-2,
      .grid-3 {
        grid-template-columns: 1fr;
      }

      .split {
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: 980px) {
      .layout {
        grid-template-columns: 1fr;
      }

      .sidebar {
        position: relative;
        height: auto;
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }
    }

    @media (max-width: 720px) {
      .content {
        padding: 18px;
      }

      .topbar {
        flex-direction: column;
        align-items: stretch;
      }

      .search {
        min-width: 0;
      }

      .metrics {
        grid-template-columns: 1fr;
      }

      .bar-row {
        grid-template-columns: 1fr;
      }

      .hero-main h2 {
        font-size: 28px;
      }
    }
  </style>
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-badge">S</div>
        <div>
          <p class="brand-title">소싱 관리자</p>
          <p class="brand-subtitle">다크모드 운영 콘솔</p>
        </div>
      </div>

      <div class="nav-group">
        <p class="nav-label">개요</p>
        <a class="nav-item active" href="#dashboard">
          <span class="nav-icon">DB</span>
          <span>대시보드</span>
        </a>
        <a class="nav-item" href="#pipeline">
          <span class="nav-icon">OP</span>
          <span>소싱 운영</span>
        </a>
        <a class="nav-item" href="#candidates">
          <span class="nav-icon">PD</span>
          <span>상품 후보 관리</span>
        </a>
      </div>

      <div class="nav-group">
        <p class="nav-label">운영 제어</p>
        <a class="nav-item" href="#taxonomy">
          <span class="nav-icon">TX</span>
          <span>테마 관리</span>
        </a>
        <a class="nav-item" href="#ranking">
          <span class="nav-icon">RK</span>
          <span>랭킹 관리</span>
        </a>
        <a class="nav-item" href="#users">
          <span class="nav-icon">US</span>
          <span>사용자 및 과금</span>
        </a>
      </div>

      <div class="nav-group">
        <p class="nav-label">시스템</p>
        <a class="nav-item" href="#logs">
          <span class="nav-icon">LG</span>
          <span>로그 및 이벤트</span>
        </a>
        <a class="nav-item" href="/docs">
          <span class="nav-icon">API</span>
          <span>API 문서</span>
        </a>
      </div>

      <div class="sidebar-footer">
        <p class="footer-title">현재 운영 정책</p>
        <p class="footer-copy">
          키워드 소싱은 3일 주기로 실행합니다. 네이버 API는 정상 연결 상태이며,
          Bright Data는 이후 쿠팡 보강 수집 단계에서만 사용합니다.
        </p>
        <a class="footer-button" href="/health">시스템 상태 보기</a>
      </div>
    </aside>

    <main class="content">
      <div class="topbar" id="dashboard">
        <div class="topbar-copy">
          <h1>관리자 콘솔</h1>
          <p>소싱 파이프라인 상태 확인, 후보 검수, 랭킹 조정, 구독 관리까지 하나의 다크모드 운영 화면에서 처리합니다.</p>
        </div>
        <div class="topbar-actions">
          <label class="search">
            <span>검색</span>
            <input type="text" placeholder="테마, 후보 상품, 사용자 검색" />
          </label>
          <button class="btn">리포트 내보내기</button>
          <button class="btn primary">소싱 배치 실행</button>
        </div>
      </div>

      <section class="hero">
        <article class="card hero-main">
          <span class="eyebrow">실시간 운영 현황</span>
          <h2>소싱, 검수, 노출, 구독 운영을 한눈에 관리하는 다크모드 관리자 화면입니다.</h2>
          <p>
            1차 버전은 운영 우선 구조에 맞춰 설계했습니다. 먼저 수집 상태를 확인하고,
            다음으로 후보 상품을 검수하며, 마지막으로 노출 및 랭킹 기준을 조정할 수 있도록 밀도 있게 배치했습니다.
          </p>
          <div class="hero-actions">
            <button class="btn primary">후보 검수 대기열 보기</button>
            <button class="btn">실패 작업 확인</button>
            <button class="btn">테마 매핑 보기</button>
          </div>
        </article>

        <aside class="card hero-side">
          <div class="section-title">
            <div>
              <h3>플랫폼 상태</h3>
              <p>지금 바로 확인해야 하는 운영 신호</p>
            </div>
            <a class="section-link" href="/health">확인</a>
          </div>
          <div class="health-list">
            <div class="health-item">
              <div>
                <p class="health-name">네이버 API 연결 상태</p>
                <p class="health-copy">검색 API가 정상적으로 활성화되어 있습니다.</p>
              </div>
              <span class="pill success">정상</span>
            </div>
            <div class="health-item">
              <div>
                <p class="health-name">키워드 배치 스케줄</p>
                <p class="health-copy">다음 전체 실행까지 2일 11시간 남았습니다.</p>
              </div>
              <span class="pill warning">대기</span>
            </div>
            <div class="health-item">
              <div>
                <p class="health-name">쿠팡 보강 수집</p>
                <p class="health-copy">Bright Data 파이프라인은 아직 활성화하지 않았습니다.</p>
              </div>
              <span class="pill danger">보류</span>
            </div>
          </div>
        </aside>
      </section>

      <section class="metrics">
        <article class="card metric-card">
          <div class="metric-head">
            <div>
              <div class="metric-label">키워드 풀</div>
              <p class="metric-value">18,420</p>
            </div>
            <div class="metric-icon">KW</div>
          </div>
          <div class="metric-meta">
            <span class="delta up">지난 회차 대비 +12.8%</span>
            <span>활성 테마 23개</span>
          </div>
        </article>

        <article class="card metric-card">
          <div class="metric-head">
            <div>
              <div class="metric-label">신규 후보</div>
              <p class="metric-value">486</p>
            </div>
            <div class="metric-icon">PD</div>
          </div>
          <div class="metric-meta">
            <span class="delta up">검수 대기 73건</span>
            <span>숨김 11건</span>
          </div>
        </article>

        <article class="card metric-card">
          <div class="metric-head">
            <div>
              <div class="metric-label">활성 구독자</div>
              <p class="metric-value">1,274</p>
            </div>
            <div class="metric-icon">US</div>
          </div>
          <div class="metric-meta">
            <span class="delta up">이번 달 +4.2%</span>
            <span>체험 사용자 42명</span>
          </div>
        </article>

        <article class="card metric-card">
          <div class="metric-head">
            <div>
              <div class="metric-label">실패 작업</div>
              <p class="metric-value">03</p>
            </div>
            <div class="metric-icon">ER</div>
          </div>
          <div class="metric-meta">
            <span class="delta down">API 재시도 2건</span>
            <span>점검 필요</span>
          </div>
        </article>
      </section>

      <section class="grid-2" id="pipeline">
        <article class="card panel">
          <div class="section-title">
            <div>
              <h2>테마별 소싱 처리량</h2>
              <p>어느 테마에서 키워드 수집이 많이 발생하는지 확인합니다.</p>
            </div>
            <a class="section-link" href="#taxonomy">테마 관리</a>
          </div>
          <div class="bars">
            <div class="bar-row">
              <span class="bar-label">생활용품</span>
              <div class="bar-track"><div class="bar-fill" style="width: 92%"></div></div>
              <span class="bar-value">3,820</span>
            </div>
            <div class="bar-row">
              <span class="bar-label">책상 꾸미기</span>
              <div class="bar-track"><div class="bar-fill" style="width: 78%"></div></div>
              <span class="bar-value">2,940</span>
            </div>
            <div class="bar-row">
              <span class="bar-label">주방 편의도구</span>
              <div class="bar-track"><div class="bar-fill" style="width: 85%"></div></div>
              <span class="bar-value">3,210</span>
            </div>
            <div class="bar-row">
              <span class="bar-label">반려동물 소품</span>
              <div class="bar-track"><div class="bar-fill" style="width: 61%"></div></div>
              <span class="bar-value">2,114</span>
            </div>
            <div class="bar-row">
              <span class="bar-label">차량 감성용품</span>
              <div class="bar-track"><div class="bar-fill" style="width: 56%"></div></div>
              <span class="bar-value">1,902</span>
            </div>
          </div>
        </article>

        <article class="card panel">
          <div class="section-title">
            <div>
              <h2>우선 확인 필요</h2>
              <p>운영자가 먼저 봐야 할 주요 알림입니다.</p>
            </div>
            <a class="section-link" href="#logs">로그 보기</a>
          </div>
          <div class="alert-list">
            <div class="alert-item">
              <strong>주방 편의도구 확장에서 중복 seed 18건이 발생했습니다.</strong>
              <p>겹치는 CID 그룹 사이에서 중복 문구가 감지되었습니다. 다음 자동 반영 전에 검토가 필요합니다.</p>
              <div class="alert-meta">
                <span>중복 품질 이슈</span>
                <span>8분 전</span>
              </div>
            </div>
            <div class="alert-item">
              <strong>구독 갱신 실패 2건이 유예기간에 진입했습니다.</strong>
              <p>권한 축소나 중지 전에 재결제 시도가 정상적으로 이뤄지는지 확인해야 합니다.</p>
              <div class="alert-meta">
                <span>과금 알림</span>
                <span>24분 전</span>
              </div>
            </div>
            <div class="alert-item">
              <strong>쿠팡 보강 수집 파이프라인은 아직 비활성 상태입니다.</strong>
              <p>현재는 워크플로 자리만 마련된 상태이며, Bright Data 실수집은 아직 사용자에게 노출하면 안 됩니다.</p>
              <div class="alert-meta">
                <span>로드맵 체크포인트</span>
                <span>오늘</span>
              </div>
            </div>
          </div>
        </article>
      </section>

      <section class="grid-3" id="candidates">
        <article class="card panel">
          <div class="section-title">
            <div>
              <h2>후보 검수 대기열</h2>
              <p>운영 승인 대기 중인 핵심 후보 상품입니다.</p>
            </div>
            <a class="section-link" href="#">전체 후보 보기</a>
          </div>
          <table>
            <thead>
              <tr>
                <th>상품</th>
                <th>테마</th>
                <th>경쟁강도</th>
                <th>점수</th>
                <th>상태</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <div class="product">
                    <div class="thumb">01</div>
                    <div>
                      <p class="product-title">실리콘 싱크대 정리 랙</p>
                      <p class="product-meta">키워드 군집: 싱크대 정리대</p>
                    </div>
                  </div>
                </td>
                <td>주방 편의도구</td>
                <td><span class="pill success">낮음</span></td>
                <td><span class="score high">91.4</span></td>
                <td><span class="pill warning">검수중</span></td>
              </tr>
              <tr>
                <td>
                  <div class="product">
                    <div class="thumb">02</div>
                    <div>
                      <p class="product-title">미니멀 모니터 받침대</p>
                      <p class="product-meta">키워드 군집: 모니터 선반</p>
                    </div>
                  </div>
                </td>
                <td>책상 꾸미기</td>
                <td><span class="pill warning">보통</span></td>
                <td><span class="score high">88.7</span></td>
                <td><span class="pill success">승인</span></td>
              </tr>
              <tr>
                <td>
                  <div class="product">
                    <div class="thumb">03</div>
                    <div>
                      <p class="product-title">휴대용 트렁크 분리 수납백</p>
                      <p class="product-meta">키워드 군집: 차량 트렁크 정리함</p>
                    </div>
                  </div>
                </td>
                <td>차량용 소품</td>
                <td><span class="pill success">낮음</span></td>
                <td><span class="score mid">82.1</span></td>
                <td><span class="pill warning">검수중</span></td>
              </tr>
              <tr>
                <td>
                  <div class="product">
                    <div class="thumb">04</div>
                    <div>
                      <p class="product-title">흡수형 극세사 욕실 매트</p>
                      <p class="product-meta">키워드 군집: 욕실 속건 매트</p>
                    </div>
                  </div>
                </td>
                <td>욕실용품</td>
                <td><span class="pill danger">높음</span></td>
                <td><span class="score mid">74.5</span></td>
                <td><span class="pill danger">보류</span></td>
              </tr>
            </tbody>
          </table>
        </article>

        <aside class="card panel">
          <div class="section-title">
            <div>
              <h2>검수 작업량</h2>
              <p>검수 단계별 대기 현황입니다.</p>
            </div>
          </div>
          <div class="mini-stat-list">
            <div class="mini-stat">
              <div class="mini-stat-top">
                <div>
                  <p class="mini-stat-title">검수 대기</p>
                  <p class="mini-stat-copy">운영자 판단이 필요한 상태</p>
                </div>
                <span class="mini-stat-value">73</span>
              </div>
              <div class="progress"><span style="width: 73%"></span></div>
            </div>
            <div class="mini-stat">
              <div class="mini-stat-top">
                <div>
                  <p class="mini-stat-title">사용자 노출 승인</p>
                  <p class="mini-stat-copy">현재 사용자 화면에 노출 중</p>
                </div>
                <span class="mini-stat-value">214</span>
              </div>
              <div class="progress"><span style="width: 84%"></span></div>
            </div>
            <div class="mini-stat">
              <div class="mini-stat-top">
                <div>
                  <p class="mini-stat-title">제외 또는 숨김</p>
                  <p class="mini-stat-copy">수동 처리 또는 규칙 기반 제외</p>
                </div>
                <span class="mini-stat-value">39</span>
              </div>
              <div class="progress"><span style="width: 32%"></span></div>
            </div>
          </div>
        </aside>
      </section>

      <section class="split" id="taxonomy">
        <article class="card panel">
          <div class="section-title">
            <div>
              <h2>테마 관리</h2>
              <p>CID 그룹과 수집 범위를 관리합니다.</p>
            </div>
          </div>
          <table>
            <thead>
              <tr>
                <th>테마</th>
                <th>활성 CID 수</th>
                <th>우선순위</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>생활용품</td>
                <td>10</td>
                <td><span class="pill success">핵심</span></td>
              </tr>
              <tr>
                <td>책상 꾸미기</td>
                <td>12</td>
                <td><span class="pill success">핵심</span></td>
              </tr>
              <tr>
                <td>주방 편의도구</td>
                <td>8</td>
                <td><span class="pill warning">확장</span></td>
              </tr>
              <tr>
                <td>여행용 소형용품</td>
                <td>6</td>
                <td><span class="pill warning">관찰</span></td>
              </tr>
            </tbody>
          </table>
        </article>

        <article class="card panel" id="ranking">
          <div class="section-title">
            <div>
              <h2>랭킹 관리</h2>
              <p>추천 엔진 가중치 예시입니다.</p>
            </div>
          </div>
          <div class="bars">
            <div class="bar-row">
              <span class="bar-label">수요 신호</span>
              <div class="bar-track"><div class="bar-fill" style="width: 88%"></div></div>
              <span class="bar-value">0.88</span>
            </div>
            <div class="bar-row">
              <span class="bar-label">저경쟁 보정</span>
              <div class="bar-track"><div class="bar-fill" style="width: 74%"></div></div>
              <span class="bar-value">0.74</span>
            </div>
            <div class="bar-row">
              <span class="bar-label">신규성 가중치</span>
              <div class="bar-track"><div class="bar-fill" style="width: 62%"></div></div>
              <span class="bar-value">0.62</span>
            </div>
            <div class="bar-row">
              <span class="bar-label">수동 큐레이션</span>
              <div class="bar-track"><div class="bar-fill" style="width: 55%"></div></div>
              <span class="bar-value">0.55</span>
            </div>
          </div>
        </article>

        <article class="card panel" id="users">
          <div class="section-title">
            <div>
              <h2>사용자 및 과금</h2>
              <p>구독 상태와 기기 제한 현황을 확인합니다.</p>
            </div>
          </div>
          <div class="mini-stat-list">
            <div class="mini-stat">
              <div class="mini-stat-top">
                <div>
                  <p class="mini-stat-title">활성 구독</p>
                  <p class="mini-stat-copy">Basic, Pro 전체 사용자 합계</p>
                </div>
                <span class="mini-stat-value">1,274</span>
              </div>
            </div>
            <div class="mini-stat">
              <div class="mini-stat-top">
                <div>
                  <p class="mini-stat-title">유예기간 계정</p>
                  <p class="mini-stat-copy">결제 복구 대상 계정</p>
                </div>
                <span class="mini-stat-value">12</span>
              </div>
            </div>
            <div class="mini-stat">
              <div class="mini-stat-top">
                <div>
                  <p class="mini-stat-title">기기 슬롯 가득 참</p>
                  <p class="mini-stat-copy">2기기 제한에 도달한 사용자</p>
                </div>
                <span class="mini-stat-value">418</span>
              </div>
            </div>
          </div>
        </article>
      </section>

      <section class="card panel" id="logs" style="margin-top: 18px;">
        <div class="section-title">
          <div>
            <h2>로그 및 시스템 이벤트</h2>
            <p>소싱, 인증, 과금 흐름에 대한 운영 이력입니다.</p>
          </div>
          <a class="section-link" href="/docs">백엔드 엔드포인트 보기</a>
        </div>
        <table>
          <thead>
            <tr>
              <th>시간</th>
              <th>이벤트</th>
              <th>영역</th>
              <th>심각도</th>
              <th>액션</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>14:28</td>
              <td>책상 꾸미기 테마의 네이버 키워드 배치가 완료되었습니다.</td>
              <td>파이프라인</td>
              <td><span class="pill success">정보</span></td>
              <td>배치 보기</td>
            </tr>
            <tr>
              <td>14:12</td>
              <td>구독자 2명의 결제 갱신에 실패했습니다.</td>
              <td>과금</td>
              <td><span class="pill warning">주의</span></td>
              <td>복구 열기</td>
            </tr>
            <tr>
              <td>13:54</td>
              <td>주방 편의도구 테마에서 키워드 중복 임계치를 초과했습니다.</td>
              <td>품질</td>
              <td><span class="pill danger">경고</span></td>
              <td>규칙 검토</td>
            </tr>
            <tr>
              <td>13:31</td>
              <td>관리자 계정의 신규 기기 승인이 완료되었습니다.</td>
              <td>인증</td>
              <td><span class="pill success">정보</span></td>
              <td>감사 로그 보기</td>
            </tr>
          </tbody>
        </table>
        <div class="footer-note">빠른 디자인 검증을 위해 FastAPI 안에서 렌더링하는 정적 관리자 화면 시안입니다.</div>
      </section>
    </main>
  </div>
</body>
</html>
"""


@router.get("/admin", response_class=HTMLResponse)
async def admin_console() -> HTMLResponse:
    return HTMLResponse(content=ADMIN_HTML)
