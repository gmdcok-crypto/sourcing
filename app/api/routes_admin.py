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
      --line: rgba(255, 255, 255, 0.08);
      --text: #eef2ff;
      --muted: #8f9bb7;
      --primary: #7c9cff;
      --primary-soft: rgba(124, 156, 255, 0.14);
      --success: #2ecc71;
      --warning: #f5b84c;
      --danger: #ff6b6b;
      --radius-xl: 24px;
      --shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
    }

    * { box-sizing: border-box; }
    html, body {
      margin: 0;
      padding: 0;
      background: linear-gradient(180deg, #09101d 0%, #0b1020 100%);
      color: var(--text);
      font-family: Inter, "Segoe UI", Arial, sans-serif;
      min-height: 100%;
    }
    a { color: inherit; text-decoration: none; }

    .layout {
      display: grid;
      grid-template-columns: 280px 1fr;
      min-height: 100vh;
    }

    .sidebar {
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

    .brand-title { font-size: 18px; font-weight: 700; margin: 0; }
    .brand-subtitle { margin: 4px 0 0; color: var(--muted); font-size: 12px; }

    .nav-label {
      margin: 0 0 10px 12px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }

    .nav-button {
      width: 100%;
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 13px 14px;
      border: 1px solid transparent;
      border-radius: 14px;
      background: transparent;
      color: #dce4ff;
      margin-bottom: 8px;
      transition: all 0.18s ease;
      cursor: pointer;
      text-align: left;
    }

    .nav-button:hover,
    .nav-button.active {
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

    .nav-button.active .nav-icon {
      background: rgba(124, 156, 255, 0.22);
      color: #ffffff;
    }

    .sidebar-footer {
      margin-top: 22px;
      padding: 18px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(19, 27, 46, 0.9), rgba(15, 22, 39, 0.88));
    }

    .footer-title { margin: 0 0 6px; font-size: 14px; font-weight: 700; }
    .footer-copy { margin: 0 0 14px; color: var(--muted); font-size: 12px; line-height: 1.6; }

    .content { padding: 26px; }

    .card {
      background: linear-gradient(180deg, rgba(18, 26, 49, 0.95), rgba(14, 21, 39, 0.94));
      border: 1px solid var(--line);
      border-radius: var(--radius-xl);
      box-shadow: var(--shadow);
    }

    .panel { padding: 22px; }
    .section-title {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin: 0 0 16px;
    }
    .section-title h2 { margin: 0; font-size: 17px; letter-spacing: -0.02em; }
    .section-title p { margin: 4px 0 0; color: var(--muted); font-size: 12px; }

    .tab-panel { display: none; }
    .tab-panel.active { display: block; }

    .metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
      margin-bottom: 18px;
    }
    .metric-card { padding: 20px; }
    .metric-label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      margin-bottom: 12px;
    }
    .metric-value { margin: 0; font-size: 32px; font-weight: 800; letter-spacing: -0.04em; }
    .metric-meta { margin-top: 10px; color: var(--muted); font-size: 12px; }

    .grid-2 {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }

    .mini-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
    }

    .mini-card {
      padding: 18px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.03);
    }
    .mini-title { margin: 0; font-size: 13px; font-weight: 700; }
    .mini-copy { margin: 4px 0 0; color: var(--muted); font-size: 12px; }
    .mini-value { margin-top: 12px; font-size: 24px; font-weight: 800; letter-spacing: -0.04em; }

    .list-block { display: grid; gap: 12px; }
    .list-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 14px 16px;
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--line);
    }
    .list-title { margin: 0 0 5px; font-size: 13px; font-weight: 700; }
    .list-copy { margin: 0; color: var(--muted); font-size: 12px; }

    .pill {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 7px 10px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.02em;
      white-space: nowrap;
    }
    .pill.success { color: #cbffde; background: rgba(46, 204, 113, 0.12); border: 1px solid rgba(46, 204, 113, 0.22); }
    .pill.warning { color: #ffe8b0; background: rgba(245, 184, 76, 0.12); border: 1px solid rgba(245, 184, 76, 0.22); }
    .pill.danger { color: #ffd0d0; background: rgba(255, 107, 107, 0.12); border: 1px solid rgba(255, 107, 107, 0.22); }

    .bars { display: grid; gap: 14px; margin-top: 18px; }
    .bar-row {
      display: grid;
      grid-template-columns: 150px 1fr 60px;
      gap: 14px;
      align-items: center;
    }
    .bar-label { color: #dfe7ff; font-size: 13px; font-weight: 600; }
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
      background: linear-gradient(90deg, var(--primary), #48d3ff);
    }
    .bar-value { color: var(--muted); font-size: 12px; text-align: right; }

    table { width: 100%; border-collapse: collapse; }
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
    tr:last-child td { border-bottom: 0; }

    .admin-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
      align-items: start;
    }

    .stack {
      display: grid;
      gap: 18px;
      align-content: start;
    }

    .taxonomy-stack {
      gap: 10px;
    }

    .form-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }

    .compact-panel .form-grid {
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }

    .field {
      display: grid;
      gap: 8px;
    }

    .field.span-2 {
      grid-column: span 2;
    }

    .field label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }

    .input,
    .select {
      width: 100%;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.03);
      color: var(--text);
      padding: 12px 14px;
      font-size: 13px;
      outline: none;
    }

    .input:focus,
    .select:focus {
      border-color: rgba(124, 156, 255, 0.5);
      box-shadow: 0 0 0 3px rgba(124, 156, 255, 0.12);
    }

    .form-actions,
    .table-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .action-btn {
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 10px;
      background: rgba(255, 255, 255, 0.04);
      color: var(--text);
      padding: 8px 12px;
      font-size: 12px;
      cursor: pointer;
    }

    .action-btn.primary {
      background: rgba(124, 156, 255, 0.16);
      border-color: rgba(124, 156, 255, 0.36);
    }

    .action-btn.danger {
      background: rgba(255, 107, 107, 0.12);
      border-color: rgba(255, 107, 107, 0.24);
    }

    .helper-text {
      margin: 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.6;
    }

    .empty-state {
      padding: 20px 0 4px;
      color: var(--muted);
      font-size: 13px;
      text-align: center;
    }

    @media (max-width: 1360px) {
      .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .grid-2, .mini-grid, .admin-grid { grid-template-columns: 1fr; }
      .compact-panel .form-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 980px) {
      .layout { grid-template-columns: 1fr; }
      .sidebar { border-right: 0; border-bottom: 1px solid var(--line); }
    }
    @media (max-width: 720px) {
      .content { padding: 18px; }
      .metrics { grid-template-columns: 1fr; }
      .bar-row { grid-template-columns: 1fr; }
      .form-grid { grid-template-columns: 1fr; }
      .field.span-2 { grid-column: span 1; }
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

      <p class="nav-label">메뉴</p>
      <button class="nav-button active" data-tab="dashboard" type="button"><span class="nav-icon">DB</span><span>대시보드</span></button>
      <button class="nav-button" data-tab="pipeline" type="button"><span class="nav-icon">OP</span><span>소싱 운영</span></button>
      <button class="nav-button" data-tab="candidates" type="button"><span class="nav-icon">PD</span><span>상품 후보 관리</span></button>
      <button class="nav-button" data-tab="taxonomy" type="button"><span class="nav-icon">TX</span><span>테마 관리</span></button>
      <button class="nav-button" data-tab="ranking" type="button"><span class="nav-icon">RK</span><span>랭킹 관리</span></button>
      <button class="nav-button" data-tab="users" type="button"><span class="nav-icon">US</span><span>사용자 및 과금</span></button>
      <button class="nav-button" data-tab="logs" type="button"><span class="nav-icon">LG</span><span>로그 및 이벤트</span></button>

      <div class="sidebar-footer">
        <p class="footer-title">현재 운영 정책</p>
        <p class="footer-copy">
          키워드 소싱은 3일 주기로 실행합니다. 네이버 API는 정상 연결 상태이며,
          Bright Data는 이후 쿠팡 보강 수집 단계에서만 사용합니다.
        </p>
        <a href="/health">시스템 상태 보기</a>
      </div>
    </aside>

    <main class="content">
      <section id="dashboard" class="tab-panel active">
        <div class="metrics">
          <article class="card metric-card"><div class="metric-label">키워드 풀</div><p class="metric-value">18,420</p><div class="metric-meta">지난 회차 대비 +12.8% / 활성 테마 23개</div></article>
          <article class="card metric-card"><div class="metric-label">신규 후보</div><p class="metric-value">486</p><div class="metric-meta">검수 대기 73건 / 숨김 11건</div></article>
          <article class="card metric-card"><div class="metric-label">활성 구독자</div><p class="metric-value">1,274</p><div class="metric-meta">이번 달 +4.2% / 체험 사용자 42명</div></article>
          <article class="card metric-card"><div class="metric-label">실패 작업</div><p class="metric-value">03</p><div class="metric-meta">API 재시도 2건 / 점검 필요</div></article>
        </div>
        <div class="grid-2">
          <article class="card panel">
            <div class="section-title"><div><h2>플랫폼 상태</h2><p>핵심 인프라와 배치 상태</p></div></div>
            <div class="list-block">
              <div class="list-item"><div><p class="list-title">네이버 API 연결 상태</p><p class="list-copy">검색 API가 정상적으로 활성화되어 있습니다.</p></div><span class="pill success">정상</span></div>
              <div class="list-item"><div><p class="list-title">키워드 배치 스케줄</p><p class="list-copy">다음 전체 실행까지 2일 11시간 남았습니다.</p></div><span class="pill warning">대기</span></div>
              <div class="list-item"><div><p class="list-title">쿠팡 보강 수집</p><p class="list-copy">Bright Data 파이프라인은 아직 활성화하지 않았습니다.</p></div><span class="pill danger">보류</span></div>
            </div>
          </article>
          <article class="card panel">
            <div class="section-title"><div><h2>우선 확인 필요</h2><p>운영자가 먼저 볼 알림</p></div></div>
            <div class="list-block">
              <div class="list-item"><div><p class="list-title">주방 편의도구 중복 seed 18건</p><p class="list-copy">다음 자동 반영 전 검토가 필요합니다.</p></div><span class="pill warning">주의</span></div>
              <div class="list-item"><div><p class="list-title">구독 갱신 실패 2건</p><p class="list-copy">유예기간 진입 계정을 확인해야 합니다.</p></div><span class="pill warning">과금</span></div>
              <div class="list-item"><div><p class="list-title">쿠팡 파이프라인 준비 중</p><p class="list-copy">실수집 전까지 운영 노출 금지 상태입니다.</p></div><span class="pill danger">보류</span></div>
            </div>
          </article>
        </div>
      </section>

      <section id="pipeline" class="tab-panel">
        <article class="card panel">
          <div class="section-title"><div><h2>소싱 운영</h2><p>테마별 키워드 수집 처리량과 배치 흐름</p></div></div>
          <div class="bars">
            <div class="bar-row"><span class="bar-label">생활용품</span><div class="bar-track"><div class="bar-fill" style="width:92%"></div></div><span class="bar-value">3,820</span></div>
            <div class="bar-row"><span class="bar-label">책상 꾸미기</span><div class="bar-track"><div class="bar-fill" style="width:78%"></div></div><span class="bar-value">2,940</span></div>
            <div class="bar-row"><span class="bar-label">주방 편의도구</span><div class="bar-track"><div class="bar-fill" style="width:85%"></div></div><span class="bar-value">3,210</span></div>
            <div class="bar-row"><span class="bar-label">반려동물 소품</span><div class="bar-track"><div class="bar-fill" style="width:61%"></div></div><span class="bar-value">2,114</span></div>
            <div class="bar-row"><span class="bar-label">차량 감성용품</span><div class="bar-track"><div class="bar-fill" style="width:56%"></div></div><span class="bar-value">1,902</span></div>
          </div>
        </article>
      </section>

      <section id="candidates" class="tab-panel">
        <div class="grid-2">
          <article class="card panel">
            <div class="section-title"><div><h2>상품 후보 관리</h2><p>운영 승인 대기 중인 핵심 후보 상품</p></div></div>
            <table>
              <thead><tr><th>상품명</th><th>테마</th><th>경쟁강도</th><th>점수</th><th>상태</th></tr></thead>
              <tbody>
                <tr><td>실리콘 싱크대 정리 랙</td><td>주방 편의도구</td><td><span class="pill success">낮음</span></td><td>91.4</td><td><span class="pill warning">검수중</span></td></tr>
                <tr><td>미니멀 모니터 받침대</td><td>책상 꾸미기</td><td><span class="pill warning">보통</span></td><td>88.7</td><td><span class="pill success">승인</span></td></tr>
                <tr><td>휴대용 트렁크 분리 수납백</td><td>차량용 소품</td><td><span class="pill success">낮음</span></td><td>82.1</td><td><span class="pill warning">검수중</span></td></tr>
                <tr><td>흡수형 극세사 욕실 매트</td><td>욕실용품</td><td><span class="pill danger">높음</span></td><td>74.5</td><td><span class="pill danger">보류</span></td></tr>
              </tbody>
            </table>
          </article>
          <article class="card panel">
            <div class="section-title"><div><h2>검수 작업량</h2><p>후보 검수 단계별 현재 대기 현황</p></div></div>
            <div class="mini-grid">
              <div class="mini-card"><p class="mini-title">검수 대기</p><p class="mini-copy">운영자 판단이 필요한 상태</p><div class="mini-value">73</div></div>
              <div class="mini-card"><p class="mini-title">사용자 노출 승인</p><p class="mini-copy">현재 사용자 화면에 노출 중</p><div class="mini-value">214</div></div>
              <div class="mini-card"><p class="mini-title">제외 또는 숨김</p><p class="mini-copy">수동 처리 또는 규칙 기반 제외</p><div class="mini-value">39</div></div>
            </div>
          </article>
        </div>
      </section>

      <section id="taxonomy" class="tab-panel">
        <div class="admin-grid">
          <div class="stack taxonomy-stack">
            <article class="card panel compact-panel">
              <div class="section-title">
                <div>
                  <h2>테마 관리</h2>
                  <p>테마 추가, 수정, 삭제를 빠르게 처리합니다.</p>
                </div>
              </div>
              <div class="form-grid" id="theme-form">
                <div class="field">
                  <label for="theme-code">테마 코드</label>
                  <input class="input" id="theme-code" type="text" placeholder="예: living" />
                </div>
                <div class="field">
                  <label for="theme-name">테마명</label>
                  <input class="input" id="theme-name" type="text" placeholder="예: 생활용품" />
                </div>
                <div class="field">
                  <label for="theme-priority">우선순위</label>
                  <input class="input" id="theme-priority" type="number" min="1" placeholder="1" />
                </div>
                <div class="field">
                  <label for="theme-status">상태</label>
                  <select class="select" id="theme-status">
                    <option value="핵심">핵심</option>
                    <option value="확장">확장</option>
                    <option value="관찰">관찰</option>
                  </select>
                </div>
              </div>
              <div class="form-actions" style="margin-top: 16px;">
                <button class="action-btn primary" id="theme-save-btn" type="button">테마 추가</button>
                <button class="action-btn" id="theme-reset-btn" type="button">입력 초기화</button>
              </div>
            </article>

            <article class="card panel">
              <div class="section-title">
                <div>
                  <h2>테마 테이블</h2>
                  <p>현재 운영 중인 테마 목록</p>
                </div>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>코드</th>
                    <th>테마명</th>
                    <th>우선순위</th>
                    <th>상태</th>
                    <th>액션</th>
                  </tr>
                </thead>
                <tbody id="theme-table-body"></tbody>
              </table>
            </article>
          </div>

          <div class="stack">
            <article class="card panel">
              <div class="section-title">
                <div>
                  <h2>CID 관리</h2>
                  <p>CID, 카테고리명, 경로, 연결 테마를 관리합니다.</p>
                </div>
              </div>
              <div class="form-grid" id="cid-form">
                <div class="field">
                  <label for="cid-value">CID</label>
                  <input class="input" id="cid-value" type="text" placeholder="예: 50000000" />
                </div>
                <div class="field">
                  <label for="cid-name">카테고리명</label>
                  <input class="input" id="cid-name" type="text" placeholder="예: 수납정리용품" />
                </div>
                <div class="field span-2">
                  <label for="cid-path">카테고리 경로</label>
                  <input class="input" id="cid-path" type="text" placeholder="예: 생활/건강 > 생활용품 > 수납/정리용품" />
                </div>
                <div class="field">
                  <label for="cid-theme">연결 테마</label>
                  <select class="select" id="cid-theme"></select>
                </div>
                <div class="field">
                  <label for="cid-status">상태</label>
                  <select class="select" id="cid-status">
                    <option value="활성">활성</option>
                    <option value="보류">보류</option>
                  </select>
                </div>
              </div>
              <div class="form-actions" style="margin-top: 16px;">
                <button class="action-btn primary" id="cid-save-btn" type="button">CID 추가</button>
                <button class="action-btn" id="cid-reset-btn" type="button">입력 초기화</button>
              </div>
              <p class="helper-text" style="margin-top: 12px;">테마를 삭제하면 연결된 CID는 유지되지만 테마명은 비워집니다.</p>
            </article>

            <article class="card panel">
              <div class="section-title">
                <div>
                  <h2>CID 테이블</h2>
                  <p>테마에 연결된 CID 목록</p>
                </div>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>CID</th>
                    <th>카테고리명</th>
                    <th>테마</th>
                    <th>상태</th>
                    <th>액션</th>
                  </tr>
                </thead>
                <tbody id="cid-table-body"></tbody>
              </table>
            </article>
          </div>
        </div>
      </section>

      <section id="ranking" class="tab-panel">
        <article class="card panel">
          <div class="section-title"><div><h2>랭킹 관리</h2><p>추천 엔진 가중치와 노출 기준 조정</p></div></div>
          <div class="bars">
            <div class="bar-row"><span class="bar-label">수요 신호</span><div class="bar-track"><div class="bar-fill" style="width:88%"></div></div><span class="bar-value">0.88</span></div>
            <div class="bar-row"><span class="bar-label">저경쟁 보정</span><div class="bar-track"><div class="bar-fill" style="width:74%"></div></div><span class="bar-value">0.74</span></div>
            <div class="bar-row"><span class="bar-label">신규성 가중치</span><div class="bar-track"><div class="bar-fill" style="width:62%"></div></div><span class="bar-value">0.62</span></div>
            <div class="bar-row"><span class="bar-label">수동 큐레이션</span><div class="bar-track"><div class="bar-fill" style="width:55%"></div></div><span class="bar-value">0.55</span></div>
          </div>
        </article>
      </section>

      <section id="users" class="tab-panel">
        <article class="card panel">
          <div class="section-title"><div><h2>사용자 및 과금</h2><p>구독 상태와 기기 제한 현황 관리</p></div></div>
          <div class="mini-grid">
            <div class="mini-card"><p class="mini-title">활성 구독</p><p class="mini-copy">Basic, Pro 전체 사용자 합계</p><div class="mini-value">1,274</div></div>
            <div class="mini-card"><p class="mini-title">유예기간 계정</p><p class="mini-copy">결제 복구 대상 계정</p><div class="mini-value">12</div></div>
            <div class="mini-card"><p class="mini-title">기기 슬롯 가득 참</p><p class="mini-copy">2기기 제한에 도달한 사용자</p><div class="mini-value">418</div></div>
          </div>
        </article>
      </section>

      <section id="logs" class="tab-panel">
        <article class="card panel">
          <div class="section-title"><div><h2>로그 및 이벤트</h2><p>소싱, 인증, 과금 흐름의 운영 이력</p></div></div>
          <table>
            <thead><tr><th>시간</th><th>이벤트</th><th>영역</th><th>심각도</th><th>액션</th></tr></thead>
            <tbody>
              <tr><td>14:28</td><td>책상 꾸미기 테마의 네이버 키워드 배치가 완료되었습니다.</td><td>파이프라인</td><td><span class="pill success">정보</span></td><td>배치 보기</td></tr>
              <tr><td>14:12</td><td>구독자 2명의 결제 갱신에 실패했습니다.</td><td>과금</td><td><span class="pill warning">주의</span></td><td>복구 열기</td></tr>
              <tr><td>13:54</td><td>주방 편의도구 테마에서 키워드 중복 임계치를 초과했습니다.</td><td>품질</td><td><span class="pill danger">경고</span></td><td>규칙 검토</td></tr>
              <tr><td>13:31</td><td>관리자 계정의 신규 기기 승인이 완료되었습니다.</td><td>인증</td><td><span class="pill success">정보</span></td><td>감사 로그 보기</td></tr>
            </tbody>
          </table>
        </article>
      </section>
    </main>
  </div>
  <script>
    const navButtons = document.querySelectorAll(".nav-button");
    const panels = document.querySelectorAll(".tab-panel");

    let editingThemeId = null;
    let editingCidId = null;
    let themes = [];
    let cidItems = [];

    const themeCodeInput = document.getElementById("theme-code");
    const themeNameInput = document.getElementById("theme-name");
    const themePriorityInput = document.getElementById("theme-priority");
    const themeStatusInput = document.getElementById("theme-status");
    const themeSaveBtn = document.getElementById("theme-save-btn");
    const themeResetBtn = document.getElementById("theme-reset-btn");
    const themeTableBody = document.getElementById("theme-table-body");

    const cidValueInput = document.getElementById("cid-value");
    const cidNameInput = document.getElementById("cid-name");
    const cidPathInput = document.getElementById("cid-path");
    const cidThemeInput = document.getElementById("cid-theme");
    const cidStatusInput = document.getElementById("cid-status");
    const cidSaveBtn = document.getElementById("cid-save-btn");
    const cidResetBtn = document.getElementById("cid-reset-btn");
    const cidTableBody = document.getElementById("cid-table-body");

    async function apiFetch(url, options = {}) {
      const response = await fetch(url, {
        headers: {
          "Content-Type": "application/json"
        },
        ...options
      });

      if (!response.ok) {
        let detail = "요청 처리에 실패했습니다.";
        try {
          const errorData = await response.json();
          detail = errorData.detail || detail;
        } catch (error) {
          detail = response.statusText || detail;
        }
        throw new Error(detail);
      }

      if (response.status === 204) {
        return null;
      }

      return response.json();
    }

    function getThemeById(themeId) {
      return themes.find((theme) => theme.id === themeId) || null;
    }

    function resetThemeForm() {
      editingThemeId = null;
      themeCodeInput.value = "";
      themeNameInput.value = "";
      themePriorityInput.value = "";
      themeStatusInput.value = "핵심";
      themeSaveBtn.textContent = "테마 추가";
    }

    function resetCidForm() {
      editingCidId = null;
      cidValueInput.value = "";
      cidNameInput.value = "";
      cidPathInput.value = "";
      cidStatusInput.value = "활성";
      if (themes.length > 0) {
        cidThemeInput.value = String(themes[0].id);
      }
      cidSaveBtn.textContent = "CID 추가";
    }

    function renderThemeOptions() {
      cidThemeInput.innerHTML = themes
        .sort((a, b) => a.display_order - b.display_order)
        .map((theme) => `<option value="${theme.id}">${theme.theme_name}</option>`)
        .join("");
    }

    function renderThemes() {
      const sortedThemes = [...themes].sort((a, b) => a.display_order - b.display_order);

      if (sortedThemes.length === 0) {
        themeTableBody.innerHTML = '<tr><td colspan="5" class="empty-state">등록된 테마가 없습니다.</td></tr>';
        return;
      }

      themeTableBody.innerHTML = sortedThemes
        .map((theme) => `
          <tr>
            <td>${theme.theme_code}</td>
            <td>${theme.theme_name}</td>
            <td>${theme.display_order}</td>
            <td><span class="pill ${theme.status_label === "핵심" ? "success" : "warning"}">${theme.status_label}</span></td>
            <td>
              <div class="table-actions">
                <button class="action-btn" type="button" onclick="editTheme(${theme.id})">수정</button>
                <button class="action-btn danger" type="button" onclick="deleteTheme(${theme.id})">삭제</button>
              </div>
            </td>
          </tr>
        `)
        .join("");
    }

    function renderCids() {
      if (cidItems.length === 0) {
        cidTableBody.innerHTML = '<tr><td colspan="5" class="empty-state">등록된 CID가 없습니다.</td></tr>';
        return;
      }

      cidTableBody.innerHTML = cidItems
        .map((item) => {
          const theme = getThemeById(item.themeId);
          return `
            <tr>
              <td>${item.cid}</td>
              <td>
                <div>${item.name}</div>
                <div class="helper-text">${item.path}</div>
              </td>
              <td>${theme ? theme.theme_name : "-"}</td>
              <td><span class="pill ${item.status === "활성" ? "success" : "warning"}">${item.status}</span></td>
              <td>
                <div class="table-actions">
                  <button class="action-btn" type="button" onclick="editCid(${item.id})">수정</button>
                  <button class="action-btn danger" type="button" onclick="deleteCid(${item.id})">삭제</button>
                </div>
              </td>
            </tr>
          `;
        })
        .join("");
    }

    function renderTaxonomy() {
      renderThemeOptions();
      renderThemes();
      renderCids();
      if (!editingCidId && themes.length > 0 && !cidThemeInput.value) {
        cidThemeInput.value = String(themes[0].id);
      }
    }

    async function loadTaxonomy() {
      const [themeData, categoryData] = await Promise.all([
        apiFetch("/api/admin/themes"),
        apiFetch("/api/admin/categories")
      ]);

      themes = (themeData.items || []).map((item) => ({
        ...item,
        themeId: item.id
      }));
      cidItems = (categoryData.items || []).map((item) => ({
        id: item.id,
        cid: item.cid,
        name: item.category_name,
        path: item.full_path,
        themeId: item.theme_id,
        status: item.status_label
      }));

      renderTaxonomy();
    }

    function editTheme(themeId) {
      const theme = getThemeById(themeId);
      if (!theme) return;

      editingThemeId = themeId;
      themeCodeInput.value = theme.theme_code;
      themeNameInput.value = theme.theme_name;
      themePriorityInput.value = theme.display_order;
      themeStatusInput.value = theme.status_label;
      themeSaveBtn.textContent = "테마 수정";
    }

    async function deleteTheme(themeId) {
      await apiFetch(`/api/admin/themes/${themeId}`, {
        method: "DELETE"
      });

      if (editingThemeId === themeId) {
        resetThemeForm();
      }

      await loadTaxonomy();
    }

    function editCid(cidId) {
      const item = cidItems.find((cid) => cid.id === cidId);
      if (!item) return;

      editingCidId = cidId;
      cidValueInput.value = item.cid;
      cidNameInput.value = item.name;
      cidPathInput.value = item.path;
      cidThemeInput.value = item.themeId ? String(item.themeId) : "";
      cidStatusInput.value = item.status;
      cidSaveBtn.textContent = "CID 수정";
    }

    async function deleteCid(cidId) {
      await apiFetch(`/api/admin/categories/${cidId}`, {
        method: "DELETE"
      });

      if (editingCidId === cidId) {
        resetCidForm();
      }

      await loadTaxonomy();
    }

    themeSaveBtn.addEventListener("click", async () => {
      const code = themeCodeInput.value.trim();
      const name = themeNameInput.value.trim();
      const priority = Number(themePriorityInput.value);
      const status = themeStatusInput.value;

      if (!code || !name || !priority) {
        return;
      }

      const payload = {
        theme_code: code,
        theme_name: name,
        display_order: priority,
        status_label: status
      };

      if (editingThemeId) {
        await apiFetch(`/api/admin/themes/${editingThemeId}`, {
          method: "PUT",
          body: JSON.stringify(payload)
        });
      } else {
        await apiFetch("/api/admin/themes", {
          method: "POST",
          body: JSON.stringify(payload)
        });
      }

      resetThemeForm();
      await loadTaxonomy();
    });

    themeResetBtn.addEventListener("click", resetThemeForm);

    cidSaveBtn.addEventListener("click", async () => {
      const cid = cidValueInput.value.trim();
      const name = cidNameInput.value.trim();
      const path = cidPathInput.value.trim();
      const themeId = cidThemeInput.value ? Number(cidThemeInput.value) : null;
      const status = cidStatusInput.value;

      if (!cid || !name || !path) {
        return;
      }

      const payload = {
        cid,
        category_name: name,
        full_path: path,
        theme_id: themeId,
        status_label: status
      };

      if (editingCidId) {
        await apiFetch(`/api/admin/categories/${editingCidId}`, {
          method: "PUT",
          body: JSON.stringify(payload)
        });
      } else {
        await apiFetch("/api/admin/categories", {
          method: "POST",
          body: JSON.stringify(payload)
        });
      }

      resetCidForm();
      await loadTaxonomy();
    });

    cidResetBtn.addEventListener("click", resetCidForm);

    window.editTheme = editTheme;
    window.deleteTheme = deleteTheme;
    window.editCid = editCid;
    window.deleteCid = deleteCid;

    loadTaxonomy().catch((error) => {
      themeTableBody.innerHTML = `<tr><td colspan="5" class="empty-state">${error.message}</td></tr>`;
      cidTableBody.innerHTML = `<tr><td colspan="5" class="empty-state">${error.message}</td></tr>`;
    });

    navButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const tabId = button.dataset.tab;
        navButtons.forEach((item) => item.classList.remove("active"));
        panels.forEach((panel) => panel.classList.remove("active"));
        button.classList.add("active");
        document.getElementById(tabId).classList.add("active");
      });
    });
  </script>
</body>
</html>
"""


@router.get("/admin", response_class=HTMLResponse)
async def admin_console() -> HTMLResponse:
    return HTMLResponse(content=ADMIN_HTML)
