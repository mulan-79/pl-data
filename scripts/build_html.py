#!/usr/bin/env python3
"""HTML 내 INDUSTRY_DATA / THEME_DATA 교체 스크립트
기존 dart_financial_website.html의 모든 커스터마이징은 유지하고
const INDUSTRY_DATA = {...}; 와 const THEME_DATA = {...}; 줄만 교체한다.
"""
import re, os, json

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src  = os.path.join(base, 'dart_financial_website.html')

with open(src, encoding='utf-8') as f:
    html = f.read()

# ── INDUSTRY_DATA ──────────────────────────────────────────
industry_json_path = os.path.join(base, 'industry_data.json')
with open(industry_json_path, encoding='utf-8') as f:
    industry_data = json.load(f)
ind_line = 'const INDUSTRY_DATA = ' + json.dumps(industry_data, ensure_ascii=False) + ';'

# 백업
with open(os.path.join(base, 'scripts', '_industry_data.js'), 'w', encoding='utf-8') as f:
    f.write(ind_line)

total  = sum(len(v) for v in industry_data['companies'].values())
kospi  = sum(1 for v in industry_data['companies'].values() for c in v if c.get('market','KOSPI')=='KOSPI')
kosdaq = sum(1 for v in industry_data['companies'].values() for c in v if c.get('market')=='KOSDAQ')
print(f'INDUSTRY_DATA: {len(ind_line)//1024}KB | 전체:{total}개 KOSPI:{kospi} KOSDAQ:{kosdaq}')

html, n = re.subn(r'^const INDUSTRY_DATA = .*$', ind_line, html, flags=re.MULTILINE)
if n == 0:
    raise RuntimeError('HTML에서 INDUSTRY_DATA를 찾을 수 없습니다.')

# ── THEME_DATA (있을 때만) ──────────────────────────────────
theme_json_path = os.path.join(base, 'theme_data.json')
if os.path.exists(theme_json_path):
    with open(theme_json_path, encoding='utf-8') as f:
        theme_data = json.load(f)
    th_line = 'const THEME_DATA = ' + json.dumps(theme_data, ensure_ascii=False) + ';'
    t_stocks = sum(len(v) for v in theme_data['companies'].values())
    print(f'THEME_DATA: {len(th_line)//1024}KB | 테마:{len(theme_data["themes"])}개 종목매핑:{t_stocks}건')
    html, n2 = re.subn(r'^const THEME_DATA = .*$', th_line, html, flags=re.MULTILINE)
    if n2 == 0:
        print('  THEME_DATA 줄 없음 → 스킵 (HTML에 플레이스홀더 필요)')
else:
    print('theme_data.json 없음 → THEME_DATA 스킵')

with open(src, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'완료! {len(html)//1024}KB → {src}')
