import json
from datetime import date, timedelta
from html import escape
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.api.routes_admin_theme_api import ensure_tables
from app.core.config import get_settings
from app.services.db import get_mysql_connection
from app.services.keyword_sourcing import KeywordSourcingService

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
    .pipeline-stack { display: grid; gap: 18px; }
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
    .progress-panel {
      display: grid;
      gap: 14px;
      margin-top: 18px;
      padding: 18px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.03);
    }
    .progress-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }
    .progress-card {
      padding: 14px 16px;
      border-radius: 14px;
      border: 1px solid rgba(255, 255, 255, 0.06);
      background: rgba(255, 255, 255, 0.025);
    }
    .progress-card-label { margin: 0 0 6px; color: var(--muted); font-size: 11px; }
    .progress-card-value { margin: 0; font-size: 18px; font-weight: 700; }
    .progress-meta { display: grid; gap: 6px; color: var(--muted); font-size: 12px; }
    .log-box {
      max-height: 220px;
      overflow: auto;
      padding: 14px 16px;
      border-radius: 14px;
      border: 1px solid rgba(255, 255, 255, 0.06);
      background: rgba(7, 11, 22, 0.72);
      font-size: 12px;
      line-height: 1.6;
      color: #dce4ff;
      white-space: pre-wrap;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 18px;
    }
    .summary-card {
      padding: 16px 18px;
      border-radius: 16px;
      border: 1px solid rgba(255, 255, 255, 0.06);
      background: rgba(255, 255, 255, 0.03);
    }
    .summary-label { margin: 0 0 6px; color: var(--muted); font-size: 12px; }
    .summary-value { margin: 0; font-size: 24px; font-weight: 800; }
    .keyword-table-wrap {
      margin-top: 18px;
      padding: 18px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.03);
      overflow-x: auto;
    }
    .keyword-pagination {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 14px;
    }
    .keyword-pagination-controls {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .keyword-pagination-pages {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }
    .keyword-pagination-meta {
      color: var(--muted);
      font-size: 12px;
    }
    .keyword-metrics-table { min-width: 1280px; }
    .keyword-metrics-table th {
      padding: 0 12px 14px;
      text-transform: none;
      letter-spacing: 0;
      white-space: nowrap;
    }
    .keyword-metrics-table td {
      padding: 2px 12px;
      white-space: nowrap;
    }
    .keyword-col { min-width: 160px; color: #9fc0ff; font-weight: 600; }
    .metric-cell { text-align: right; }
    .metric-center { text-align: center; }
    .toolbar-inline {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .history-toolbar {
      display: flex;
      align-items: end;
      gap: 10px;
      padding: 10px 12px;
      border-radius: 14px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      background: rgba(255, 255, 255, 0.03);
    }
    .history-toolbar .field {
      gap: 6px;
    }
    .history-date-wrap {
      display: flex;
      align-items: center;
      gap: 8px;
      position: relative;
    }
    .history-toolbar .input {
      width: auto;
      min-width: 180px;
      color-scheme: dark;
      cursor: default;
    }
    .history-picker-btn {
      width: 40px;
      height: 40px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      font-size: 18px;
      line-height: 1;
      color: #f5f7ff;
    }
    .history-calendar-popup {
      position: absolute;
      top: calc(100% + 10px);
      right: 0;
      width: 280px;
      padding: 14px;
      border-radius: 16px;
      border: 1px solid rgba(255, 255, 255, 0.1);
      background: #10151f;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
      z-index: 30;
      display: none;
    }
    .history-calendar-popup.open {
      display: block;
    }
    .calendar-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
    }
    .calendar-title {
      font-size: 14px;
      font-weight: 700;
      color: var(--text);
    }
    .calendar-nav-btn {
      width: 34px;
      height: 34px;
      padding: 0;
      font-size: 16px;
    }
    .calendar-weekdays,
    .calendar-grid {
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
      gap: 6px;
    }
    .calendar-weekday {
      text-align: center;
      font-size: 11px;
      color: var(--muted);
      padding-bottom: 4px;
    }
    .calendar-day {
      height: 34px;
      border-radius: 10px;
      border: 1px solid transparent;
      background: rgba(255, 255, 255, 0.03);
      color: var(--text);
      font-size: 12px;
      cursor: pointer;
      transition: transform 0.14s ease, background-color 0.14s ease, border-color 0.14s ease;
    }
    .calendar-day:hover {
      background: rgba(255, 255, 255, 0.08);
      border-color: rgba(255, 255, 255, 0.16);
      transform: translateY(-1px);
    }
    .calendar-day.outside {
      color: rgba(230, 236, 255, 0.38);
      background: rgba(255, 255, 255, 0.015);
    }
    .calendar-day.selected {
      background: rgba(124, 156, 255, 0.24);
      border-color: rgba(124, 156, 255, 0.5);
      color: #ffffff;
    }
    .calendar-day.today {
      border-color: rgba(124, 156, 255, 0.28);
    }

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
      padding: 6px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      vertical-align: middle;
      font-size: 13px;
    }
    tr:last-child td { border-bottom: 0; }
    .selectable-row { cursor: pointer; transition: background 0.18s ease; }
    .selectable-row:hover td { background: rgba(255, 255, 255, 0.03); }
    .selectable-row.selected td { background: rgba(124, 156, 255, 0.14); }

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
      transition: transform 0.14s ease, background-color 0.14s ease, border-color 0.14s ease, box-shadow 0.14s ease;
      box-shadow: 0 6px 18px rgba(0, 0, 0, 0.12);
    }
    .action-btn:hover {
      background: rgba(255, 255, 255, 0.08);
      border-color: rgba(255, 255, 255, 0.18);
      box-shadow: 0 10px 24px rgba(0, 0, 0, 0.18);
      transform: translateY(-1px);
    }
    .action-btn:active {
      transform: translateY(1px) scale(0.985);
      box-shadow: 0 3px 10px rgba(0, 0, 0, 0.18);
    }

    .action-btn.primary {
      background: rgba(124, 156, 255, 0.16);
      border-color: rgba(124, 156, 255, 0.36);
    }
    .action-btn.primary:hover {
      background: rgba(124, 156, 255, 0.24);
      border-color: rgba(124, 156, 255, 0.5);
    }

    .action-btn.danger {
      background: rgba(255, 107, 107, 0.12);
      border-color: rgba(255, 107, 107, 0.24);
    }
    .action-btn.danger:hover {
      background: rgba(255, 107, 107, 0.18);
      border-color: rgba(255, 107, 107, 0.36);
    }
    .action-btn:disabled {
      opacity: 0.45;
      cursor: not-allowed;
      transform: none;
      box-shadow: none;
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
      <a class="nav-button __NAV_DASHBOARD_ACTIVE__" data-tab="dashboard" href="/admin?tab=dashboard"><span class="nav-icon">DB</span><span>대시보드</span></a>
      <a class="nav-button __NAV_PIPELINE_ACTIVE__" data-tab="pipeline" href="/admin?tab=pipeline"><span class="nav-icon">OP</span><span>소싱 운영</span></a>
      <a class="nav-button __NAV_CANDIDATES_ACTIVE__" data-tab="candidates" href="/admin?tab=candidates"><span class="nav-icon">PD</span><span>상품 후보 관리</span></a>
      <a class="nav-button __NAV_TAXONOMY_ACTIVE__" data-tab="taxonomy" href="/admin?tab=taxonomy"><span class="nav-icon">TX</span><span>테마 관리</span></a>
      <a class="nav-button __NAV_RANKING_ACTIVE__" data-tab="ranking" href="/admin?tab=ranking"><span class="nav-icon">RK</span><span>랭킹 관리</span></a>
      <a class="nav-button __NAV_USERS_ACTIVE__" data-tab="users" href="/admin?tab=users"><span class="nav-icon">US</span><span>사용자 및 과금</span></a>
      <a class="nav-button __NAV_LOGS_ACTIVE__" data-tab="logs" href="/admin?tab=logs"><span class="nav-icon">LG</span><span>로그 및 이벤트</span></a>

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
      <section id="dashboard" class="tab-panel __TAB_DASHBOARD_ACTIVE__">
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

      <section id="pipeline" class="tab-panel __TAB_PIPELINE_ACTIVE__">
        <article class="card panel">
          <div class="section-title">
            <div><h2>소싱 운영</h2><p>테마별 키워드 수집 처리량과 배치 흐름</p></div>
            <div class="toolbar-inline">
              <form class="history-toolbar" action="/admin" method="get">
                <input type="hidden" name="tab" value="pipeline" />
                <div class="field">
                  <label for="keyword-history-date">저장 결과 조회 날짜</label>
                  <div class="history-date-wrap">
                    <input class="input" id="keyword-history-date" name="history_date" type="text" inputmode="none" readonly value="__DEFAULT_HISTORY_DATE__" />
                    <button class="action-btn history-picker-btn" id="keyword-history-picker-btn" type="button" aria-label="날짜 선택" aria-expanded="false">📅</button>
                    <div class="history-calendar-popup" id="keyword-history-calendar-popup">
                      <div class="calendar-header">
                        <button class="action-btn calendar-nav-btn" id="keyword-history-prev-month" type="button" aria-label="이전 달">&lt;</button>
                        <div class="calendar-title" id="keyword-history-calendar-title">__HISTORY_CALENDAR_TITLE__</div>
                        <button class="action-btn calendar-nav-btn" id="keyword-history-next-month" type="button" aria-label="다음 달">&gt;</button>
                      </div>
                      <div class="calendar-weekdays">
                        <div class="calendar-weekday">일</div>
                        <div class="calendar-weekday">월</div>
                        <div class="calendar-weekday">화</div>
                        <div class="calendar-weekday">수</div>
                        <div class="calendar-weekday">목</div>
                        <div class="calendar-weekday">금</div>
                        <div class="calendar-weekday">토</div>
                      </div>
                      <div class="calendar-grid" id="keyword-history-calendar-grid">__HISTORY_CALENDAR_GRID__</div>
                    </div>
                  </div>
                </div>
                <button class="action-btn" id="keyword-history-load-btn" type="submit">조회</button>
              </form>
              <form class="history-toolbar" id="keyword-export-form" action="/api/admin/keyword-sourcing/export" method="get">
                <input type="hidden" name="run_id" value="__EXPORT_RUN_ID__" />
                <button class="action-btn" id="keyword-export-btn" type="submit">엑셀 저장</button>
              </form>
              <script>
                (() => {
                  const displayInput = document.getElementById("keyword-history-date");
                  const pickerBtn = document.getElementById("keyword-history-picker-btn");
                  const popup = document.getElementById("keyword-history-calendar-popup");
                  const title = document.getElementById("keyword-history-calendar-title");
                  const grid = document.getElementById("keyword-history-calendar-grid");
                  const prevBtn = document.getElementById("keyword-history-prev-month");
                  const nextBtn = document.getElementById("keyword-history-next-month");
                  if (!displayInput || !pickerBtn || !popup || !title || !grid || !prevBtn || !nextBtn) {
                    return;
                  }

                  function parseDate(value) {
                    if (!value) return null;
                    const parts = value.split("-").map((item) => Number(item));
                    if (parts.length !== 3 || parts.some((item) => Number.isNaN(item))) return null;
                    return new Date(parts[0], parts[1] - 1, parts[2]);
                  }

                  function formatDate(value) {
                    const year = value.getFullYear();
                    const month = String(value.getMonth() + 1).padStart(2, "0");
                    const day = String(value.getDate()).padStart(2, "0");
                    return `${year}-${month}-${day}`;
                  }

                  function sameDate(left, right) {
                    return left.getFullYear() === right.getFullYear()
                      && left.getMonth() === right.getMonth()
                      && left.getDate() === right.getDate();
                  }

                  let selectedDate = parseDate(displayInput.value) || new Date();
                  let viewDate = new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1);

                  function renderCalendar() {
                    title.textContent = `${viewDate.getFullYear()}년 ${viewDate.getMonth() + 1}월`;
                    const firstDay = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1);
                    const startDate = new Date(firstDay);
                    startDate.setDate(firstDay.getDate() - firstDay.getDay());
                    const today = new Date();
                    today.setHours(0, 0, 0, 0);

                    const cells = [];
                    for (let offset = 0; offset < 42; offset += 1) {
                      const cellDate = new Date(startDate);
                      cellDate.setDate(startDate.getDate() + offset);
                      const classes = ["calendar-day"];
                      if (cellDate.getMonth() !== viewDate.getMonth()) classes.push("outside");
                      if (sameDate(cellDate, selectedDate)) classes.push("selected");
                      if (sameDate(cellDate, today)) classes.push("today");
                      cells.push(`
                        <button class="${classes.join(" ")}" type="button" data-date="${formatDate(cellDate)}">${cellDate.getDate()}</button>
                      `);
                    }
                    grid.innerHTML = cells.join("");
                  }

                  function openCalendar() {
                    renderCalendar();
                    popup.classList.add("open");
                    pickerBtn.setAttribute("aria-expanded", "true");
                  }

                  function closeCalendar() {
                    popup.classList.remove("open");
                    pickerBtn.setAttribute("aria-expanded", "false");
                  }

                  pickerBtn.addEventListener("click", (event) => {
                    event.stopPropagation();
                    if (popup.classList.contains("open")) {
                      closeCalendar();
                    } else {
                      openCalendar();
                    }
                  });

                  displayInput.addEventListener("click", (event) => {
                    event.stopPropagation();
                    openCalendar();
                  });

                  prevBtn.addEventListener("click", (event) => {
                    event.stopPropagation();
                    viewDate = new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1);
                    renderCalendar();
                  });

                  nextBtn.addEventListener("click", (event) => {
                    event.stopPropagation();
                    viewDate = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1);
                    renderCalendar();
                  });

                  grid.addEventListener("click", (event) => {
                    const target = event.target.closest("[data-date]");
                    if (!target) return;
                    selectedDate = parseDate(target.dataset.date) || selectedDate;
                    displayInput.value = formatDate(selectedDate);
                    viewDate = new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1);
                    closeCalendar();
                  });

                  document.addEventListener("click", (event) => {
                    if (!popup.classList.contains("open")) return;
                    if (event.target.closest(".history-date-wrap")) return;
                    closeCalendar();
                  });

                  displayInput.value = formatDate(selectedDate);
                  renderCalendar();
                  window.__historyCalendarInitialized = true;
                  window.__openHistoryCalendar = openCalendar;
                  window.__closeHistoryCalendar = closeCalendar;
                })();
              </script>
              <form action="/api/admin/keyword-sourcing/start" method="post" id="keyword-sourcing-form">
                <select class="select" id="keyword-sourcing-theme-id" name="theme_id">
                  <option value="">전체 테마</option>
                  __KEYWORD_THEME_OPTIONS__
                </select>
                <button class="action-btn primary" id="run-keyword-sourcing-btn" type="submit">키워드 소싱</button>
              </form>
              <button class="action-btn danger" id="stop-keyword-sourcing-btn" type="button">소싱 중지</button>
            </div>
          </div>
          <div class="pipeline-stack">
            <div class="bars">
              <div class="bar-row"><span class="bar-label">생활용품</span><div class="bar-track"><div class="bar-fill" style="width:92%"></div></div><span class="bar-value">3,820</span></div>
              <div class="bar-row"><span class="bar-label">책상 꾸미기</span><div class="bar-track"><div class="bar-fill" style="width:78%"></div></div><span class="bar-value">2,940</span></div>
              <div class="bar-row"><span class="bar-label">주방 편의도구</span><div class="bar-track"><div class="bar-fill" style="width:85%"></div></div><span class="bar-value">3,210</span></div>
              <div class="bar-row"><span class="bar-label">반려동물 소품</span><div class="bar-track"><div class="bar-fill" style="width:61%"></div></div><span class="bar-value">2,114</span></div>
              <div class="bar-row"><span class="bar-label">차량 감성용품</span><div class="bar-track"><div class="bar-fill" style="width:56%"></div></div><span class="bar-value">1,902</span></div>
            </div>
            <div class="progress-panel">
              <div class="section-title">
                <div><h2>키워드 소싱 진행 현황</h2></div>
              </div>
              <div class="bar-row">
                <span class="bar-label" id="keyword-progress-label">__KEYWORD_PROGRESS_LABEL__</span>
                <div class="bar-track"><div class="bar-fill" id="keyword-progress-fill" style="width:__KEYWORD_PROGRESS_PERCENT__%"></div></div>
                <span class="bar-value" id="keyword-progress-value">__KEYWORD_PROGRESS_PERCENT__%</span>
              </div>
              <div class="progress-grid">
                <div class="progress-card"><p class="progress-card-label">상태</p><p class="progress-card-value" id="keyword-status-text">__KEYWORD_STATUS_TEXT__</p></div>
                <div class="progress-card"><p class="progress-card-label">처리 CID</p><p class="progress-card-value" id="keyword-processed-count">__KEYWORD_PROCESSED_COUNT__</p></div>
                <div class="progress-card"><p class="progress-card-label">키워드 수</p><p class="progress-card-value" id="keyword-row-count">__KEYWORD_ROW_COUNT__</p></div>
                <div class="progress-card"><p class="progress-card-label">성공 / 실패</p><p class="progress-card-value" id="keyword-success-failure">__KEYWORD_SUCCESS_FAILURE__</p></div>
              </div>
              <div class="progress-meta">
                <div id="keyword-current-theme">현재 테마: __KEYWORD_CURRENT_THEME__</div>
                <div id="keyword-current-cid">현재 CID: __KEYWORD_CURRENT_CID__</div>
                <div id="keyword-current-query">현재 Query: __KEYWORD_CURRENT_QUERY__</div>
                <div id="keyword-last-updated">마지막 갱신: 방금 전</div>
              </div>
              <div class="log-box" id="keyword-log-box">__KEYWORD_LOG_TEXT__</div>
            </div>
            <div class="summary-grid">
              <div class="summary-card">
                <p class="summary-label">Top150 수집</p>
                <p class="summary-value" id="keyword-top150-count">__KEYWORD_TOP150_COUNT__</p>
              </div>
              <div class="summary-card">
                <p class="summary-label">유효키워드 확정</p>
                <p class="summary-value" id="keyword-top100-count">__KEYWORD_TOP100_COUNT__</p>
              </div>
              <div class="summary-card">
                <p class="summary-label">광고 지표 결합</p>
                <p class="summary-value" id="keyword-searchad-count">__KEYWORD_SEARCHAD_COUNT__</p>
                </div>
                <div class="summary-card">
                <p class="summary-label">R2 저장</p>
                <p class="summary-value" id="keyword-r2-status">__KEYWORD_R2_STATUS__</p>
              </div>
                <div class="summary-card">
                <p class="summary-label">고효율 / 중간 / 대형</p>
                <p class="summary-value" id="keyword-group-counts">__KEYWORD_GROUP_COUNTS__</p>
                </div>
            </div>
            <div class="keyword-table-wrap">
              <div class="section-title">
                <div><h2>키워드 파이프라인 결과</h2></div>
              </div>
              <form class="keyword-pagination" action="/admin" method="get">
                <input type="hidden" name="tab" value="pipeline" />
                <input type="hidden" name="history_date" value="__DEFAULT_HISTORY_DATE__" />
                <div class="keyword-pagination-controls">
                  <label for="keyword-page-size">페이지당 표시</label>
                  <select class="select" id="keyword-page-size" name="page_size">
                    <option value="15">15</option>
                    <option value="30">30</option>
                    <option value="50">50</option>
                    <option value="100">100</option>
                  </select>
                </div>
                <div class="keyword-pagination-pages" id="keyword-pagination-pages">__KEYWORD_PAGE_BUTTONS__</div>
                <div class="keyword-pagination-meta" id="keyword-pagination-meta">__KEYWORD_PAGE_META__</div>
              </form>
              <table class="keyword-metrics-table">
                <thead>
                  <tr>
                    <th>테마 세부위치</th>
                    <th>키워드명</th>
                    <th>소속그룹</th>
                    <th>검색량</th>
                    <th>클릭률</th>
                    <th>경쟁강도</th>
                    <th>노출광고수</th>
                    <th>광고효율</th>
                    <th>시즌</th>
                    <th>등록상품수</th>
                    <th>쿠팡불러오기</th>
                  </tr>
                </thead>
                <tbody id="keyword-summary-body">__KEYWORD_SUMMARY_ROWS__</tbody>
              </table>
            </div>
          </div>
        </article>
      </section>

      <section id="candidates" class="tab-panel __TAB_CANDIDATES_ACTIVE__">
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

      <section id="taxonomy" class="tab-panel __TAB_TAXONOMY_ACTIVE__">
        <div class="admin-grid">
          <div class="stack taxonomy-stack">
            <article class="card panel compact-panel">
              <div class="section-title">
                <div>
                  <h2>테마 관리</h2>
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
              </div>
              <div class="form-actions" style="margin-top: 16px;">
                <button class="action-btn primary" id="theme-add-btn" type="button">추가</button>
                <button class="action-btn" id="theme-update-btn" type="button" disabled>수정</button>
                <button class="action-btn danger" id="theme-delete-btn" type="button" disabled>삭제</button>
                <button class="action-btn" id="theme-reset-btn" type="button">입력 초기화</button>
              </div>
            </article>

            <article class="card panel">
              <div class="section-title">
                <div>
                  <h2>테마 테이블</h2>
                </div>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>코드</th>
                    <th>테마명</th>
                  </tr>
                </thead>
                <tbody id="theme-table-body">__THEME_TABLE_ROWS__</tbody>
              </table>
            </article>
          </div>

          <div class="stack">
            <article class="card panel">
              <div class="section-title">
                <div>
                  <h2>CID 관리</h2>
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
                  <select class="select" id="cid-theme">__CID_THEME_OPTIONS__</select>
                </div>
              </div>
              <div class="form-actions" style="margin-top: 16px;">
                <button class="action-btn primary" id="cid-add-btn" type="button">추가</button>
                <button class="action-btn" id="cid-update-btn" type="button" disabled>수정</button>
                <button class="action-btn danger" id="cid-delete-btn" type="button" disabled>삭제</button>
                <button class="action-btn" id="cid-reset-btn" type="button">입력 초기화</button>
              </div>
            </article>

            <article class="card panel">
              <div class="section-title">
                <div>
                  <h2>CID 테이블</h2>
                </div>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>카테고리명</th>
                    <th>CID</th>
                    <th>경로</th>
                    <th>테마</th>
                  </tr>
                </thead>
                <tbody id="cid-table-body">__CID_TABLE_ROWS__</tbody>
              </table>
            </article>
          </div>
        </div>
      </section>

      <section id="ranking" class="tab-panel __TAB_RANKING_ACTIVE__">
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

      <section id="users" class="tab-panel __TAB_USERS_ACTIVE__">
        <article class="card panel">
          <div class="section-title"><div><h2>사용자 및 과금</h2><p>구독 상태와 기기 제한 현황 관리</p></div></div>
          <div class="mini-grid">
            <div class="mini-card"><p class="mini-title">활성 구독</p><p class="mini-copy">Basic, Pro 전체 사용자 합계</p><div class="mini-value">1,274</div></div>
            <div class="mini-card"><p class="mini-title">유예기간 계정</p><p class="mini-copy">결제 복구 대상 계정</p><div class="mini-value">12</div></div>
            <div class="mini-card"><p class="mini-title">기기 슬롯 가득 참</p><p class="mini-copy">2기기 제한에 도달한 사용자</p><div class="mini-value">418</div></div>
          </div>
        </article>
      </section>

      <section id="logs" class="tab-panel __TAB_LOGS_ACTIVE__">
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
  <script id="initial-themes-json" type="application/json">__INITIAL_THEMES_JSON__</script>
  <script id="initial-categories-json" type="application/json">__INITIAL_CATEGORIES_JSON__</script>
  <script id="initial-keyword-rows-json" type="application/json">__INITIAL_KEYWORD_ROWS_JSON__</script>
  <script>
    function readInitialJson(scriptId) {
      const node = document.getElementById(scriptId);
      if (!node) {
        return [];
      }
      try {
        return JSON.parse(node.textContent || "[]");
      } catch (error) {
        console.error(error);
        return [];
      }
    }

    const navButtons = document.querySelectorAll(".nav-button");
    const panels = document.querySelectorAll(".tab-panel");

    function switchAdminTab(tabId) {
      navButtons.forEach((item) => {
        item.classList.toggle("active", item.dataset.tab === tabId);
      });
      panels.forEach((panel) => {
        panel.classList.toggle("active", panel.id === tabId);
      });
    }

    window.switchAdminTab = switchAdminTab;

    navButtons.forEach((button) => {
      button.addEventListener("click", () => {
        switchAdminTab(button.dataset.tab);
      });
    });

    let editingThemeId = null;
    let editingCidId = null;
    let themes = readInitialJson("initial-themes-json");
    let cidItems = readInitialJson("initial-categories-json");
    let initialKeywordRows = readInitialJson("initial-keyword-rows-json");

    const themeCodeInput = document.getElementById("theme-code");
    const themeNameInput = document.getElementById("theme-name");
    const themeAddBtn = document.getElementById("theme-add-btn");
    const themeUpdateBtn = document.getElementById("theme-update-btn");
    const themeDeleteBtn = document.getElementById("theme-delete-btn");
    const themeResetBtn = document.getElementById("theme-reset-btn");
    const themeTableBody = document.getElementById("theme-table-body");

    const cidValueInput = document.getElementById("cid-value");
    const cidNameInput = document.getElementById("cid-name");
    const cidPathInput = document.getElementById("cid-path");
    const cidThemeInput = document.getElementById("cid-theme");
    const cidAddBtn = document.getElementById("cid-add-btn");
    const cidUpdateBtn = document.getElementById("cid-update-btn");
    const cidDeleteBtn = document.getElementById("cid-delete-btn");
    const cidResetBtn = document.getElementById("cid-reset-btn");
    const cidTableBody = document.getElementById("cid-table-body");
    const keywordSourcingForm = document.getElementById("keyword-sourcing-form");
    const keywordSourcingThemeId = document.getElementById("keyword-sourcing-theme-id");
    const runKeywordSourcingBtn = document.getElementById("run-keyword-sourcing-btn");
    const stopKeywordSourcingBtn = document.getElementById("stop-keyword-sourcing-btn");
    const keywordHistoryDateInput = document.getElementById("keyword-history-date");
    const keywordHistoryPickerBtn = document.getElementById("keyword-history-picker-btn");
    const keywordHistoryCalendarPopup = document.getElementById("keyword-history-calendar-popup");
    const keywordHistoryCalendarTitle = document.getElementById("keyword-history-calendar-title");
    const keywordHistoryCalendarGrid = document.getElementById("keyword-history-calendar-grid");
    const keywordHistoryPrevMonthBtn = document.getElementById("keyword-history-prev-month");
    const keywordHistoryNextMonthBtn = document.getElementById("keyword-history-next-month");
    const keywordHistoryLoadBtn = document.getElementById("keyword-history-load-btn");
    const keywordExportBtn = document.getElementById("keyword-export-btn");
    const keywordExportForm = document.getElementById("keyword-export-form");
    const keywordProgressLabel = document.getElementById("keyword-progress-label");
    const keywordProgressFill = document.getElementById("keyword-progress-fill");
    const keywordProgressValue = document.getElementById("keyword-progress-value");
    const keywordStatusText = document.getElementById("keyword-status-text");
    const keywordProcessedCount = document.getElementById("keyword-processed-count");
    const keywordRowCount = document.getElementById("keyword-row-count");
    const keywordSuccessFailure = document.getElementById("keyword-success-failure");
    const keywordCurrentTheme = document.getElementById("keyword-current-theme");
    const keywordCurrentCid = document.getElementById("keyword-current-cid");
    const keywordCurrentQuery = document.getElementById("keyword-current-query");
    const keywordLastUpdated = document.getElementById("keyword-last-updated");
    const keywordLogBox = document.getElementById("keyword-log-box");
    const keywordTop150Count = document.getElementById("keyword-top150-count");
    const keywordTop100Count = document.getElementById("keyword-top100-count");
    const keywordSearchadCount = document.getElementById("keyword-searchad-count");
    const keywordR2Status = document.getElementById("keyword-r2-status");
    const keywordGroupCounts = document.getElementById("keyword-group-counts");
    const keywordPageSize = document.getElementById("keyword-page-size");
    const keywordPaginationPages = document.getElementById("keyword-pagination-pages");
    const keywordPaginationMeta = document.getElementById("keyword-pagination-meta");
    const keywordSummaryBody = document.getElementById("keyword-summary-body");
    let keywordSummaryRows = Array.isArray(initialKeywordRows) ? initialKeywordRows : [];
    let keywordSummaryPageIndex = 0;
    let keywordSummaryPageSize = Number(__INITIAL_KEYWORD_PAGE_SIZE__) || 15;
    let keywordSourcingRunId = null;
    let keywordStatusPoller = null;
    let keywordHistoryMode = false;
    let keywordCalendarViewDate = new Date();
    let keywordDetailLoadedRunId = null;
    let keywordStatusRefreshInFlight = false;
    let keywordStatusLastSuccessAt = Date.now();

    if (keywordHistoryDateInput && !keywordHistoryDateInput.value) {
      keywordHistoryDateInput.value = new Date().toISOString().slice(0, 10);
    }

    function parseDateInput(value) {
      if (!value) {
        return null;
      }
      const parts = value.split("-").map((item) => Number(item));
      if (parts.length !== 3 || parts.some((item) => Number.isNaN(item))) {
        return null;
      }
      return new Date(parts[0], parts[1] - 1, parts[2]);
    }

    function formatDateInput(date) {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, "0");
      const day = String(date.getDate()).padStart(2, "0");
      return `${year}-${month}-${day}`;
    }

    function isSameDate(left, right) {
      return left.getFullYear() === right.getFullYear()
        && left.getMonth() === right.getMonth()
        && left.getDate() === right.getDate();
    }

    function syncCalendarViewToSelectedDate() {
      const selectedDate = parseDateInput(keywordHistoryDateInput.value);
      keywordCalendarViewDate = selectedDate || new Date();
    }

    function renderHistoryCalendar() {
      if (!keywordHistoryCalendarTitle || !keywordHistoryCalendarGrid) {
        return;
      }

      const year = keywordCalendarViewDate.getFullYear();
      const month = keywordCalendarViewDate.getMonth();
      keywordHistoryCalendarTitle.textContent = `${year}년 ${month + 1}월`;

      const firstDay = new Date(year, month, 1);
      const startDate = new Date(firstDay);
      startDate.setDate(firstDay.getDate() - firstDay.getDay());
      const selectedDate = parseDateInput(keywordHistoryDateInput.value);
      const today = new Date();
      today.setHours(0, 0, 0, 0);

      const cells = [];
      for (let offset = 0; offset < 42; offset += 1) {
        const cellDate = new Date(startDate);
        cellDate.setDate(startDate.getDate() + offset);
        const classes = ["calendar-day"];
        if (cellDate.getMonth() !== month) {
          classes.push("outside");
        }
        if (selectedDate && isSameDate(cellDate, selectedDate)) {
          classes.push("selected");
        }
        if (isSameDate(cellDate, today)) {
          classes.push("today");
        }
        cells.push(`
          <button
            class="${classes.join(" ")}"
            type="button"
            data-date="${formatDateInput(cellDate)}"
          >${cellDate.getDate()}</button>
        `);
      }

      keywordHistoryCalendarGrid.innerHTML = cells.join("");
    }

    function openHistoryCalendar() {
      if (!keywordHistoryCalendarPopup) {
        return;
      }
      syncCalendarViewToSelectedDate();
      renderHistoryCalendar();
      keywordHistoryCalendarPopup.classList.add("open");
    }

    function closeHistoryCalendar() {
      if (!keywordHistoryCalendarPopup) {
        return;
      }
      keywordHistoryCalendarPopup.classList.remove("open");
    }

    async function apiFetch(url, options = {}) {
      const controller = new AbortController();
      const timeoutMs = typeof options.timeoutMs === "number" ? options.timeoutMs : 12000;
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
      const { timeoutMs: _timeoutMs, headers: optionHeaders, ...restOptions } = options;
      let response;
      try {
        response = await fetch(url, {
          cache: "no-store",
          headers: {
            "Content-Type": "application/json",
            ...(optionHeaders || {})
          },
          signal: controller.signal,
          ...restOptions
        });
      } catch (error) {
        if (error && error.name === "AbortError") {
          throw new Error("요청 시간이 초과되었습니다.");
        }
        throw error;
      } finally {
        clearTimeout(timeoutId);
      }

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

    function markKeywordStatusHealthy() {
      keywordStatusLastSuccessAt = Date.now();
      if (keywordStatusText && keywordStatusText.textContent === "연결 재시도 중") {
        keywordStatusText.textContent = "running";
      }
      if (keywordLastUpdated) {
        keywordLastUpdated.textContent = "마지막 갱신: 방금 전";
      }
    }

    function getThemeById(themeId) {
      return themes.find((theme) => theme.id === themeId) || null;
    }

    function getCidById(cidId) {
      return cidItems.find((cid) => cid.id === cidId) || null;
    }

    function syncThemeActionButtons() {
      const hasSelection = editingThemeId !== null;
      themeUpdateBtn.disabled = !hasSelection;
      themeDeleteBtn.disabled = !hasSelection;
    }

    function syncCidActionButtons() {
      const hasSelection = editingCidId !== null;
      cidUpdateBtn.disabled = !hasSelection;
      cidDeleteBtn.disabled = !hasSelection;
    }

    function resetThemeForm() {
      editingThemeId = null;
      themeCodeInput.value = "";
      themeNameInput.value = "";
      syncThemeActionButtons();
      renderThemes();
    }

    function resetCidForm() {
      editingCidId = null;
      cidValueInput.value = "";
      cidNameInput.value = "";
      cidPathInput.value = "";
      if (themes.length > 0) {
        cidThemeInput.value = String(themes[0].id);
      }
      syncCidActionButtons();
      renderCids();
    }

    function renderThemeOptions() {
      cidThemeInput.innerHTML = themes
        .map((theme) => `<option value="${theme.id}">${theme.theme_name}</option>`)
        .join("");
    }

    function renderThemes() {
      const sortedThemes = [...themes];

      if (sortedThemes.length === 0) {
        themeTableBody.innerHTML = '<tr><td colspan="2" class="empty-state">등록된 테마가 없습니다.</td></tr>';
        return;
      }

      themeTableBody.innerHTML = sortedThemes
        .map((theme) => `
          <tr class="selectable-row ${editingThemeId === theme.id ? "selected" : ""}" data-theme-id="${theme.id}">
            <td>${theme.theme_code}</td>
            <td>${theme.theme_name}</td>
          </tr>
        `)
        .join("");
    }

    function renderCids() {
      if (cidItems.length === 0) {
        cidTableBody.innerHTML = '<tr><td colspan="4" class="empty-state">등록된 CID가 없습니다.</td></tr>';
        return;
      }

      cidTableBody.innerHTML = cidItems
        .map((item) => {
          const theme = getThemeById(item.themeId);
          return `
            <tr class="selectable-row ${editingCidId === item.id ? "selected" : ""}" data-cid-id="${item.id}">
              <td>${item.name}</td>
              <td>${item.cid}</td>
              <td>${item.path}</td>
              <td>${theme ? theme.theme_name : "-"}</td>
            </tr>
          `;
        })
        .join("");
    }

    function renderTaxonomy() {
      renderThemeOptions();
      renderThemes();
      renderCids();
      if (keywordSourcingThemeId) {
        const currentValue = keywordSourcingThemeId.value;
        const optionHtml = ['<option value="">전체 테마</option>']
          .concat(
            themes.map((theme) => `<option value="${theme.id}">${theme.theme_name}</option>`)
          )
          .join("");
        keywordSourcingThemeId.innerHTML = optionHtml;
        if (currentValue && themes.some((theme) => String(theme.id) === currentValue)) {
          keywordSourcingThemeId.value = currentValue;
        }
      }
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
        themeId: item.theme_id
      }));

      renderTaxonomy();
    }

    function renderKeywordSourcingStatus(state) {
      const progress = Number(state.progress_percent || 0);
      const existingLogs = Array.isArray(state.logs) ? [...state.logs] : ["실행 대기중입니다."];
      keywordProgressLabel.textContent = state.message || "대기중";
      keywordProgressFill.style.width = `${progress}%`;
      keywordProgressValue.textContent = `${progress}%`;
      keywordStatusText.textContent = state.status || "idle";
      keywordProcessedCount.textContent = `${state.processed_categories || 0} / ${state.category_count || 0}`;
      keywordRowCount.textContent = String(state.row_count || 0);
      keywordSuccessFailure.textContent = `${state.success_count || 0} / ${state.failure_count || 0}`;
      keywordCurrentTheme.textContent = `현재 테마: ${state.current_theme_name || "-"}`;
      keywordCurrentCid.textContent = `현재 CID: ${state.current_cid || "-"}`;
      keywordCurrentQuery.textContent = `현재 Query: ${state.current_query || "-"}`;
      keywordLogBox.textContent = existingLogs.join("\n");
      keywordLogBox.scrollTop = keywordLogBox.scrollHeight;
      keywordTop150Count.textContent = String(state.top150_count || 0);
      keywordTop100Count.textContent = String(state.top100_count || 0);
      keywordSearchadCount.textContent = String(state.searchad_count || 0);
      keywordR2Status.textContent = state.r2_parquet_key ? "완료" : "대기";
      const groupCounts = state.group_counts || {};
      keywordGroupCounts.textContent = `${groupCounts["고효율"] || 0} / ${groupCounts["중간성장"] || 0} / ${groupCounts["대형"] || 0}`;
    }

    function buildKeywordSummaryRows(classifiedKeywords) {
      const formatMetricValue = (value) => {
        if (value == null || value === "") {
          return "-";
        }
        const numeric = Number(value);
        if (Number.isFinite(numeric)) {
          return numeric.toLocaleString("ko-KR");
        }
        return String(value);
      };
      const formatPercentValue = (value) => {
        if (value == null || value === "") {
          return "-";
        }
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) {
          return `${String(value)}%`;
        }
        const rounded = Math.round(numeric * 100) / 100;
        const hasFraction = Math.abs(rounded % 1) > 0;
        return `${rounded.toFixed(hasFraction ? 2 : 1).replace(/\.?0+$/, hasFraction ? "" : ".0")}%`;
      };

      const rows = [];
      classifiedKeywords.forEach((row, index) => {
        const keyword = row.keyword || row.query || row.seed_keyword || "-";
        rows.push({
          themeDetail: row.shopping_category_path || row.full_path || row.category_name || row.theme_name || "-",
          keyword,
          group: row.group_name || (row.query || row.seed_keyword ? "이전 저장본" : "-"),
          totalSearches: formatMetricValue(row.monthly_mobile_searches ?? row.total_searches),
          clickRate: formatPercentValue(row.monthly_mobile_ctr),
          competitionLevel: row.competition_level || "-",
          exposureAds: formatMetricValue(row.monthly_exposure_ads),
          adEfficiency: row.ad_efficiency || row.group_name || "-",
          season: row.season_months || "-",
          productCount: formatMetricValue(row.product_count),
          coupangAction: "불러오기",
        });
      });
      return rows;
    }

    function renderKeywordSummaryPageRows(pageRows) {
      if (!pageRows || pageRows.length === 0) {
        keywordSummaryBody.innerHTML = '<tr><td colspan="11" class="empty-state">아직 요약된 키워드가 없습니다.</td></tr>';
        return;
      }
      keywordSummaryBody.innerHTML = pageRows
        .map((row) => `
          <tr>
            <td>${row.themeDetail}</td>
            <td class="keyword-col">${row.keyword}</td>
            <td class="metric-center">${row.group}</td>
            <td class="metric-cell">${row.totalSearches}</td>
            <td class="metric-cell">${row.clickRate}</td>
            <td class="metric-center">${row.competitionLevel}</td>
            <td class="metric-center">${row.exposureAds}</td>
            <td class="metric-center">${row.adEfficiency}</td>
            <td class="metric-center">${row.season}</td>
            <td class="metric-center">${row.productCount}</td>
            <td class="metric-center"><button class="action-btn" type="button" disabled>${row.coupangAction}</button></td>
          </tr>
        `)
        .join("");
    }

    function renderKeywordSummaryRows(classifiedKeywords) {
      keywordSummaryRows = buildKeywordSummaryRows(classifiedKeywords);
      renderKeywordSummaryPageRows(keywordSummaryRows);
    }

    async function loadKeywordSourcingDetail(runId) {
      const params = new URLSearchParams();
      if (runId) {
        params.set("run_id", runId);
      }
      params.set("_ts", String(Date.now()));
      const state = await apiFetch(`/api/admin/keyword-sourcing/detail?${params.toString()}`);
      if (state.run_id) {
        keywordSourcingRunId = state.run_id;
      }
      keywordDetailLoadedRunId = state.run_id || runId || null;
      const classifiedKeywords = Array.isArray(state.classified_keywords) ? state.classified_keywords : [];
      const previewRows = Array.isArray(state.preview_rows) ? state.preview_rows : [];
      const fallbackRows = classifiedKeywords.length > 0 ? classifiedKeywords : previewRows;
      renderKeywordSummaryRows(fallbackRows);
    }

    async function refreshKeywordSourcingStatus() {
      if (keywordHistoryMode) {
        return;
      }
      const params = new URLSearchParams();
      if (keywordSourcingRunId) {
        params.set("run_id", keywordSourcingRunId);
      }
      params.set("_ts", String(Date.now()));
      const query = `?${params.toString()}`;
      const state = await apiFetch(`/api/admin/keyword-sourcing/status${query}`);
      if (keywordHistoryMode) {
        return;
      }
      if (state.run_id) {
        keywordSourcingRunId = state.run_id;
      }
      syncKeywordExportForm();
      markKeywordStatusHealthy();
      renderKeywordSourcingStatus(state);
      if (state.status === "running") {
        keywordDetailLoadedRunId = null;
      } else if (state.run_id && keywordDetailLoadedRunId !== state.run_id) {
        try {
          await loadKeywordSourcingDetail(state.run_id);
        } catch (error) {
          console.error(error);
        }
      }

      if (state.status === "running") {
        runKeywordSourcingBtn.disabled = true;
        runKeywordSourcingBtn.textContent = "수집 중...";
        if (stopKeywordSourcingBtn) {
          stopKeywordSourcingBtn.disabled = false;
        }
      } else {
        runKeywordSourcingBtn.disabled = false;
        runKeywordSourcingBtn.textContent = "키워드 소싱";
        if (stopKeywordSourcingBtn) {
          stopKeywordSourcingBtn.disabled = true;
        }
      }
    }

    function startKeywordStatusPolling() {
      if (keywordStatusPoller) {
        return;
      }
      keywordStatusPoller = setInterval(async () => {
        if (keywordHistoryMode) {
          return;
        }
        if (keywordStatusRefreshInFlight) {
          return;
        }
        keywordStatusRefreshInFlight = true;
        try {
          await refreshKeywordSourcingStatus();
        } catch (error) {
          if (keywordProgressLabel) {
            keywordProgressLabel.textContent = "진행 상태 재연결 중...";
          }
          if (keywordStatusText) {
            keywordStatusText.textContent = "연결 재시도 중";
          }
          console.error(error);
        } finally {
          keywordStatusRefreshInFlight = false;
        }
      }, 2000);
    }

    function stopKeywordStatusPolling() {
      if (keywordStatusPoller) {
        clearInterval(keywordStatusPoller);
        keywordStatusPoller = null;
      }
    }

    function startKeywordLastUpdatedTicker() {
      setInterval(() => {
        if (!keywordLastUpdated) {
          return;
        }
        const diffSeconds = Math.max(0, Math.floor((Date.now() - keywordStatusLastSuccessAt) / 1000));
        if (diffSeconds < 5) {
          keywordLastUpdated.textContent = "마지막 갱신: 방금 전";
          return;
        }
        keywordLastUpdated.textContent = `마지막 갱신: ${diffSeconds}초 전`;
      }, 1000);
    }

    async function loadKeywordSourcingHistoryByDate() {
      const selectedDate = keywordHistoryDateInput.value;
      if (!selectedDate) {
        alert("조회할 날짜를 먼저 선택해 주세요.");
        return;
      }

      keywordHistoryMode = true;
      stopKeywordStatusPolling();
      const state = await apiFetch(`/api/admin/keyword-sourcing/history?date_value=${encodeURIComponent(selectedDate)}&_ts=${Date.now()}`);
      if (state.run_id) {
        keywordSourcingRunId = state.run_id;
      }
      syncKeywordExportForm();
      markKeywordStatusHealthy();
      renderKeywordSourcingStatus(state);
    }

    function syncKeywordExportForm() {
      if (!keywordExportForm) {
        return;
      }
      const runIdInput = keywordExportForm.querySelector('input[name="run_id"]');
      if (runIdInput) {
        runIdInput.value = keywordSourcingRunId || "";
      }
    }
    syncKeywordExportForm();

    function editTheme(themeId) {
      const theme = getThemeById(themeId);
      if (!theme) return;

      editingThemeId = themeId;
      themeCodeInput.value = theme.theme_code;
      themeNameInput.value = theme.theme_name;
      syncThemeActionButtons();
      renderThemes();
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
      const item = getCidById(cidId);
      if (!item) return;

      editingCidId = cidId;
      cidValueInput.value = item.cid;
      cidNameInput.value = item.name;
      cidPathInput.value = item.path;
      cidThemeInput.value = item.themeId ? String(item.themeId) : "";
      syncCidActionButtons();
      renderCids();
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

    themeTableBody.addEventListener("click", (event) => {
      const row = event.target.closest("[data-theme-id]");
      if (!row) return;
      editTheme(Number(row.dataset.themeId));
    });

    cidTableBody.addEventListener("click", (event) => {
      const row = event.target.closest("[data-cid-id]");
      if (!row) return;
      editCid(Number(row.dataset.cidId));
    });

    themeAddBtn.addEventListener("click", async () => {
      const code = themeCodeInput.value.trim();
      const name = themeNameInput.value.trim();

      if (!code || !name) {
        return;
      }

      if (!confirm("이 테마를 추가하시겠습니까?")) {
        return;
      }

      const payload = {
        theme_code: code,
        theme_name: name
      };

      await apiFetch("/api/admin/themes", {
        method: "POST",
        body: JSON.stringify(payload)
      });

      resetThemeForm();
      await loadTaxonomy();
    });

    themeUpdateBtn.addEventListener("click", async () => {
      if (!editingThemeId) return;

      const code = themeCodeInput.value.trim();
      const name = themeNameInput.value.trim();

      if (!code || !name) {
        return;
      }

      if (!confirm("선택한 테마를 수정하시겠습니까?")) {
        return;
      }

      await apiFetch(`/api/admin/themes/${editingThemeId}`, {
        method: "PUT",
        body: JSON.stringify({
          theme_code: code,
          theme_name: name
        })
      });

      resetThemeForm();
      await loadTaxonomy();
    });

    themeDeleteBtn.addEventListener("click", async () => {
      if (!editingThemeId) return;
      if (!confirm("선택한 테마를 삭제하시겠습니까? 연결된 CID의 테마명은 비워집니다.")) {
        return;
      }
      await deleteTheme(editingThemeId);
    });

    themeResetBtn.addEventListener("click", resetThemeForm);

    cidAddBtn.addEventListener("click", async () => {
      const cid = cidValueInput.value.trim();
      const name = cidNameInput.value.trim();
      const path = cidPathInput.value.trim();
      const themeId = cidThemeInput.value ? Number(cidThemeInput.value) : null;

      if (!cid || !name || !path) {
        return;
      }

      if (!confirm("이 CID를 추가하시겠습니까?")) {
        return;
      }

      const payload = {
        cid,
        category_name: name,
        full_path: path,
        theme_id: themeId
      };

      await apiFetch("/api/admin/categories", {
        method: "POST",
        body: JSON.stringify(payload)
      });

      resetCidForm();
      await loadTaxonomy();
    });

    cidUpdateBtn.addEventListener("click", async () => {
      if (!editingCidId) return;

      const cid = cidValueInput.value.trim();
      const name = cidNameInput.value.trim();
      const path = cidPathInput.value.trim();
      const themeId = cidThemeInput.value ? Number(cidThemeInput.value) : null;

      if (!cid || !name || !path) {
        return;
      }

      if (!confirm("선택한 CID를 수정하시겠습니까?")) {
        return;
      }

      await apiFetch(`/api/admin/categories/${editingCidId}`, {
        method: "PUT",
        body: JSON.stringify({
          cid,
          category_name: name,
          full_path: path,
          theme_id: themeId
        })
      });

      resetCidForm();
      await loadTaxonomy();
    });

    cidDeleteBtn.addEventListener("click", async () => {
      if (!editingCidId) return;
      if (!confirm("선택한 CID를 삭제하시겠습니까? 되돌릴 수 없습니다.")) {
        return;
      }
      await deleteCid(editingCidId);
    });

    cidResetBtn.addEventListener("click", resetCidForm);

    if (keywordSourcingForm) {
      keywordSourcingForm.addEventListener("submit", async (event) => {
        if (!confirm("전체 테마 기준으로 CID당 30건씩 키워드 소싱을 실행하시겠습니까?")) {
          event.preventDefault();
          return;
        }

        try {
          event.preventDefault();
          keywordHistoryMode = false;
          keywordDetailLoadedRunId = null;
          const payload = {};
          const selectedThemeId = keywordSourcingThemeId ? keywordSourcingThemeId.value : "";
          if (selectedThemeId) {
            payload.theme_id = Number(selectedThemeId);
          }
          const result = await apiFetch("/api/admin/keyword-sourcing/test", {
            method: "POST",
            body: JSON.stringify(payload)
          });
          keywordSourcingRunId = result.run_id || keywordSourcingRunId;
          startKeywordStatusPolling();
          await refreshKeywordSourcingStatus();
        } catch (error) {
          alert(`키워드 소싱 실패: ${error.message}`);
          keywordSourcingForm.submit();
        }
      });
    }

    if (stopKeywordSourcingBtn) {
      stopKeywordSourcingBtn.disabled = true;
      stopKeywordSourcingBtn.addEventListener("click", async () => {
        if (!confirm("현재 진행 중인 키워드 소싱을 중지하시겠습니까?")) {
          return;
        }

        try {
          const state = await apiFetch("/api/admin/keyword-sourcing/stop", {
            method: "POST"
          });
          renderKeywordSourcingStatus(state);
          if (state.run_id) {
            await loadKeywordSourcingDetail(state.run_id);
          }
        } catch (error) {
          alert(`키워드 소싱 중지 실패: ${error.message}`);
        }
      });
    }

    if (keywordHistoryLoadBtn && keywordHistoryLoadBtn.type === "button") {
      keywordHistoryLoadBtn.addEventListener("click", async () => {
        try {
          await loadKeywordSourcingHistoryByDate();
        } catch (error) {
          alert(`저장된 결과 조회 실패: ${error.message}`);
        }
      });
    }

    if (keywordExportForm) {
      keywordExportForm.addEventListener("submit", () => {
        syncKeywordExportForm();
      });
    }

    if (keywordPageSize) {
      keywordPageSize.value = String(keywordSummaryPageSize);
      keywordPageSize.addEventListener("change", () => {
        if (keywordPageSize.form) {
          keywordPageSize.form.submit();
        }
      });
    }

    if (!window.__historyCalendarInitialized && keywordHistoryPickerBtn) {
      keywordHistoryPickerBtn.addEventListener("click", (event) => {
        event.stopPropagation();
        if (keywordHistoryCalendarPopup && keywordHistoryCalendarPopup.classList.contains("open")) {
          closeHistoryCalendar();
          return;
        }
        openHistoryCalendar();
      });
    }

    if (!window.__historyCalendarInitialized && keywordHistoryDateInput) {
      keywordHistoryDateInput.addEventListener("click", (event) => {
        event.stopPropagation();
        openHistoryCalendar();
      });
    }

    if (!window.__historyCalendarInitialized && keywordHistoryPrevMonthBtn) {
      keywordHistoryPrevMonthBtn.addEventListener("click", (event) => {
        event.stopPropagation();
        keywordCalendarViewDate = new Date(
          keywordCalendarViewDate.getFullYear(),
          keywordCalendarViewDate.getMonth() - 1,
          1,
        );
        renderHistoryCalendar();
      });
    }

    if (!window.__historyCalendarInitialized && keywordHistoryNextMonthBtn) {
      keywordHistoryNextMonthBtn.addEventListener("click", (event) => {
        event.stopPropagation();
        keywordCalendarViewDate = new Date(
          keywordCalendarViewDate.getFullYear(),
          keywordCalendarViewDate.getMonth() + 1,
          1,
        );
        renderHistoryCalendar();
      });
    }

    if (!window.__historyCalendarInitialized && keywordHistoryCalendarGrid) {
      keywordHistoryCalendarGrid.addEventListener("click", (event) => {
        const dayButton = event.target.closest("[data-date]");
        if (!dayButton) {
          return;
        }
        keywordHistoryDateInput.value = dayButton.dataset.date || keywordHistoryDateInput.value;
        closeHistoryCalendar();
      });
    }

    if (!window.__historyCalendarInitialized) {
      document.addEventListener("click", (event) => {
        if (!keywordHistoryCalendarPopup || !keywordHistoryCalendarPopup.classList.contains("open")) {
          return;
        }
        if (event.target.closest(".history-date-wrap")) {
          return;
        }
        closeHistoryCalendar();
      });
    }

    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible" && !keywordHistoryMode) {
        refreshKeywordSourcingStatus().catch((error) => {
          console.error(error);
        });
        startKeywordStatusPolling();
      }
    });

    window.addEventListener("focus", () => {
      if (!keywordHistoryMode) {
        refreshKeywordSourcingStatus().catch((error) => {
          console.error(error);
        });
        startKeywordStatusPolling();
      }
    });

    loadTaxonomy().catch((error) => {
      themeTableBody.innerHTML = `<tr><td colspan="2" class="empty-state">${error.message}</td></tr>`;
      cidTableBody.innerHTML = `<tr><td colspan="4" class="empty-state">${error.message}</td></tr>`;
    });
    renderKeywordSummaryRows(keywordSummaryRows);
    refreshKeywordSourcingStatus().catch((error) => {
      if (keywordLogBox) {
        keywordLogBox.textContent = `진행 상태를 불러오지 못했습니다: ${error.message}`;
      }
      console.error(error);
    });
    loadKeywordSourcingDetail(keywordSourcingRunId).catch((error) => {
      console.error(error);
    });
    startKeywordLastUpdatedTicker();
    if (keywordStatusText && keywordStatusText.textContent === "running") {
      startKeywordStatusPolling();
    }
    startKeywordStatusPolling();
  </script>
</body>
</html>
"""


@router.get("/admin", response_class=HTMLResponse)
async def admin_console(
    tab: str = "dashboard",
    history_date: Optional[date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=15, ge=1, le=100),
) -> HTMLResponse:
    history_status: Optional[Dict[str, Any]] = None
    if tab == "pipeline" and history_date is not None:
        history_status = KeywordSourcingService.load_saved_result_for_date(
            get_settings(),
            target_date=history_date,
        )
    return HTMLResponse(
        content=render_admin_html(
            tab,
            history_status=history_status,
            history_date=history_date,
            page=page,
            page_size=page_size,
        )
    )


VALID_ADMIN_TABS = {
    "dashboard",
    "pipeline",
    "candidates",
    "taxonomy",
    "ranking",
    "users",
    "logs",
}


def render_admin_html(
    active_tab: str,
    *,
    history_status: Optional[Dict[str, Any]] = None,
    history_date: Optional[date] = None,
    page: int = 1,
    page_size: int = 15,
) -> str:
    selected_tab = active_tab if active_tab in VALID_ADMIN_TABS else "dashboard"
    html = ADMIN_HTML
    taxonomy_data = load_admin_taxonomy_data()
    keyword_status = load_keyword_status_data()
    if history_status is not None:
        keyword_status.update(history_status)
        keyword_status["log_text"] = "\n".join(history_status.get("logs") or ["실행 대기중입니다."])
    default_history_date = history_date or date.today()
    history_title, history_grid = build_history_calendar_markup(default_history_date)

    for tab in VALID_ADMIN_TABS:
        nav_token = f"__NAV_{tab.upper()}_ACTIVE__"
        panel_token = f"__TAB_{tab.upper()}_ACTIVE__"
        is_active = tab == selected_tab
        html = html.replace(nav_token, "active" if is_active else "")
        html = html.replace(panel_token, "active" if is_active else "")

    html = html.replace("__THEME_TABLE_ROWS__", build_theme_rows_html(taxonomy_data["themes"]))
    html = html.replace("__CID_THEME_OPTIONS__", build_theme_options_html(taxonomy_data["themes"]))
    html = html.replace("__CID_TABLE_ROWS__", build_category_rows_html(taxonomy_data["categories"]))
    html = html.replace(
        "__INITIAL_THEMES_JSON__",
        json.dumps(taxonomy_data["themes"], ensure_ascii=False),
    )
    html = html.replace(
        "__INITIAL_CATEGORIES_JSON__",
        json.dumps(taxonomy_data["categories"], ensure_ascii=False),
    )
    paginated_keyword_data = build_keyword_summary_page_data(
        keyword_status,
        page=page,
        page_size=page_size,
        history_date=history_date,
    )
    html = html.replace(
        "__INITIAL_KEYWORD_ROWS_JSON__",
        json.dumps(paginated_keyword_data["rows"], ensure_ascii=False),
    )
    html = html.replace("__INITIAL_KEYWORD_PAGE_SIZE__", str(page_size))
    html = html.replace("__KEYWORD_PROGRESS_LABEL__", escape(str(keyword_status["message"])))
    html = html.replace("__KEYWORD_PROGRESS_PERCENT__", str(keyword_status["progress_percent"]))
    html = html.replace("__KEYWORD_STATUS_TEXT__", escape(str(keyword_status["status"])))
    html = html.replace(
        "__KEYWORD_PROCESSED_COUNT__",
        escape(f'{keyword_status["processed_categories"]} / {keyword_status["category_count"]}'),
    )
    html = html.replace("__KEYWORD_ROW_COUNT__", escape(str(keyword_status["row_count"])))
    html = html.replace(
        "__KEYWORD_SUCCESS_FAILURE__",
        escape(f'{keyword_status["success_count"]} / {keyword_status["failure_count"]}'),
    )
    html = html.replace("__KEYWORD_CURRENT_THEME__", escape(str(keyword_status["current_theme_name"] or "-")))
    html = html.replace("__KEYWORD_CURRENT_CID__", escape(str(keyword_status["current_cid"] or "-")))
    html = html.replace("__KEYWORD_CURRENT_QUERY__", escape(str(keyword_status["current_query"] or "-")))
    html = html.replace("__KEYWORD_LOG_TEXT__", escape(keyword_status["log_text"]))
    html = html.replace("__KEYWORD_TOP150_COUNT__", escape(str(keyword_status["top150_count"])))
    html = html.replace("__KEYWORD_TOP100_COUNT__", escape(str(keyword_status["top100_count"])))
    html = html.replace("__KEYWORD_SEARCHAD_COUNT__", escape(str(keyword_status["searchad_count"])))
    html = html.replace("__KEYWORD_R2_STATUS__", "완료" if keyword_status["r2_parquet_key"] else "대기")
    html = html.replace(
        "__KEYWORD_GROUP_COUNTS__",
        escape(
            f'{keyword_status["group_counts"].get("고효율", 0)} / '
            f'{keyword_status["group_counts"].get("중간성장", 0)} / '
            f'{keyword_status["group_counts"].get("대형", 0)}'
        ),
    )
    html = html.replace("__KEYWORD_SUMMARY_ROWS__", build_keyword_summary_rows_html(keyword_status, page=page, page_size=page_size))
    html = html.replace("__KEYWORD_PAGE_BUTTONS__", build_keyword_summary_page_buttons_html(paginated_keyword_data))
    html = html.replace("__KEYWORD_PAGE_META__", paginated_keyword_data["meta_text"])
    html = html.replace("__KEYWORD_THEME_OPTIONS__", build_theme_options_html(taxonomy_data["themes"]))
    html = html.replace("__DEFAULT_HISTORY_DATE__", default_history_date.isoformat())
    html = html.replace("__HISTORY_CALENDAR_TITLE__", escape(history_title))
    html = html.replace("__HISTORY_CALENDAR_GRID__", history_grid)
    return html


def load_admin_taxonomy_data() -> Dict[str, List[Dict[str, Any]]]:
    connection = get_mysql_connection()
    try:
        ensure_tables(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    t.id,
                    t.theme_code,
                    t.theme_name,
                    COUNT(tcm.id) AS cid_count
                FROM themes t
                LEFT JOIN theme_category_maps tcm
                    ON t.id = tcm.theme_id
                GROUP BY t.id, t.theme_code, t.theme_name
                ORDER BY t.id ASC
                """
            )
            themes = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    nc.id,
                    nc.cid,
                    nc.category_name,
                    nc.full_path,
                    t.id AS theme_id,
                    t.theme_name
                FROM naver_categories nc
                LEFT JOIN theme_category_maps tcm
                    ON nc.id = tcm.category_id
                LEFT JOIN themes t
                    ON tcm.theme_id = t.id
                ORDER BY nc.id ASC
                """
            )
            categories = cursor.fetchall()

        return {"themes": themes, "categories": categories}
    finally:
        connection.close()


def load_keyword_status_data() -> Dict[str, Any]:
    from app.services.keyword_sourcing import KeywordSourcingService

    state = KeywordSourcingService.get_status()
    logs = state.get("logs") or ["실행 대기중입니다."]

    return {
        "message": state.get("message") or "대기중",
        "progress_percent": int(state.get("progress_percent") or 0),
        "status": state.get("status") or "idle",
        "processed_categories": int(state.get("processed_categories") or 0),
        "category_count": int(state.get("category_count") or 0),
        "row_count": int(state.get("row_count") or 0),
        "success_count": int(state.get("success_count") or 0),
        "failure_count": int(state.get("failure_count") or 0),
        "current_theme_name": state.get("current_theme_name"),
        "current_cid": state.get("current_cid"),
        "current_query": state.get("current_query"),
        "log_text": "\n".join(logs),
        "r2_json_key": state.get("r2_json_key"),
        "r2_parquet_key": state.get("r2_parquet_key"),
        "valid_keywords": state.get("valid_keywords") or [],
        "noise_keywords": state.get("noise_keywords") or [],
        "top150_count": int(state.get("top150_count") or 0),
        "top100_count": int(state.get("top100_count") or 0),
        "searchad_count": int(state.get("searchad_count") or 0),
        "group_counts": state.get("group_counts") or {},
        "classified_keywords": state.get("classified_keywords") or [],
    }


def build_history_calendar_markup(selected_date: date) -> tuple[str, str]:
    view_month = date(selected_date.year, selected_date.month, 1)
    first_weekday_offset = (view_month.weekday() + 1) % 7
    start_date = view_month - timedelta(days=first_weekday_offset)
    today = date.today()

    cells: List[str] = []
    for day_offset in range(42):
        cell_date = start_date + timedelta(days=day_offset)
        classes = ["calendar-day"]
        if cell_date.month != view_month.month:
            classes.append("outside")
        if cell_date == selected_date:
            classes.append("selected")
        if cell_date == today:
            classes.append("today")
        cells.append(
            (
                f'<button class="{" ".join(classes)}" type="button" '
                f'data-date="{cell_date.isoformat()}">{cell_date.day}</button>'
            )
        )

    return f"{view_month.year}년 {view_month.month}월", "".join(cells)


def build_theme_options_html(themes: List[Dict[str, Any]]) -> str:
    return "".join(
        f'<option value="{theme["id"]}">{escape(str(theme["theme_name"]))}</option>'
        for theme in themes
    )


def build_theme_rows_html(themes: List[Dict[str, Any]]) -> str:
    if not themes:
        return '<tr><td colspan="2" class="empty-state">등록된 테마가 없습니다.</td></tr>'

    return "".join(
        (
            f'<tr class="selectable-row" data-theme-id="{theme["id"]}">'
            f"<td>{escape(str(theme['theme_code']))}</td>"
            f"<td>{escape(str(theme['theme_name']))}</td>"
            "</tr>"
        )
        for theme in themes
    )


def build_category_rows_html(categories: List[Dict[str, Any]]) -> str:
    if not categories:
        return '<tr><td colspan="4" class="empty-state">등록된 CID가 없습니다.</td></tr>'

    return "".join(
        (
            f'<tr class="selectable-row" data-cid-id="{category["id"]}">'
            f"<td>{escape(str(category['category_name']))}</td>"
            f"<td>{escape(str(category['cid']))}</td>"
            f"<td>{escape(str(category['full_path']))}</td>"
            f"<td>{escape(str(category.get('theme_name') or '-'))}</td>"
            "</tr>"
        )
        for category in categories
    )


def build_keyword_summary_rows_html(
    keyword_status: Dict[str, Any],
    *,
    page: int = 1,
    page_size: int = 15,
) -> str:
    page_rows = build_keyword_summary_page_data(
        keyword_status,
        page=page,
        page_size=page_size,
        history_date=None,
    )["rows"]
    rows: List[str] = []
    for row in page_rows:
        rows.append(
            (
                "<tr>"
                f"<td>{escape(str(row['themeDetail']))}</td>"
                f"<td class=\"keyword-col\">{escape(str(row['keyword']))}</td>"
                f"<td class=\"metric-center\">{escape(str(row['group']))}</td>"
                f"<td class=\"metric-cell\">{escape(str(row['totalSearches']))}</td>"
                f"<td class=\"metric-cell\">{escape(str(row['clickRate']))}</td>"
                f"<td class=\"metric-center\">{escape(str(row['competitionLevel']))}</td>"
                f"<td class=\"metric-center\">{escape(str(row['exposureAds']))}</td>"
                f"<td class=\"metric-center\">{escape(str(row['adEfficiency']))}</td>"
                f"<td class=\"metric-center\">{escape(str(row['season']))}</td>"
                f"<td class=\"metric-center\">{escape(str(row['productCount']))}</td>"
                "<td class=\"metric-center\"><button class=\"action-btn\" type=\"button\" disabled>불러오기</button></td>"
                "</tr>"
            )
        )

    if not rows:
        return '<tr><td colspan="11" class="empty-state">아직 요약된 키워드가 없습니다.</td></tr>'

    return "".join(rows)


def build_keyword_summary_page_buttons_html(page_data: Dict[str, Any]) -> str:
    total_pages = int(page_data.get("total_pages") or 0)
    current_page = int(page_data.get("page") or 1)
    if total_pages == 0:
        return ""

    tabs: List[str] = []
    prev_page = max(1, current_page - 1)
    next_page = min(total_pages, current_page + 1)
    tabs.append(
        f'<button class="action-btn" type="submit" name="page" value="{prev_page}" {"disabled" if current_page == 1 else ""}>이전</button>'
    )
    start_page = max(1, current_page - 2)
    end_page = min(total_pages, start_page + 4)
    for page_number in range(start_page, end_page + 1):
        classes = "action-btn primary" if page_number == current_page else "action-btn"
        tabs.append(f'<button class="{classes}" type="submit" name="page" value="{page_number}">{page_number}</button>')
    tabs.append(
        f'<button class="action-btn" type="submit" name="page" value="{next_page}" {"disabled" if current_page >= total_pages else ""}>다음</button>'
    )
    return "".join(tabs)


def build_keyword_summary_page_data(
    keyword_status: Dict[str, Any],
    *,
    page: int,
    page_size: int,
    history_date: Optional[date],
) -> Dict[str, Any]:
    all_rows = build_keyword_summary_rows_data(keyword_status)
    total_rows = len(all_rows)
    if total_rows == 0:
        return {
            "rows": [],
            "page": 1,
            "page_size": page_size,
            "total_rows": 0,
            "total_pages": 0,
            "meta_text": "총 0건",
        }
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    current_page = min(max(1, page), total_pages)
    start_index = (current_page - 1) * page_size
    end_index = min(start_index + page_size, total_rows)
    return {
        "rows": all_rows[start_index:end_index],
        "page": current_page,
        "page_size": page_size,
        "total_rows": total_rows,
        "total_pages": total_pages,
        "meta_text": f"총 {total_rows:,}건 중 {start_index + 1}-{end_index} 표시",
    }


def build_keyword_summary_rows_data(keyword_status: Dict[str, Any]) -> List[Dict[str, Any]]:
    classified_keywords = keyword_status.get("classified_keywords") or []
    if not classified_keywords:
        classified_keywords = keyword_status.get("preview_rows") or []

    rows: List[Dict[str, Any]] = []
    for keyword_row in classified_keywords:
        keyword_text = (
            keyword_row.get("keyword")
            or keyword_row.get("query")
            or keyword_row.get("seed_keyword")
            or ""
        )
        total_searches = keyword_row.get("monthly_mobile_searches")
        if total_searches is None:
            total_searches = keyword_row.get("total_searches")
        monthly_mobile_ctr = keyword_row.get("monthly_mobile_ctr")
        competition_level = str(keyword_row.get("competition_level") or "-")
        ad_efficiency = str(keyword_row.get("ad_efficiency") or keyword_row.get("group_name") or "-")
        click_rate_text = format_percent_value(monthly_mobile_ctr)
        theme_detail = (
            keyword_row.get("shopping_category_path")
            or keyword_row.get("full_path")
            or keyword_row.get("category_name")
            or keyword_row.get("theme_name")
            or "-"
        )
        product_count = keyword_row.get("product_count")
        exposure_ads = keyword_row.get("monthly_exposure_ads")
        season_months = keyword_row.get("season_months") or "-"
        rows.append(
            {
                "themeDetail": str(theme_detail),
                "keyword": str(keyword_text),
                "group": str(
                    keyword_row.get("group_name")
                    or ("이전 저장본" if keyword_row.get("query") or keyword_row.get("seed_keyword") else "-")
                ),
                "totalSearches": format_metric_value(total_searches),
                "clickRate": click_rate_text,
                "competitionLevel": competition_level,
                "exposureAds": format_metric_value(exposure_ads),
                "adEfficiency": ad_efficiency,
                "season": str(season_months),
                "productCount": format_metric_value(product_count),
            }
        )
    return rows


def format_metric_value(value: Any) -> str:
    if value in (None, ""):
        return "-"
    try:
        normalized = str(value).replace(",", "").strip()
        if not normalized:
            return "-"
        return f"{int(float(normalized)):,}"
    except (TypeError, ValueError):
        return str(value)


def format_percent_value(value: Any) -> str:
    if value in (None, ""):
        return "-"
    try:
        numeric = float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return f"{value}%"
    rounded = round(numeric, 2)
    if rounded.is_integer():
        return f"{rounded:.1f}%"
    formatted = f"{rounded:.2f}".rstrip("0").rstrip(".")
    return f"{formatted}%"
