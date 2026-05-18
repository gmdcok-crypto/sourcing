from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["admin"])


ADMIN_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>소싱 관리자 - 테마 관리</title>
  <style>
    :root {
      --bg: #0b1020;
      --bg-soft: #121a31;
      --line: rgba(255, 255, 255, 0.08);
      --text: #eef2ff;
      --muted: #8f9bb7;
      --primary: #7c9cff;
      --primary-soft: rgba(124, 156, 255, 0.16);
      --success: #39d98a;
      --danger: #ff7b86;
      --radius-lg: 18px;
      --radius-md: 14px;
      --shadow: 0 24px 60px rgba(0, 0, 0, 0.28);
    }

    * {
      box-sizing: border-box;
    }

    html, body {
      margin: 0;
      padding: 0;
      background: linear-gradient(180deg, #09101d 0%, #0b1020 100%);
      color: var(--text);
      font-family: Inter, "Segoe UI", Arial, sans-serif;
      min-height: 100%;
    }

    .layout {
      display: grid;
      grid-template-columns: 320px 1fr;
      min-height: 100vh;
    }

    .sidebar {
      position: sticky;
      top: 0;
      height: 100vh;
      padding: 24px 18px;
      border-right: 1px solid var(--line);
      background: rgba(10, 14, 27, 0.95);
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

    .sidebar-footer {
      margin-top: 16px;
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

    .toolbar {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 20px;
    }

    .search,
    .input,
    .select {
      width: 100%;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(14, 20, 35, 0.92);
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

    .theme-layout {
      display: grid;
      grid-template-columns: 320px 1fr;
      gap: 18px;
    }

    .card {
      background: linear-gradient(180deg, rgba(18, 26, 49, 0.95), rgba(14, 21, 39, 0.94));
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow);
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

    .panel {
      padding: 20px;
    }

    .theme-list {
      display: grid;
      gap: 10px;
      max-height: calc(100vh - 250px);
      overflow: auto;
      padding-right: 4px;
    }

    .theme-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px;
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--line);
      cursor: pointer;
      transition: all 0.18s ease;
    }

    .theme-item.active,
    .theme-item:hover {
      border-color: rgba(124, 156, 255, 0.28);
      background: rgba(124, 156, 255, 0.12);
    }

    .theme-name {
      margin: 0 0 6px;
      font-size: 13px;
      font-weight: 700;
    }

    .theme-copy {
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

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }

    .summary-card {
      padding: 18px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.03);
    }

    .summary-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;
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

    .table-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .table-actions .btn {
      padding: 8px 12px;
      font-size: 12px;
    }

    .status-text {
      color: var(--muted);
      font-size: 12px;
    }

    .inline-form {
      display: grid;
      grid-template-columns: 1.2fr 160px 160px auto;
      gap: 10px;
      margin-bottom: 18px;
    }

    .empty {
      padding: 32px;
      border: 1px dashed var(--line);
      border-radius: 18px;
      color: var(--muted);
      text-align: center;
    }

    .error {
      color: #ffb2b2;
      margin-top: 12px;
      font-size: 13px;
    }

    .success-text {
      color: #8ef0b5;
      margin-top: 12px;
      font-size: 13px;
    }

    @media (max-width: 1360px) {
      .theme-layout {
        grid-template-columns: 1fr;
      }

      .summary-grid {
        grid-template-columns: 1fr;
      }

      .inline-form {
        grid-template-columns: 1fr 1fr;
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

      .inline-form {
        grid-template-columns: 1fr;
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

      <div class="sidebar-footer">
        <p class="footer-title">테마 관리 안내</p>
        <p class="footer-copy">
          좌측에서 테마를 선택하면 우측에서 연결된 CID 목록을 바로 조회할 수 있습니다.
          새 CID 추가, 정렬 순서 수정, 활성 상태 변경, 삭제 작업을 이 화면에서 처리합니다.
        </p>
        <a class="btn" href="/health" style="display:inline-block;">시스템 상태 보기</a>
      </div>
    </aside>

    <main class="content">
      <div class="topbar">
        <div class="topbar-copy">
          <h1>테마 관리</h1>
          <p>테마별 CID 목록을 조회하고, 연결된 카테고리를 추가, 수정, 삭제할 수 있습니다.</p>
        </div>
      </div>

      <div class="toolbar">
        <input id="theme-search" class="search" type="text" placeholder="테마명 검색" />
      </div>

      <section class="theme-layout">
        <aside class="card panel">
          <div class="section-title">
            <div>
              <h2>테마 목록</h2>
              <p>테마를 선택하면 연결된 CID를 불러옵니다.</p>
            </div>
          </div>
          <div id="theme-list" class="theme-list"></div>
        </aside>

        <section class="card panel">
          <div class="section-title">
            <div>
              <h2 id="theme-title">테마를 선택하세요</h2>
              <p id="theme-subtitle">좌측에서 테마를 선택하면 CID 테이블을 확인할 수 있습니다.</p>
            </div>
            <div class="status-text" id="theme-status"></div>
          </div>

          <div class="summary-grid">
            <div class="summary-card">
              <div class="summary-head">
                <strong>활성 CID</strong>
                <span id="summary-active">0</span>
              </div>
              <div class="status-text">현재 활성 상태로 연결된 카테고리 수</div>
            </div>
            <div class="summary-card">
              <div class="summary-head">
                <strong>전체 매핑</strong>
                <span id="summary-total">0</span>
              </div>
              <div class="status-text">선택된 테마에 연결된 전체 CID 수</div>
            </div>
            <div class="summary-card">
              <div class="summary-head">
                <strong>테마 상태</strong>
                <span id="summary-theme-active">-</span>
              </div>
              <div class="status-text">테마 활성 여부와 운영 기준 표시</div>
            </div>
          </div>

          <div class="section-title">
            <div>
              <h2>CID 매핑 추가</h2>
              <p>기존 `naver_categories`에 있는 CID만 연결할 수 있습니다.</p>
            </div>
          </div>

          <div class="inline-form">
            <input id="new-cid" class="input" type="text" placeholder="추가할 CID 입력" />
            <input id="new-order" class="input" type="number" min="0" value="0" placeholder="정렬순서" />
            <select id="new-active" class="select">
              <option value="true">활성</option>
              <option value="false">비활성</option>
            </select>
            <button id="add-button" class="btn primary" type="button">추가</button>
          </div>

          <div id="message-area"></div>

          <div class="section-title" style="margin-top: 22px;">
            <div>
              <h2>CID 테이블</h2>
              <p>정렬순서와 활성 상태를 수정하거나 매핑을 삭제할 수 있습니다.</p>
            </div>
          </div>

          <div id="table-wrapper">
            <div class="empty">선택된 테마가 없습니다.</div>
          </div>
        </section>
      </section>
    </main>
  </div>
  <script>
    const state = {
      themes: [],
      selectedThemeId: null,
      selectedTheme: null,
      mappings: [],
    };

    const themeListEl = document.getElementById("theme-list");
    const themeTitleEl = document.getElementById("theme-title");
    const themeSubtitleEl = document.getElementById("theme-subtitle");
    const themeStatusEl = document.getElementById("theme-status");
    const summaryActiveEl = document.getElementById("summary-active");
    const summaryTotalEl = document.getElementById("summary-total");
    const summaryThemeActiveEl = document.getElementById("summary-theme-active");
    const tableWrapperEl = document.getElementById("table-wrapper");
    const messageAreaEl = document.getElementById("message-area");
    const searchInputEl = document.getElementById("theme-search");
    const newCidEl = document.getElementById("new-cid");
    const newOrderEl = document.getElementById("new-order");
    const newActiveEl = document.getElementById("new-active");
    const addButtonEl = document.getElementById("add-button");

    function showMessage(message, isError = false) {
      messageAreaEl.innerHTML = `<div class="${isError ? "error" : "success-text"}">${message}</div>`;
      window.setTimeout(() => {
        messageAreaEl.innerHTML = "";
      }, 3000);
    }

    function renderThemeList() {
      const keyword = searchInputEl.value.trim().toLowerCase();
      const items = state.themes.filter((theme) =>
        theme.theme_name.toLowerCase().includes(keyword)
      );

      if (!items.length) {
        themeListEl.innerHTML = '<div class="empty">검색 결과가 없습니다.</div>';
        return;
      }

      themeListEl.innerHTML = items
        .map((theme) => {
          const activeClass = theme.id === state.selectedThemeId ? "active" : "";
          return `
            <button class="theme-item ${activeClass}" data-theme-id="${theme.id}" type="button">
              <div style="text-align:left;">
                <p class="theme-name">${theme.theme_name}</p>
                <p class="theme-copy">CID ${theme.category_count}개 / 코드 ${theme.theme_code}</p>
              </div>
              <span class="pill ${theme.is_active ? "success" : "danger"}">${theme.is_active ? "활성" : "비활성"}</span>
            </button>
          `;
        })
        .join("");

      document.querySelectorAll("[data-theme-id]").forEach((button) => {
        button.addEventListener("click", () => {
          loadThemeCategories(Number(button.dataset.themeId));
        });
      });
    }

    function renderThemeSummary() {
      if (!state.selectedTheme) {
        themeTitleEl.textContent = "테마를 선택하세요";
        themeSubtitleEl.textContent = "좌측에서 테마를 선택하면 CID 테이블을 확인할 수 있습니다.";
        themeStatusEl.textContent = "";
        summaryActiveEl.textContent = "0";
        summaryTotalEl.textContent = "0";
        summaryThemeActiveEl.textContent = "-";
        tableWrapperEl.innerHTML = '<div class="empty">선택된 테마가 없습니다.</div>';
        return;
      }

      const activeCount = state.mappings.filter((item) => item.is_active).length;
      themeTitleEl.textContent = state.selectedTheme.theme_name;
      themeSubtitleEl.textContent = `${state.selectedTheme.theme_code} / 테마별 CID 매핑을 관리합니다.`;
      themeStatusEl.textContent = `총 ${state.mappings.length}개 매핑`;
      summaryActiveEl.textContent = String(activeCount);
      summaryTotalEl.textContent = String(state.mappings.length);
      summaryThemeActiveEl.textContent = state.selectedTheme.is_active ? "활성" : "비활성";

      if (!state.mappings.length) {
        tableWrapperEl.innerHTML = '<div class="empty">이 테마에는 아직 연결된 CID가 없습니다.</div>';
        return;
      }

      tableWrapperEl.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>CID</th>
              <th>카테고리명</th>
              <th>전체 경로</th>
              <th>정렬순서</th>
              <th>상태</th>
              <th>액션</th>
            </tr>
          </thead>
          <tbody>
            ${state.mappings.map((item) => `
              <tr>
                <td>${item.cid}</td>
                <td>${item.category_name}</td>
                <td>${item.full_path}</td>
                <td><input class="input mapping-order" style="max-width:110px;" type="number" min="0" value="${item.display_order}" data-id="${item.id}" /></td>
                <td>
                  <select class="select mapping-active" style="max-width:130px;" data-id="${item.id}">
                    <option value="true" ${item.is_active ? "selected" : ""}>활성</option>
                    <option value="false" ${!item.is_active ? "selected" : ""}>비활성</option>
                  </select>
                </td>
                <td>
                  <div class="table-actions">
                    <button class="btn save-button" data-id="${item.id}" type="button">수정</button>
                    <button class="btn delete-button" data-id="${item.id}" type="button">삭제</button>
                  </div>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;

      document.querySelectorAll(".save-button").forEach((button) => {
        button.addEventListener("click", async () => {
          const id = Number(button.dataset.id);
          const orderInput = document.querySelector(`.mapping-order[data-id="${id}"]`);
          const activeSelect = document.querySelector(`.mapping-active[data-id="${id}"]`);
          await updateMapping(id, Number(orderInput.value), activeSelect.value === "true");
        });
      });

      document.querySelectorAll(".delete-button").forEach((button) => {
        button.addEventListener("click", async () => {
          const id = Number(button.dataset.id);
          if (!confirm("이 CID 매핑을 삭제하시겠습니까?")) {
            return;
          }
          await deleteMapping(id);
        });
      });
    }

    async function loadThemes() {
      const response = await fetch("/api/admin/themes");
      const data = await response.json();
      state.themes = data.items || [];
      renderThemeList();
      if (!state.selectedThemeId && state.themes.length) {
        await loadThemeCategories(state.themes[0].id);
      }
    }

    async function loadThemeCategories(themeId) {
      const response = await fetch(`/api/admin/themes/${themeId}/categories`);
      const data = await response.json();
      state.selectedThemeId = themeId;
      state.selectedTheme = state.themes.find((theme) => theme.id === themeId) || null;
      state.mappings = data.items || [];
      renderThemeList();
      renderThemeSummary();
    }

    async function addMapping() {
      if (!state.selectedThemeId) {
        showMessage("먼저 테마를 선택하세요.", true);
        return;
      }

      const payload = {
        cid: newCidEl.value.trim(),
        display_order: Number(newOrderEl.value || 0),
        is_active: newActiveEl.value === "true",
      };

      if (!payload.cid) {
        showMessage("CID를 입력하세요.", true);
        return;
      }

      const response = await fetch(`/api/admin/themes/${state.selectedThemeId}/categories`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) {
        showMessage(data.detail || "CID 추가에 실패했습니다.", true);
        return;
      }

      newCidEl.value = "";
      newOrderEl.value = "0";
      newActiveEl.value = "true";
      showMessage("CID 매핑을 저장했습니다.");
      await loadThemeCategories(state.selectedThemeId);
      await loadThemes();
    }

    async function updateMapping(mappingId, displayOrder, isActive) {
      const response = await fetch(`/api/admin/themes/${state.selectedThemeId}/categories/${mappingId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          display_order: displayOrder,
          is_active: isActive,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        showMessage(data.detail || "CID 수정에 실패했습니다.", true);
        return;
      }

      showMessage("CID 매핑을 수정했습니다.");
      await loadThemeCategories(state.selectedThemeId);
    }

    async function deleteMapping(mappingId) {
      const response = await fetch(`/api/admin/themes/${state.selectedThemeId}/categories/${mappingId}`, {
        method: "DELETE",
      });

      const data = await response.json();
      if (!response.ok) {
        showMessage(data.detail || "CID 삭제에 실패했습니다.", true);
        return;
      }

      showMessage("CID 매핑을 삭제했습니다.");
      await loadThemeCategories(state.selectedThemeId);
      await loadThemes();
    }

    searchInputEl.addEventListener("input", renderThemeList);
    addButtonEl.addEventListener("click", addMapping);

    loadThemes().catch((error) => {
      console.error(error);
      showMessage("테마 데이터를 불러오지 못했습니다. MYSQL_URL과 DB 상태를 확인하세요.", true);
    });
  </script>
</body>
</html>
"""


@router.get("/admin", response_class=HTMLResponse)
async def admin_console() -> HTMLResponse:
    return HTMLResponse(content=ADMIN_HTML)
