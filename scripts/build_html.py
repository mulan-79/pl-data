#!/usr/bin/env python3
"""HTML 내 INDUSTRY_DATA만 교체하는 스크립트
기존 dart_financial_website.html의 모든 커스터마이징은 유지하고
const INDUSTRY_DATA = {...}; 한 줄만 최신 industry_data.json으로 교체한다.
"""
import re, os, json

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(base, 'dart_financial_website.html')
backup = os.path.join(base, 'scripts', '_industry_data.js')
industry_json_path = os.path.join(base, 'industry_data.json')

# industry_data.json → 새 INDUSTRY_DATA 라인 생성
with open(industry_json_path, encoding='utf-8') as f:
    industry_data = json.load(f)
new_line = 'const INDUSTRY_DATA = ' + json.dumps(industry_data, ensure_ascii=False) + ';'

# 백업 갱신
with open(backup, 'w', encoding='utf-8') as f:
    f.write(new_line)

total  = sum(len(v) for v in industry_data['companies'].values())
kospi  = sum(1 for v in industry_data['companies'].values() for c in v if c.get('market','KOSPI')=='KOSPI')
kosdaq = sum(1 for v in industry_data['companies'].values() for c in v if c.get('market')=='KOSDAQ')
print(f'INDUSTRY_DATA: {len(new_line)//1024}KB | 전체:{total}개 KOSPI:{kospi} KOSDAQ:{kosdaq}')

# 기존 HTML에서 const INDUSTRY_DATA = ...줄만 교체 (정규식으로 안전하게)
with open(src, encoding='utf-8') as f:
    html = f.read()

# ^const INDUSTRY_DATA = .*$ : 해당 줄 전체를 new_line으로 교체
new_html, n = re.subn(r'^const INDUSTRY_DATA = .*$', new_line, html, flags=re.MULTILINE)
if n == 0:
    raise RuntimeError('HTML에서 INDUSTRY_DATA를 찾을 수 없습니다.')
html = new_html

with open(src, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'완료! {len(html)//1024}KB → {src}')
