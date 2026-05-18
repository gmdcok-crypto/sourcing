from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["admin"])


ADMIN_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Sourcing Admin Console</title>
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
          <p class="brand-title">Sourcing Admin</p>
          <p class="brand-subtitle">Dark operations console</p>
        </div>
      </div>

      <div class="nav-group">
        <p class="nav-label">Overview</p>
        <a class="nav-item active" href="#dashboard">
          <span class="nav-icon">DB</span>
          <span>Dashboard</span>
        </a>
        <a class="nav-item" href="#pipeline">
          <span class="nav-icon">OP</span>
          <span>Sourcing Operations</span>
        </a>
        <a class="nav-item" href="#candidates">
          <span class="nav-icon">PD</span>
          <span>Product Candidates</span>
        </a>
      </div>

      <div class="nav-group">
        <p class="nav-label">Control</p>
        <a class="nav-item" href="#taxonomy">
          <span class="nav-icon">TX</span>
          <span>Theme Taxonomy</span>
        </a>
        <a class="nav-item" href="#ranking">
          <span class="nav-icon">RK</span>
          <span>Ranking Controls</span>
        </a>
        <a class="nav-item" href="#users">
          <span class="nav-icon">US</span>
          <span>Users and Billing</span>
        </a>
      </div>

      <div class="nav-group">
        <p class="nav-label">System</p>
        <a class="nav-item" href="#logs">
          <span class="nav-icon">LG</span>
          <span>Logs and Events</span>
        </a>
        <a class="nav-item" href="/docs">
          <span class="nav-icon">API</span>
          <span>API Docs</span>
        </a>
      </div>

      <div class="sidebar-footer">
        <p class="footer-title">Current operating policy</p>
        <p class="footer-copy">
          Keyword sourcing is scheduled every 3 days. Naver API is active.
          Bright Data is reserved for later Coupang enrichment.
        </p>
        <a class="footer-button" href="/health">View system health</a>
      </div>
    </aside>

    <main class="content">
      <div class="topbar" id="dashboard">
        <div class="topbar-copy">
          <h1>Admin Console</h1>
          <p>Monitor sourcing pipelines, approve candidates, tune ranking, and manage subscriptions from one dark-mode operations workspace.</p>
        </div>
        <div class="topbar-actions">
          <label class="search">
            <span>Search</span>
            <input type="text" placeholder="Search themes, candidates, users" />
          </label>
          <button class="btn">Export report</button>
          <button class="btn primary">Run sourcing batch</button>
        </div>
      </div>

      <section class="hero">
        <article class="card hero-main">
          <span class="eyebrow">Live operations snapshot</span>
          <h2>Professional dark-mode control surface for sourcing, curation, and subscription operations.</h2>
          <p>
            This first version is optimized for operational clarity: sourcing health first, candidate review second,
            ranking controls third. The layout is intentionally dense, tactile, and fast to scan on large screens.
          </p>
          <div class="hero-actions">
            <button class="btn primary">Open candidate review queue</button>
            <button class="btn">Inspect failed jobs</button>
            <button class="btn">View taxonomy map</button>
          </div>
        </article>

        <aside class="card hero-side">
          <div class="section-title">
            <div>
              <h3>Platform health</h3>
              <p>Immediate signals for system status</p>
            </div>
            <a class="section-link" href="/health">Inspect</a>
          </div>
          <div class="health-list">
            <div class="health-item">
              <div>
                <p class="health-name">Naver API connectivity</p>
                <p class="health-copy">Search API active and available</p>
              </div>
              <span class="pill success">Operational</span>
            </div>
            <div class="health-item">
              <div>
                <p class="health-name">Keyword batch schedule</p>
                <p class="health-copy">Next full run in 2 days 11 hours</p>
              </div>
              <span class="pill warning">Queued</span>
            </div>
            <div class="health-item">
              <div>
                <p class="health-name">Coupang enrichment</p>
                <p class="health-copy">Bright Data pipeline not enabled yet</p>
              </div>
              <span class="pill danger">Pending</span>
            </div>
          </div>
        </aside>
      </section>

      <section class="metrics">
        <article class="card metric-card">
          <div class="metric-head">
            <div>
              <div class="metric-label">Keyword pool</div>
              <p class="metric-value">18,420</p>
            </div>
            <div class="metric-icon">KW</div>
          </div>
          <div class="metric-meta">
            <span class="delta up">+12.8% from last cycle</span>
            <span>23 themes active</span>
          </div>
        </article>

        <article class="card metric-card">
          <div class="metric-head">
            <div>
              <div class="metric-label">New candidates</div>
              <p class="metric-value">486</p>
            </div>
            <div class="metric-icon">PD</div>
          </div>
          <div class="metric-meta">
            <span class="delta up">+73 ready for review</span>
            <span>11 hidden</span>
          </div>
        </article>

        <article class="card metric-card">
          <div class="metric-head">
            <div>
              <div class="metric-label">Active subscribers</div>
              <p class="metric-value">1,274</p>
            </div>
            <div class="metric-icon">US</div>
          </div>
          <div class="metric-meta">
            <span class="delta up">+4.2% MTD</span>
            <span>42 trial users</span>
          </div>
        </article>

        <article class="card metric-card">
          <div class="metric-head">
            <div>
              <div class="metric-label">Failed jobs</div>
              <p class="metric-value">03</p>
            </div>
            <div class="metric-icon">ER</div>
          </div>
          <div class="metric-meta">
            <span class="delta down">2 API retry events</span>
            <span>Needs inspection</span>
          </div>
        </article>
      </section>

      <section class="grid-2" id="pipeline">
        <article class="card panel">
          <div class="section-title">
            <div>
              <h2>Sourcing throughput by theme</h2>
              <p>Track where the keyword pipeline is most productive</p>
            </div>
            <a class="section-link" href="#taxonomy">Manage themes</a>
          </div>
          <div class="bars">
            <div class="bar-row">
              <span class="bar-label">Living Goods</span>
              <div class="bar-track"><div class="bar-fill" style="width: 92%"></div></div>
              <span class="bar-value">3,820</span>
            </div>
            <div class="bar-row">
              <span class="bar-label">Desk Styling</span>
              <div class="bar-track"><div class="bar-fill" style="width: 78%"></div></div>
              <span class="bar-value">2,940</span>
            </div>
            <div class="bar-row">
              <span class="bar-label">Kitchen Utility</span>
              <div class="bar-track"><div class="bar-fill" style="width: 85%"></div></div>
              <span class="bar-value">3,210</span>
            </div>
            <div class="bar-row">
              <span class="bar-label">Pet Accessories</span>
              <div class="bar-track"><div class="bar-fill" style="width: 61%"></div></div>
              <span class="bar-value">2,114</span>
            </div>
            <div class="bar-row">
              <span class="bar-label">Car Lifestyle</span>
              <div class="bar-track"><div class="bar-fill" style="width: 56%"></div></div>
              <span class="bar-value">1,902</span>
            </div>
          </div>
        </article>

        <article class="card panel">
          <div class="section-title">
            <div>
              <h2>Attention required</h2>
              <p>Operational alerts that should be reviewed first</p>
            </div>
            <a class="section-link" href="#logs">Open logs</a>
          </div>
          <div class="alert-list">
            <div class="alert-item">
              <strong>Kitchen Utility expansion produced 18 duplicated seeds</strong>
              <p>Duplicate phrases were detected across overlapping CID groups. Review before next automatic promotion.</p>
              <div class="alert-meta">
                <span>Duplicate quality issue</span>
                <span>8 minutes ago</span>
              </div>
            </div>
            <div class="alert-item">
              <strong>2 subscriber renewals entered grace period</strong>
              <p>Payment retries should be observed before account entitlements are reduced or suspended.</p>
              <div class="alert-meta">
                <span>Billing alert</span>
                <span>24 minutes ago</span>
              </div>
            </div>
            <div class="alert-item">
              <strong>Coupang enrichment pipeline remains disabled</strong>
              <p>The placeholder workflow is visible, but no Bright Data production run should be exposed to users yet.</p>
              <div class="alert-meta">
                <span>Roadmap checkpoint</span>
                <span>Today</span>
              </div>
            </div>
          </div>
        </article>
      </section>

      <section class="grid-3" id="candidates">
        <article class="card panel">
          <div class="section-title">
            <div>
              <h2>Candidate review queue</h2>
              <p>High-signal products awaiting operator approval</p>
            </div>
            <a class="section-link" href="#">View all candidates</a>
          </div>
          <table>
            <thead>
              <tr>
                <th>Product</th>
                <th>Theme</th>
                <th>Competition</th>
                <th>Score</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <div class="product">
                    <div class="thumb">01</div>
                    <div>
                      <p class="product-title">Silicone sink organizer rack</p>
                      <p class="product-meta">Keyword cluster: kitchen sink rack</p>
                    </div>
                  </div>
                </td>
                <td>Kitchen Utility</td>
                <td><span class="pill success">Low</span></td>
                <td><span class="score high">91.4</span></td>
                <td><span class="pill warning">Review</span></td>
              </tr>
              <tr>
                <td>
                  <div class="product">
                    <div class="thumb">02</div>
                    <div>
                      <p class="product-title">Minimal monitor riser shelf</p>
                      <p class="product-meta">Keyword cluster: desk monitor stand</p>
                    </div>
                  </div>
                </td>
                <td>Desk Styling</td>
                <td><span class="pill warning">Medium</span></td>
                <td><span class="score high">88.7</span></td>
                <td><span class="pill success">Approved</span></td>
              </tr>
              <tr>
                <td>
                  <div class="product">
                    <div class="thumb">03</div>
                    <div>
                      <p class="product-title">Portable trunk divider bag</p>
                      <p class="product-meta">Keyword cluster: car trunk organizer</p>
                    </div>
                  </div>
                </td>
                <td>Car Accessories</td>
                <td><span class="pill success">Low</span></td>
                <td><span class="score mid">82.1</span></td>
                <td><span class="pill warning">Review</span></td>
              </tr>
              <tr>
                <td>
                  <div class="product">
                    <div class="thumb">04</div>
                    <div>
                      <p class="product-title">Absorbent microfiber bath mat</p>
                      <p class="product-meta">Keyword cluster: bathroom quick dry mat</p>
                    </div>
                  </div>
                </td>
                <td>Bathroom Goods</td>
                <td><span class="pill danger">High</span></td>
                <td><span class="score mid">74.5</span></td>
                <td><span class="pill danger">Hold</span></td>
              </tr>
            </tbody>
          </table>
        </article>

        <aside class="card panel">
          <div class="section-title">
            <div>
              <h2>Review workload</h2>
              <p>Queue pressure across the moderation flow</p>
            </div>
          </div>
          <div class="mini-stat-list">
            <div class="mini-stat">
              <div class="mini-stat-top">
                <div>
                  <p class="mini-stat-title">Pending review</p>
                  <p class="mini-stat-copy">Needs operator decision</p>
                </div>
                <span class="mini-stat-value">73</span>
              </div>
              <div class="progress"><span style="width: 73%"></span></div>
            </div>
            <div class="mini-stat">
              <div class="mini-stat-top">
                <div>
                  <p class="mini-stat-title">Approved for users</p>
                  <p class="mini-stat-copy">Currently visible in the PWA feed</p>
                </div>
                <span class="mini-stat-value">214</span>
              </div>
              <div class="progress"><span style="width: 84%"></span></div>
            </div>
            <div class="mini-stat">
              <div class="mini-stat-top">
                <div>
                  <p class="mini-stat-title">Excluded or hidden</p>
                  <p class="mini-stat-copy">Manual or rule-based suppression</p>
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
              <h2>Theme taxonomy</h2>
              <p>Maintain CID groups and sourcing scope</p>
            </div>
          </div>
          <table>
            <thead>
              <tr>
                <th>Theme</th>
                <th>Active CID</th>
                <th>Priority</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Living Goods</td>
                <td>10</td>
                <td><span class="pill success">Core</span></td>
              </tr>
              <tr>
                <td>Desk Styling</td>
                <td>12</td>
                <td><span class="pill success">Core</span></td>
              </tr>
              <tr>
                <td>Kitchen Utility</td>
                <td>8</td>
                <td><span class="pill warning">Expand</span></td>
              </tr>
              <tr>
                <td>Travel Small Goods</td>
                <td>6</td>
                <td><span class="pill warning">Watch</span></td>
              </tr>
            </tbody>
          </table>
        </article>

        <article class="card panel" id="ranking">
          <div class="section-title">
            <div>
              <h2>Ranking controls</h2>
              <p>Suggested weighting for the recommendation engine</p>
            </div>
          </div>
          <div class="bars">
            <div class="bar-row">
              <span class="bar-label">Demand signal</span>
              <div class="bar-track"><div class="bar-fill" style="width: 88%"></div></div>
              <span class="bar-value">0.88</span>
            </div>
            <div class="bar-row">
              <span class="bar-label">Low competition</span>
              <div class="bar-track"><div class="bar-fill" style="width: 74%"></div></div>
              <span class="bar-value">0.74</span>
            </div>
            <div class="bar-row">
              <span class="bar-label">Novelty lift</span>
              <div class="bar-track"><div class="bar-fill" style="width: 62%"></div></div>
              <span class="bar-value">0.62</span>
            </div>
            <div class="bar-row">
              <span class="bar-label">Manual curation</span>
              <div class="bar-track"><div class="bar-fill" style="width: 55%"></div></div>
              <span class="bar-value">0.55</span>
            </div>
          </div>
        </article>

        <article class="card panel" id="users">
          <div class="section-title">
            <div>
              <h2>Users and billing</h2>
              <p>Subscription and device-cap visibility</p>
            </div>
          </div>
          <div class="mini-stat-list">
            <div class="mini-stat">
              <div class="mini-stat-top">
                <div>
                  <p class="mini-stat-title">Active subscriptions</p>
                  <p class="mini-stat-copy">Basic and Pro users combined</p>
                </div>
                <span class="mini-stat-value">1,274</span>
              </div>
            </div>
            <div class="mini-stat">
              <div class="mini-stat-top">
                <div>
                  <p class="mini-stat-title">Grace period accounts</p>
                  <p class="mini-stat-copy">Payment recovery workflow</p>
                </div>
                <span class="mini-stat-value">12</span>
              </div>
            </div>
            <div class="mini-stat">
              <div class="mini-stat-top">
                <div>
                  <p class="mini-stat-title">Maxed device slots</p>
                  <p class="mini-stat-copy">Users at 2-device limit</p>
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
            <h2>Logs and system events</h2>
            <p>Operational trail for sourcing, auth, and billing</p>
          </div>
          <a class="section-link" href="/docs">Inspect backend endpoints</a>
        </div>
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Event</th>
              <th>Domain</th>
              <th>Severity</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>14:28</td>
              <td>Naver keyword batch completed for Desk Styling</td>
              <td>Pipeline</td>
              <td><span class="pill success">Info</span></td>
              <td>View batch</td>
            </tr>
            <tr>
              <td>14:12</td>
              <td>Payment renewal failed for 2 subscribers</td>
              <td>Billing</td>
              <td><span class="pill warning">Warn</span></td>
              <td>Open recovery</td>
            </tr>
            <tr>
              <td>13:54</td>
              <td>Keyword duplication threshold exceeded in Kitchen Utility</td>
              <td>Quality</td>
              <td><span class="pill danger">Alert</span></td>
              <td>Review rule</td>
            </tr>
            <tr>
              <td>13:31</td>
              <td>New device approval completed for admin operator</td>
              <td>Auth</td>
              <td><span class="pill success">Info</span></td>
              <td>Inspect audit</td>
            </tr>
          </tbody>
        </table>
        <div class="footer-note">Static concept screen rendered from FastAPI for rapid design validation.</div>
      </section>
    </main>
  </div>
</body>
</html>
"""


@router.get("/admin", response_class=HTMLResponse)
async def admin_console() -> HTMLResponse:
    return HTMLResponse(content=ADMIN_HTML)
