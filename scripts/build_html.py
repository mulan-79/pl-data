#!/usr/bin/env python3
"""새 디자인 HTML 생성 스크립트"""
import re, os

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(base, 'dart_financial_website.html')
backup = os.path.join(base, 'scripts', '_industry_data.js')

with open(src, encoding='utf-8') as f:
    old = f.read()

# Extract INDUSTRY_DATA (if present in current file, save backup)
idx_start = old.find('const INDUSTRY_DATA =')
if idx_start != -1:
    idx_end = old.find(';\n', idx_start) + 2
    industry_line = old[idx_start:idx_end].strip()
    # Save backup for future runs
    with open(backup, 'w', encoding='utf-8') as f:
        f.write(industry_line)
    print(f'INDUSTRY_DATA 추출 완료 ({len(industry_line)//1024}KB)')
elif os.path.exists(backup):
    with open(backup, encoding='utf-8') as f:
        industry_line = f.read().strip()
    print(f'INDUSTRY_DATA 백업에서 로드 ({len(industry_line)//1024}KB)')
else:
    raise RuntimeError('INDUSTRY_DATA를 찾을 수 없습니다. dart_financial_website.html에 데이터가 있어야 합니다.')

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>업종별 재무현황</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:'Noto Sans KR','Apple SD Gothic Neo',sans-serif;background:#f8fafc;color:#0f172a;min-height:100vh;font-size:13px;}
::-webkit-scrollbar{width:6px;height:6px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:99px;}
::-webkit-scrollbar-thumb:hover{background:#94a3b8;}
.page-wrap{max-width:1400px;margin:0 auto;padding:20px 24px;}
/* Header */
.topbar{background:#1e3a8a;padding:0 24px;}
.topbar-inner{max-width:1400px;margin:0 auto;height:56px;display:flex;align-items:center;justify-content:space-between;}
.brand{display:flex;align-items:center;gap:12px;}
.brand-icon-box{width:32px;height:32px;background:rgba(255,255,255,0.15);border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.brand-title{color:white;font-weight:700;font-size:16px;letter-spacing:-0.02em;}
.brand-sub{color:rgba(255,255,255,0.6);font-size:11px;margin-top:1px;}
.badge-ofs{display:inline-block;padding:1px 7px;border-radius:99px;background:rgba(255,255,255,0.2);color:rgba(255,255,255,0.9);font-size:10px;font-weight:700;letter-spacing:0.3px;vertical-align:middle;margin-left:6px;}
.header-select{height:34px;padding:0 28px 0 10px;background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);color:white;border-radius:8px;font-size:12px;font-family:inherit;outline:none;cursor:pointer;appearance:none;}
.header-select option{background:#1e3a8a;color:white;}
/* Filter bar */
.filter-bar{background:white;border:1px solid #e2e8f0;border-radius:12px;padding:16px 20px;margin-bottom:20px;display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap;}
.filter-label{display:block;font-size:11px;font-weight:600;color:#64748b;margin-bottom:6px;letter-spacing:0.04em;}
.ctrl-wrap{position:relative;}
.ctrl-select,.ctrl-input{border:1px solid #e2e8f0;border-radius:8px;padding:0 12px;height:38px;font-family:inherit;font-size:13px;color:#334155;background:white;outline:none;transition:border-color .15s,box-shadow .15s;width:100%;}
.ctrl-select{cursor:pointer;appearance:none;padding-right:32px;}
.ctrl-select:focus,.ctrl-input:focus{border-color:#1e3a8a;box-shadow:0 0 0 3px #dbeafe;}
.chevron{position:absolute;right:10px;top:50%;transform:translateY(-50%);pointer-events:none;}
.search-icon{position:absolute;left:11px;top:50%;transform:translateY(-50%);pointer-events:none;}
.ctrl-input.has-icon{padding-left:34px;}
.filter-actions{display:flex;gap:8px;margin-left:auto;}
.btn-primary{height:38px;padding:0 16px;background:#1e3a8a;color:white;border:none;border-radius:8px;font-family:inherit;font-size:13px;font-weight:600;cursor:pointer;transition:background .15s;display:flex;align-items:center;gap:6px;white-space:nowrap;}
.btn-primary:hover{background:#1e40af;}
.btn-ghost{height:38px;padding:0 16px;background:white;color:#334155;border:1px solid #e2e8f0;border-radius:8px;font-family:inherit;font-size:13px;font-weight:500;cursor:pointer;transition:all .15s;display:flex;align-items:center;gap:6px;white-space:nowrap;}
.btn-ghost:hover{border-color:#1e3a8a;color:#1e3a8a;}
.btn-ghost.sm{height:32px;font-size:12px;}
/* Stat cards */
.stat-cards{display:flex;gap:12px;margin-bottom:20px;}
.stat-card{background:white;border:1px solid #e2e8f0;border-radius:12px;padding:16px 20px;flex:1;min-width:0;transition:box-shadow .2s,border-color .2s;}
.stat-card:hover{border-color:#1e3a8a;box-shadow:0 4px 12px rgba(30,58,138,0.08);}
.stat-label{font-size:11px;color:#64748b;font-weight:500;margin-bottom:6px;}
.stat-value{font-size:22px;font-weight:700;letter-spacing:-0.03em;font-family:'JetBrains Mono',monospace;}
.stat-sub{font-size:11px;color:#94a3b8;margin-top:4px;}
.stat-value.pos{color:#047857;}
.stat-value.neg{color:#dc2626;}
.stat-value.nc{color:#0f172a;}
/* Section header */
.section-hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;}
.section-eyebrow{font-size:11px;font-weight:600;color:#1e3a8a;letter-spacing:0.06em;text-transform:uppercase;margin-bottom:4px;}
.section-title-row{display:flex;align-items:baseline;gap:8px;}
.section-h2{font-size:18px;font-weight:700;color:#0f172a;letter-spacing:-0.02em;}
.section-sub{font-size:12px;color:#94a3b8;}
.view-tabs{display:flex;gap:4px;background:#f1f5f9;padding:3px;border-radius:8px;}
.view-tab{padding:6px 14px;border-radius:6px;border:none;font-family:inherit;font-size:13px;font-weight:500;cursor:pointer;transition:all .15s;background:transparent;color:#64748b;}
.view-tab.active{background:#1e3a8a;color:white;}
/* Table */
.table-card{background:white;border:1px solid #e2e8f0;border-radius:14px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.04);margin-bottom:24px;}
.table-scroll{overflow-x:auto;}
.fin-table{border-collapse:collapse;width:100%;font-size:12.5px;}
.fin-table th,.fin-table td{padding:0 10px;white-space:nowrap;border-right:1px solid #f1f5f9;}
.fin-table th:last-child,.fin-table td:last-child{border-right:none;}
.fin-table thead tr{height:30px;}
.fin-table tbody tr{height:44px;border-top:1px solid #f1f5f9;cursor:pointer;transition:background .12s;}
.fin-table tbody tr:hover{background:#f0f5ff;}
.fin-table tbody tr.selected{background:#eff6ff;}
.num{font-family:'JetBrains Mono',monospace;font-size:12px;text-align:right;}
.pos{color:#047857;font-weight:600;}
.neg{color:#dc2626;font-weight:600;}
.neutral{color:#64748b;}
.muted{color:#94a3b8;}
.col-co{position:sticky;left:0;z-index:2;background:white;border-right:2px solid #f1f5f9!important;}
.fin-table tbody tr:hover .col-co{background:#f0f5ff;}
.fin-table tbody tr.selected .col-co{background:#eff6ff;}
.col-co-head{position:sticky;left:0;z-index:3;}
.table-footer{padding:12px 20px;background:#f8fafc;border-top:1px solid #f1f5f9;display:flex;align-items:center;justify-content:space-between;}
.footer-text{font-size:12px;color:#94a3b8;}
.rank-badge{width:24px;height:24px;border-radius:6px;background:#f1f5f9;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#64748b;flex-shrink:0;}
/* Tooltip */
.th-tip{position:relative;cursor:help;}
.th-tip:hover .tip-body{opacity:1;transform:translateX(-50%) translateY(0);}
.tip-body{position:absolute;bottom:calc(100% + 6px);left:50%;transform:translateX(-50%) translateY(4px);background:#0f172a;color:white;font-size:11px;padding:4px 8px;border-radius:6px;white-space:nowrap;opacity:0;pointer-events:none;transition:all .15s;z-index:100;font-family:'Noto Sans KR',sans-serif;font-weight:400;}
/* MiniBar */
.minibar-wrap{display:flex;align-items:center;gap:5px;justify-content:flex-end;}
.minibar-track{width:52px;height:5px;border-radius:3px;background:#f1f5f9;overflow:hidden;flex-shrink:0;}
.minibar-fill{height:100%;border-radius:3px;}
/* Detail panel */
.detail-panel{background:white;border:1px solid #e2e8f0;border-radius:14px;padding:24px;box-shadow:0 1px 4px rgba(0,0,0,0.04);}
.detail-panel h3{font-size:16px;font-weight:700;color:#0f172a;margin-bottom:16px;}
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px;}
.kpi-card{background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;}
.kpi-title{font-size:11px;color:#64748b;font-weight:500;margin-bottom:6px;}
.kpi-val{font-size:20px;font-weight:700;letter-spacing:-0.03em;font-family:'JetBrains Mono',monospace;}
.kpi-delta{font-size:11px;margin-top:4px;}
.panel-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;}
.panel-box{border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;}
.panel-box-title{background:#f8fafc;padding:10px 14px;font-size:12px;font-weight:600;color:#475569;border-bottom:1px solid #e2e8f0;}
.pl-table{width:100%;border-collapse:collapse;font-size:12px;}
.pl-table td{padding:8px 14px;border-bottom:1px solid #f1f5f9;}
.pl-table td:not(:first-child){font-family:'JetBrains Mono',monospace;text-align:right;}
.pl-table tr:last-child td{border-bottom:none;}
.chart-box{padding:14px;display:flex;align-items:flex-end;gap:10px;height:140px;}
.q-col{display:flex;flex-direction:column;align-items:center;flex:1;gap:4px;}
.bars{display:flex;align-items:flex-end;gap:3px;}
.bar{border-radius:3px 3px 0 0;}
.bar-rev{background:#c7d9ff;}
.bar-op{background:#1e3a8a;}
.q-label{font-size:10px;color:#94a3b8;}
</style>
</head>
<body>

<header class="topbar">
  <div class="topbar-inner">
    <div class="brand">
      <div class="brand-icon-box">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2">
          <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
          <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
        </svg>
      </div>
      <div>
        <div class="brand-title">업종별 재무현황 <span class="badge-ofs">별도기준</span></div>
        <div class="brand-sub">업종 기반 실적 비교 · 재무/손익/비용 통합</div>
      </div>
    </div>
    <div style="position:relative;">
      <select id="periodSelect" class="header-select"><option value="2025_annual">2025년 연간</option></select>
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.7)" stroke-width="2.5" style="position:absolute;right:10px;top:50%;transform:translateY(-50%);pointer-events:none;"><path d="m6 9 6 6 6-6"/></svg>
    </div>
  </div>
</header>

<div class="page-wrap">
  <div class="filter-bar">
    <div style="flex:0 0 280px;">
      <label class="filter-label">업종 선택</label>
      <div class="ctrl-wrap">
        <select id="industrySelect" class="ctrl-select"><option value="">업종을 선택하세요...</option><option value="all">🔍 전체 업종 검색</option></select>
        <svg class="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2.5"><path d="m6 9 6 6 6-6"/></svg>
      </div>
    </div>
    <div style="flex:0 0 100px;">
      <label class="filter-label">표시 기업 수</label>
      <div class="ctrl-wrap">
        <select id="rowCount" class="ctrl-select">
          <option value="10">10개</option><option value="20" selected>20개</option><option value="30">30개</option><option value="50">50개</option>
        </select>
        <svg class="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2.5"><path d="m6 9 6 6 6-6"/></svg>
      </div>
    </div>
    <div style="flex:1 1 200px;">
      <label class="filter-label">회사 검색</label>
      <div class="ctrl-wrap">
        <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <input id="companySearch" class="ctrl-input has-icon" type="text" placeholder="회사명 입력"/>
      </div>
    </div>
    <div style="flex:0 0 180px;">
      <label class="filter-label">정렬</label>
      <div class="ctrl-wrap">
        <select id="sortBy" class="ctrl-select">
          <option value="revenue-desc">매출액 높은순</option>
          <option value="opm-desc">영업이익률 높은순</option>
          <option value="growth-desc">매출증감률 높은순</option>
          <option value="opincome-desc">영업이익 증감률</option>
          <option value="name-asc">회사명 가나다순</option>
        </select>
        <svg class="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2.5"><path d="m6 9 6 6 6-6"/></svg>
      </div>
    </div>
    <div class="filter-actions">
      <button class="btn-primary" onclick="apiCache.clear();renderIndustryDashboard();">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/></svg>
        새로고침
      </button>
      <button class="btn-ghost" onclick="resetFilters()">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
        기본값
      </button>
    </div>
  </div>

  <div class="stat-cards">
    <div class="stat-card"><div class="stat-label">조회 기업 수</div><div class="stat-value nc" id="sc-count">—</div><div class="stat-sub" id="sc-count-sub"></div></div>
    <div class="stat-card"><div class="stat-label">평균 영업이익률</div><div class="stat-value nc" id="sc-opm">—</div><div class="stat-sub">전기 대비 평균</div></div>
    <div class="stat-card"><div class="stat-label">평균 순이익률</div><div class="stat-value nc" id="sc-npm">—</div><div class="stat-sub">전기 대비 평균</div></div>
    <div class="stat-card"><div class="stat-label">평균 매출증감률</div><div class="stat-value nc" id="sc-growth">—</div><div class="stat-sub">전기 대비</div></div>
  </div>

  <div class="section-hd">
    <div>
      <div class="section-eyebrow">재무정보</div>
      <div class="section-title-row">
        <h2 class="section-h2">회사별 재무 현황</h2>
        <span class="section-sub" id="sectionSub">업종을 선택하세요</span>
      </div>
    </div>
    <div class="view-tabs">
      <button class="view-tab active" id="tabFull" onclick="setViewMode(\'full\')">전체</button>
      <button class="view-tab" id="tabCompact" onclick="setViewMode(\'compact\')">요약</button>
    </div>
  </div>

  <div class="table-card">
    <div class="table-scroll">
      <table class="fin-table">
        <thead>
          <tr>
            <th rowspan="2" class="col-co-head" style="background:#1e3a8a;color:white;font-weight:700;font-size:12.5px;text-align:left;padding:0 16px;min-width:160px;border-bottom:1px solid rgba(255,255,255,0.15);border-right:2px solid rgba(255,255,255,0.15)!important;">회사명</th>
            <th colspan="3" id="thPrevLabel" style="background:#1e3a8a;color:white;font-size:11px;font-weight:600;letter-spacing:.04em;text-align:center;border-bottom:1px solid rgba(255,255,255,0.15);">전기 대비</th>
            <th colspan="3" style="background:#1e3a8a;color:white;font-size:11px;font-weight:600;letter-spacing:.04em;text-align:center;border-bottom:1px solid rgba(255,255,255,0.15);border-left:2px solid rgba(255,255,255,0.15);">매출액</th>
            <th colspan="3" style="background:#1e3a8a;color:white;font-size:11px;font-weight:600;letter-spacing:.04em;text-align:center;border-bottom:1px solid rgba(255,255,255,0.15);border-left:2px solid rgba(255,255,255,0.15);">매출원가</th>
            <th colspan="3" style="background:#1e3a8a;color:white;font-size:11px;font-weight:600;letter-spacing:.04em;text-align:center;border-bottom:1px solid rgba(255,255,255,0.15);border-left:2px solid rgba(255,255,255,0.15);">판매관리비</th>
            <th colspan="3" style="background:#1e3a8a;color:white;font-size:11px;font-weight:600;letter-spacing:.04em;text-align:center;border-bottom:1px solid rgba(255,255,255,0.15);border-left:2px solid rgba(255,255,255,0.15);">영업이익</th>
            <th colspan="2" style="background:#1e3a8a;color:white;font-size:11px;font-weight:600;letter-spacing:.04em;text-align:center;border-bottom:1px solid rgba(255,255,255,0.15);border-left:2px solid rgba(255,255,255,0.15);">세전이익</th>
          </tr>
          <tr style="background:#1e3a8a;">
            <th class="th-tip" style="color:rgba(255,255,255,.85);font-size:11px;font-weight:500;text-align:right;padding:0 10px;">영업이익률<span class="tip-body">영업이익 ÷ 매출액</span></th>
            <th class="th-tip" style="color:rgba(255,255,255,.85);font-size:11px;font-weight:500;text-align:right;padding:0 10px;border-left:1px solid rgba(255,255,255,.1);">순이익률<span class="tip-body">순이익 ÷ 매출액</span></th>
            <th class="th-tip" style="color:rgba(255,255,255,.85);font-size:11px;font-weight:500;text-align:right;padding:0 10px;border-left:1px solid rgba(255,255,255,.1);">매출증감률<span class="tip-body">전기 대비 매출 증감</span></th>
            <th style="color:rgba(255,255,255,.85);font-size:11px;font-weight:500;text-align:right;padding:0 10px;border-left:2px solid rgba(255,255,255,.15);">당기</th>
            <th style="color:rgba(255,255,255,.85);font-size:11px;font-weight:500;text-align:right;padding:0 10px;border-left:1px solid rgba(255,255,255,.1);">전기</th>
            <th style="color:rgba(255,255,255,.85);font-size:11px;font-weight:500;text-align:right;padding:0 10px;border-left:1px solid rgba(255,255,255,.1);">증감률</th>
            <th style="color:rgba(255,255,255,.85);font-size:11px;font-weight:500;text-align:right;padding:0 10px;border-left:2px solid rgba(255,255,255,.15);">당기</th>
            <th style="color:rgba(255,255,255,.85);font-size:11px;font-weight:500;text-align:right;padding:0 10px;border-left:1px solid rgba(255,255,255,.1);">전기</th>
            <th style="color:rgba(255,255,255,.85);font-size:11px;font-weight:500;text-align:right;padding:0 10px;border-left:1px solid rgba(255,255,255,.1);">증감률</th>
            <th style="color:rgba(255,255,255,.85);font-size:11px;font-weight:500;text-align:right;padding:0 10px;border-left:2px solid rgba(255,255,255,.15);">당기</th>
            <th style="color:rgba(255,255,255,.85);font-size:11px;font-weight:500;text-align:right;padding:0 10px;border-left:1px solid rgba(255,255,255,.1);">전기</th>
            <th class="th-tip" style="color:rgba(255,255,255,.85);font-size:11px;font-weight:500;text-align:right;padding:0 10px;border-left:1px solid rgba(255,255,255,.1);">증감률<span class="tip-body">영업이익 전기 대비</span></th>
            <th style="color:rgba(255,255,255,.85);font-size:11px;font-weight:500;text-align:right;padding:0 10px;border-left:2px solid rgba(255,255,255,.15);">당기</th>
            <th style="color:rgba(255,255,255,.85);font-size:11px;font-weight:500;text-align:right;padding:0 10px;border-left:1px solid rgba(255,255,255,.1);">전기</th>
            <th style="color:rgba(255,255,255,.85);font-size:11px;font-weight:500;text-align:right;padding:0 10px;border-left:2px solid rgba(255,255,255,.15);">당기</th>
            <th style="color:rgba(255,255,255,.85);font-size:11px;font-weight:500;text-align:right;padding:0 10px;border-left:1px solid rgba(255,255,255,.1);">전기</th>
          </tr>
        </thead>
        <tbody id="tableBody">
          <tr><td colspan="18" style="text-align:center;padding:60px;color:#94a3b8;">업종을 선택하세요</td></tr>
        </tbody>
      </table>
    </div>
    <div class="table-footer">
      <span class="footer-text" id="footerText">—</span>
      <button class="btn-ghost sm" onclick="csvDownload()">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        CSV 다운로드
      </button>
    </div>
  </div>

  <div id="detailPanel"></div>
</div>

<script>
%%INDUSTRY_DATA%%

let selectedCompanyCode = '', currentMetrics = [], periodMeta = {}, viewMode = 'full';

const fmt = v => v ? Math.round(v/1e6).toLocaleString('ko-KR') : '—';
const fmtEok = v => { if(!v) return '—'; const e=v/1e8; return Math.abs(e)>=1e3?(e/1e3).toFixed(1)+'조':e.toFixed(1)+'억'; };
const fmtPct = v => (v===null||v===undefined||isNaN(v)) ? '—' : (v>0?'+':'')+v.toFixed(1)+'%';
const pctCls = v => (v===null||v===undefined||isNaN(v)) ? 'neutral' : v>0?'pos':v<0?'neg':'neutral';
const growthRate = (c,p) => (!p||!c) ? null : (c-p)/Math.abs(p)*100;

function miniBar(value, max) {
  max = max||30;
  if(value===null||isNaN(value)) return '<span class="muted">—</span>';
  const neg=value<0, w=Math.min(Math.abs(value)/max*52,52), col=neg?'#fca5a5':'#6ee7b7';
  return '<div class="minibar-wrap"><span class="num '+pctCls(value)+'" style="font-size:12px;">'+fmtPct(value)+'</span>'
        +'<div class="minibar-track"><div class="minibar-fill" style="background:'+col+';width:'+w+'px;'+(neg?'margin-left:auto;':'')+'"></div></div></div>';
}

function getSelectedPeriod(){const v=document.getElementById('periodSelect').value,p=v.split('_');return{year:p[0],quarter:p[1],key:v};}
function getPeriodLabel(){const v=document.getElementById('periodSelect').value;return (periodMeta[v]&&periodMeta[v].label)||v;}
function getPrevLabel(){const v=document.getElementById('periodSelect').value;return (periodMeta[v]&&periodMeta[v].prevLabel)||'전기 대비';}

function setViewMode(m){
  viewMode=m;
  document.getElementById('tabFull').classList.toggle('active',m==='full');
  document.getElementById('tabCompact').classList.toggle('active',m==='compact');
  if(currentMetrics.length) renderResults(currentMetrics);
}

async function loadManifest(){
  try{
    const r=await fetch('/data/manifest.json'); if(!r.ok) return;
    const d=await r.json(), sel=document.getElementById('periodSelect');
    sel.innerHTML='';
    d.periods.forEach(p=>{
      periodMeta[p.key]={label:p.label,prevLabel:p.prevLabel};
      const o=document.createElement('option'); o.value=p.key; o.textContent=p.label; sel.appendChild(o);
    });
    if(d.latest) sel.value=d.latest;
  }catch(e){ periodMeta['2025_annual']={label:'2025년 연간',prevLabel:'2024년 연간 대비'}; }
}

function initializeIndustries(){
  const s=document.getElementById('industrySelect');
  INDUSTRY_DATA.industries.forEach(i=>{const o=document.createElement('option');o.value=i.code;o.textContent=i.name;s.appendChild(o);});
}

const apiCache=new Map();

async function renderIndustryDashboard(){
  const ic=document.getElementById('industrySelect').value;
  const rc=Number(document.getElementById('rowCount').value);
  const cs=document.getElementById('companySearch').value.trim().toLowerCase();
  const {year,quarter}=getSelectedPeriod();

  document.getElementById('thPrevLabel').textContent=getPrevLabel();

  if(!ic){
    document.getElementById('tableBody').innerHTML='<tr><td colspan="18" style="text-align:center;padding:60px;color:#94a3b8;">업종을 선택하세요</td></tr>';
    updateStatCards([],null); return;
  }

  // 전체 업종 모드: 모든 기업 합산 (중복 제거)
  let ind=null, allCo=[];
  if(ic==='all'){
    const seen=new Set();
    Object.values(INDUSTRY_DATA.companies).forEach(companies=>{
      companies.forEach(c=>{ if(!seen.has(c.stock_code)){seen.add(c.stock_code);allCo.push(c);} });
    });
  } else {
    ind=INDUSTRY_DATA.industries.find(i=>i.code===ic);
    allCo=INDUSTRY_DATA.companies[ic]||[];
    if(!allCo.length){
      document.getElementById('tableBody').innerHTML='<tr><td colspan="18" style="text-align:center;padding:60px;color:#94a3b8;">해당 업종의 기업 데이터가 없습니다.</td></tr>'; return;
    }
  }

  if(selectedCompanyCode&&!allCo.some(c=>c.stock_code===selectedCompanyCode)) selectedCompanyCode='';

  const ck=ic+'-'+year+'-'+quarter;
  if(!apiCache.has(ck)){
    document.getElementById('tableBody').innerHTML='<tr><td colspan="18" style="text-align:center;padding:60px;color:#94a3b8;"><div style="font-size:28px;margin-bottom:10px;">⏳</div><div style="font-size:14px;font-weight:600;color:#475569;">데이터 불러오는 중...</div><div style="font-size:12px;margin-top:6px;">'+(ind?ind.name:'')+' · '+getPeriodLabel()+'</div></td></tr>';
    try{
      const r=await fetch('/data/financial_'+year+'_'+quarter+'.json');
      if(!r.ok) throw new Error(year+'년 '+quarter+' 데이터가 아직 없습니다. (매주 월요일 자동 업데이트)');
      const d=await r.json();
      apiCache.set(ck, allCo.map(c=>Object.assign({},d.companies[c.stock_code]||{stockCode:c.stock_code},{companyName:c.name})));
    }catch(e){
      document.getElementById('tableBody').innerHTML='<tr><td colspan="18" style="text-align:center;padding:60px;color:#dc2626;">데이터 없음: '+e.message+'</td></tr>'; return;
    }
  }

  let metrics=apiCache.get(ck).slice();
  if(cs) metrics=metrics.filter(m=>m.companyName&&m.companyName.toLowerCase().includes(cs));
  const sb=document.getElementById('sortBy').value;
  metrics.sort((a,b)=>{
    if(sb==='name-asc') return (a.companyName||'').localeCompare(b.companyName||'','ko');
    if(sb==='opm-desc') return (b.opMargin||0)-(a.opMargin||0);
    if(sb==='growth-desc') return (b.revenueGrowth||0)-(a.revenueGrowth||0);
    if(sb==='opincome-desc') return (b.opIncome||0)-(a.opIncome||0);
    return (b.revenue||0)-(a.revenue||0);
  });
  metrics=metrics.slice(0,rc);
  currentMetrics=metrics;

  const indLabel = ic==='all' ? '전체 업종' : (ind?ind.name:'');
  document.getElementById('sectionSub').textContent='— '+indLabel+' · '+getPeriodLabel()+' (단위: 백만원)';
  document.getElementById('footerText').textContent='총 '+metrics.length+'개 기업 표시 중'+(ic==='all'?' (전체 업종)':'')+' · 단위: 백만원';
  updateStatCards(metrics, ic==='all' ? {name:'전체 업종'} : ind);
  renderResults(metrics);
}

function updateStatCards(metrics,industry){
  const n=metrics.filter(m=>m.revenue>0).length, len=metrics.length;
  const avgOpm=len?metrics.reduce((s,m)=>s+(m.opMargin||0),0)/len:null;
  const avgNpm=len?metrics.reduce((s,m)=>s+(m.netMargin||0),0)/len:null;
  const avgGrow=len?metrics.reduce((s,m)=>s+(m.revenueGrowth||0),0)/len:null;
  document.getElementById('sc-count').textContent=n+'개';
  document.getElementById('sc-count-sub').textContent=industry?industry.name.substring(0,14):'';
  const setC=(id,v)=>{const el=document.getElementById(id);el.textContent=fmtPct(v);el.className='stat-value '+(v>0?'pos':v<0?'neg':'nc');};
  setC('sc-opm',avgOpm); setC('sc-npm',avgNpm); setC('sc-growth',avgGrow);
}

function renderResults(metrics){
  const tb=document.getElementById('tableBody');
  if(!metrics.length){tb.innerHTML='<tr><td colspan="18" style="text-align:center;padding:40px;color:#94a3b8;">검색 결과가 없습니다.</td></tr>';renderDetailPanel(null);return;}

  const nc=(v,cls,grp)=>'<td class="num '+(cls||'neutral')+'" style="text-align:right;border-left:'+(grp?'2':'1')+'px solid #f1f5f9;">'+v+'</td>';

  tb.innerHTML=metrics.map((item,ri)=>{
    const revG=item.revenueGrowth, cogsG=growthRate(item.cogs,item.prevCogs);
    const sgaG=growthRate(item.sga,item.prevSga), opG=growthRate(item.opIncome,item.prevOpIncome);
    const hasCogs=item.cogs>0, hasSga=item.sga>0;
    const opCol=(item.opIncome||0)<0?'#dc2626':(item.opIncome||0)>0?'#047857':'#64748b';
    const taxCol=(item.pretaxIncome||0)<0?'#dc2626':(item.pretaxIncome||0)>0?'#047857':'#64748b';
    const isSel=item.stockCode===selectedCompanyCode;

    let opmCell;
    if(viewMode==='compact'){
      const bg=(item.opMargin||0)>0?'#ecfdf5':'#fef2f2', col=(item.opMargin||0)>0?'#047857':'#dc2626';
      opmCell='<td class="num" style="text-align:right;"><span style="display:inline-block;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:600;background:'+bg+';color:'+col+';">'+fmtPct(item.opMargin)+'</span></td>';
    } else {
      opmCell='<td class="num '+pctCls(item.opMargin)+'" style="text-align:right;">'+fmtPct(item.opMargin)+'</td>';
    }

    return '<tr class="'+(isSel?'selected':'')+'" onclick="selectRow(\''+item.stockCode+'\')">'
      +'<td class="col-co" style="padding:0 16px;"><div style="display:flex;align-items:center;gap:8px;"><div class="rank-badge">'+(ri+1)+'</div><span style="font-weight:600;font-size:13px;">'+(item.companyName||item.stockCode)+'</span></div></td>'
      +opmCell
      +'<td class="num '+pctCls(item.netMargin)+'" style="text-align:right;border-left:1px solid #f1f5f9;">'+fmtPct(item.netMargin)+'</td>'
      +'<td style="border-left:1px solid #f1f5f9;">'+miniBar(revG,30)+'</td>'
      +nc(fmt(item.revenue),'neutral',true)+nc(fmt(item.prevRevenue),'neutral',false)
      +'<td class="num '+pctCls(revG)+'" style="text-align:right;border-left:1px solid #f1f5f9;">'+fmtPct(revG)+'</td>'
      +nc(hasCogs?fmt(item.cogs):'—',hasCogs?'neutral':'muted',true)+nc(hasCogs?fmt(item.prevCogs):'—',hasCogs?'neutral':'muted',false)
      +'<td class="num '+(hasCogs?pctCls(cogsG):'muted')+'" style="text-align:right;border-left:1px solid #f1f5f9;">'+(hasCogs?fmtPct(cogsG):'—')+'</td>'
      +nc(hasSga?fmt(item.sga):'—',hasSga?'neutral':'muted',true)+nc(hasSga?fmt(item.prevSga):'—',hasSga?'neutral':'muted',false)
      +'<td class="num '+(hasSga?pctCls(sgaG):'muted')+'" style="text-align:right;border-left:1px solid #f1f5f9;">'+(hasSga?fmtPct(sgaG):'—')+'</td>'
      +'<td class="num" style="text-align:right;border-left:2px solid #f1f5f9;color:'+opCol+';font-weight:600;">'+fmt(item.opIncome)+'</td>'
      +nc(fmt(item.prevOpIncome),'neutral',false)
      +'<td style="border-left:1px solid #f1f5f9;">'+miniBar(opG,100)+'</td>'
      +'<td class="num" style="text-align:right;border-left:2px solid #f1f5f9;color:'+taxCol+';font-weight:600;">'+fmt(item.pretaxIncome)+'</td>'
      +nc(fmt(item.prevPretaxIncome),'neutral',false)
      +'</tr>';
  }).join('');

  renderDetailPanel(metrics.find(m=>m.stockCode===selectedCompanyCode)||null);
}

function selectRow(sc){selectedCompanyCode=(selectedCompanyCode===sc)?'':sc;renderResults(currentMetrics);}

function renderDetailPanel(item){
  const p=document.getElementById('detailPanel');
  if(!item){p.innerHTML='';return;}
  const rev=item.revenue||0, prevRev=item.prevRevenue||0;
  const op=item.opIncome||0, prevOp=item.prevOpIncome||0;
  const net=item.netIncome||0, cogs=item.cogs||0, prevCogs=item.prevCogs||0;
  const sga=item.sga||0, prevSga=item.prevSga||0;
  const pretax=item.pretaxIncome||0, prevPretax=item.prevPretaxIncome||0;
  const revG=growthRate(rev,prevRev), opG=growthRate(op,prevOp), netG=growthRate(net,item.prevNetIncome);
  const cogsG=growthRate(cogs,prevCogs), sgaG=growthRate(sga,prevSga);
  const kpi=(t,v,d,dv)=>'<div class="kpi-card"><div class="kpi-title">'+t+'</div><div class="kpi-val '+pctCls(dv)+'">'+v+'</div><div class="kpi-delta '+pctCls(dv)+'">'+d+'</div></div>';
  const qw=[0.24,0.22,0.25,0.29], maxR=Math.max(...qw.map(w=>rev*w),1);
  const bars=qw.map((w,i)=>{
    const rh=Math.max(16,rev*w/maxR*100), oh=Math.max(8,Math.abs(op*w)/maxR*100);
    return '<div class="q-col"><div class="bars"><div class="bar bar-rev" style="height:'+rh+'px;width:16px;"></div><div class="bar bar-op" style="height:'+oh+'px;width:10px;"></div></div><div class="q-label">'+(i+1)+'Q</div></div>';
  }).join('');
  const plr=(label,c,pv,g,b)=>{
    const s=b?'font-weight:700;':'';
    const ct=c?Math.round(c/1e6).toLocaleString():'—', pt=pv?Math.round(pv/1e6).toLocaleString():'—';
    return '<tr><td style="'+s+'">'+label+'</td><td class="'+pctCls(c)+'" style="'+s+'">'+ct+'</td><td class="neutral" style="'+s+'">'+pt+'</td><td class="'+pctCls(g)+'" style="'+s+'">'+fmtPct(g)+'</td></tr>';
  };
  p.innerHTML='<div class="detail-panel">'
    +'<h3>📊 '+item.companyName+' — '+getPeriodLabel()+' 재무상세</h3>'
    +'<div class="kpi-grid">'+kpi('매출액',fmtEok(rev),fmtPct(revG)+' 전기비',revG)+kpi('영업이익',fmtEok(op),fmtPct(opG)+' 전기비',opG)+kpi('당기순이익',fmtEok(net),fmtPct(netG)+' 전기비',netG)+kpi('영업이익률',item.opMargin?item.opMargin.toFixed(1)+'%':'—',fmtPct(opG)+' 전기비',opG)+'</div>'
    +'<div class="panel-grid">'
      +'<div class="panel-box"><div class="panel-box-title">손익계산서 요약 (단위: 백만원)</div>'
        +'<table class="pl-table"><thead><tr style="background:#f8fafc;"><td style="font-weight:600;padding:8px 14px;border-bottom:1px solid #e2e8f0;">계정과목</td><td style="font-weight:600;padding:8px 14px;border-bottom:1px solid #e2e8f0;text-align:right;">당기</td><td style="font-weight:600;padding:8px 14px;border-bottom:1px solid #e2e8f0;text-align:right;">전기</td><td style="font-weight:600;padding:8px 14px;border-bottom:1px solid #e2e8f0;text-align:right;">증감률</td></tr></thead>'
        +'<tbody>'+plr('매출액',rev,prevRev,revG,true)+plr('매출원가',cogs,prevCogs,cogsG,false)+plr('판매비와관리비',sga,prevSga,sgaG,false)+plr('영업이익',op,prevOp,opG,true)+plr('세전이익',pretax,prevPretax,growthRate(pretax,prevPretax),false)+plr('당기순이익',net,item.prevNetIncome||0,netG,true)+'</tbody></table></div>'
      +'<div class="panel-box"><div class="panel-box-title">분기별 매출·영업이익 (추정)</div>'
        +'<div class="chart-box" style="align-items:flex-end;gap:12px;">'+bars+'</div>'
        +'<div style="padding:8px 14px;font-size:11px;color:#94a3b8;">■ 매출액 &nbsp;■ 영업이익 (연간 분기 추정)</div>'
      +'</div>'
    +'</div></div>';
  setTimeout(()=>p.scrollIntoView({behavior:'smooth',block:'nearest'}),50);
}

function csvDownload(){
  if(!currentMetrics.length) return;
  const hdr=['회사명','영업이익률(%)','순이익률(%)','매출증감률(%)','매출액(백만원)','전기매출(백만원)','매출원가(백만원)','전기매출원가(백만원)','판관비(백만원)','전기판관비(백만원)','영업이익(백만원)','전기영업이익(백만원)','세전이익(백만원)','전기세전이익(백만원)'];
  const rows=currentMetrics.map(m=>[m.companyName,m.opMargin?.toFixed(1)||'',m.netMargin?.toFixed(1)||'',m.revenueGrowth?.toFixed(1)||'',Math.round((m.revenue||0)/1e6),Math.round((m.prevRevenue||0)/1e6),Math.round((m.cogs||0)/1e6),Math.round((m.prevCogs||0)/1e6),Math.round((m.sga||0)/1e6),Math.round((m.prevSga||0)/1e6),Math.round((m.opIncome||0)/1e6),Math.round((m.prevOpIncome||0)/1e6),Math.round((m.pretaxIncome||0)/1e6),Math.round((m.prevPretaxIncome||0)/1e6)]);
  const csv='\\ufeff'+[hdr,...rows].map(r=>r.join(',')).join('\\n');
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));
  a.download='재무현황_'+getPeriodLabel()+'.csv'; a.click();
}

function resetFilters(){
  document.getElementById('industrySelect').value='32100';
  document.getElementById('rowCount').value='20';
  document.getElementById('companySearch').value='';
  document.getElementById('sortBy').value='revenue-desc';
  const first=document.getElementById('periodSelect').options[0];
  if(first) document.getElementById('periodSelect').value=first.value;
  selectedCompanyCode=''; currentMetrics=[]; apiCache.clear();
  renderIndustryDashboard();
}

document.addEventListener('DOMContentLoaded', async function(){
  initializeIndustries();
  document.getElementById('industrySelect').value='32100';
  ['industrySelect','rowCount','sortBy'].forEach(id=>document.getElementById(id).addEventListener('change',renderIndustryDashboard));
  document.getElementById('companySearch').addEventListener('input',renderIndustryDashboard);
  document.getElementById('periodSelect').addEventListener('change',()=>{currentMetrics=[];apiCache.clear();renderIndustryDashboard();});
  await loadManifest();
  renderIndustryDashboard();
});
</script>
</body>
</html>'''

result = HTML_TEMPLATE.replace('%%INDUSTRY_DATA%%', industry_line)

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dart_financial_website.html')
with open(out, 'w', encoding='utf-8') as f:
    f.write(result)

print(f'완료! 크기: {len(result)//1024}KB → {out}')
