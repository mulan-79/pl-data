#!/usr/bin/env python3
"""
[사용 중지] prev* 필드 동기화 스크립트 — 평상시 실행하지 말 것

fetch_dart_data.py가 frmtrm_add_amount(전기 누계)로 전기값을 DART에서
직접 취득하므로 이 스크립트는 더 이상 불필요하다. 실행하면 DART가 보고한
전기값을 우리 DB에서 파생한 값으로 덮어써 정확도가 떨어진다
(교차 대조 결과 약 3%가 어긋남).

전년도 데이터가 통째로 없어 전기값을 보완해야 하는 예외 상황에서만 사용.

사용법:
  python accumulate_quarters.py 2026        # 2026년만 처리 (권장)
  python accumulate_quarters.py 2026 2025   # 여러 연도 지정
  python accumulate_quarters.py             # 전체 연도
"""
import json, os, re, sys

base     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(base, 'data')

PREV_MAP = {'prevRevenue':'revenue','prevCogs':'cogs','prevSga':'sga',
            'prevOpIncome':'opIncome','prevPretaxIncome':'pretaxIncome','prevNetIncome':'netIncome'}

def load(year, q):
    p = os.path.join(data_dir, f'financial_{year}_{q}.json')
    if not os.path.exists(p): return None
    with open(p, encoding='utf-8') as f: return json.load(f)

def save(d, year, q):
    p = os.path.join(data_dir, f'financial_{year}_{q}.json')
    with open(p, 'w', encoding='utf-8') as f: json.dump(d, f, ensure_ascii=False)

def get_co(companies, sc):
    return companies.get(sc) or companies.get(sc.zfill(6)) or companies.get(sc.lstrip('0'))

def recalc_rates(co):
    r  = co.get('revenue', 0)
    pr = co.get('prevRevenue', 0)
    co['revenueGrowth'] = round((r-pr)/abs(pr)*100,2) if pr else 0
    co['cogsRate']  = round(co.get('cogs',0)/r*100,2) if r else 0
    co['sgaRate']   = round(co.get('sga',0)/r*100,2) if r else 0
    co['opMargin']  = round(co.get('opIncome',0)/r*100,2) if r else 0
    co['netMargin'] = round(co.get('netIncome',0)/r*100,2) if r else 0

# 처리할 연도 결정
if len(sys.argv) > 1:
    years = sorted(sys.argv[1:], reverse=True)
    print(f'지정 연도만 처리: {years}')
else:
    years = sorted(set(
        m.group(1)
        for f in os.listdir(data_dir)
        for m in [re.match(r'financial_(\d{4})_(Q1|Q2|Q3|annual)\.json', f)]
        if m
    ), reverse=True)
    print(f'전체 연도 처리: {years}')

# prev* 필드를 전년도 누계값으로 업데이트
for year in years:
    prev_year = str(int(year) - 1)
    print(f'\n--- {year} prev* → {prev_year} 기준 ---')
    for q in ['Q1', 'Q2', 'Q3']:
        d_prev = load(prev_year, q)
        d_curr = load(year, q)
        if not d_prev or not d_curr:
            print(f'  [SKIP] {year} {q}'); continue
        cnt = 0
        for sc, co in d_curr['companies'].items():
            p = get_co(d_prev['companies'], sc)
            if not p: continue
            for pf, sf in PREV_MAP.items():
                co[pf] = p.get(sf, 0)
            recalc_rates(co); cnt += 1
        save(d_curr, year, q)
        print(f'  [{year} {q}] {cnt}개 prev* 업데이트')

print('\n완료!')
