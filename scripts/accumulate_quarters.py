#!/usr/bin/env python3
"""
개별 분기값 → 누계값으로 합산 변환
  Q1 누계 = Q1
  Q2 누계 = Q1 + Q2
  Q3 누계 = Q1 + Q2 + Q3

사용법:
  python accumulate_quarters.py 2026        # 2026년만 처리 (권장: 새 분기 추가 후)
  python accumulate_quarters.py 2026 2025   # 여러 연도 지정
  python accumulate_quarters.py             # 전체 연도 (주의: 이미 누계된 파일에 재실행 금지)
"""
import json, os, re, sys

base     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(base, 'data')

SUM_FIELDS = ['revenue','cogs','sga','opIncome','pretaxIncome','netIncome']
PREV_MAP   = {'prevRevenue':'revenue','prevCogs':'cogs','prevSga':'sga',
              'prevOpIncome':'opIncome','prevPretaxIncome':'pretaxIncome','prevNetIncome':'netIncome'}

def load(year, q):
    p = os.path.join(data_dir, f'financial_{year}_{q}.json')
    if not os.path.exists(p): return None
    with open(p, encoding='utf-8') as f: return json.load(f)

def save(d, year, q):
    p = os.path.join(data_dir, f'financial_{year}_{q}.json')
    with open(p, 'w', encoding='utf-8') as f: json.dump(d, f, ensure_ascii=False)

def recalc_rates(co):
    r  = co.get('revenue', 0)
    pr = co.get('prevRevenue', 0)
    co['revenueGrowth'] = round((r-pr)/abs(pr)*100,2) if pr else 0
    co['cogsRate']  = round(co.get('cogs',0)/r*100,2) if r else 0
    co['sgaRate']   = round(co.get('sga',0)/r*100,2) if r else 0
    co['opMargin']  = round(co.get('opIncome',0)/r*100,2) if r else 0
    co['netMargin'] = round(co.get('netIncome',0)/r*100,2) if r else 0

def get_co(companies, sc):
    return companies.get(sc) or companies.get(sc.zfill(6)) or companies.get(sc.lstrip('0'))

# 처리할 연도 결정: 인수 있으면 지정 연도만, 없으면 전체
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

# ── 1단계: 각 연도별 누계 합산 ──────────────────────────
for year in years:
    q1 = load(year, 'Q1')
    q2 = load(year, 'Q2')
    q3 = load(year, 'Q3')
    if not q1:
        print(f'[SKIP] {year} Q1 파일 없음'); continue

    if q2:
        cnt = 0
        for sc, co in q2['companies'].items():
            c1 = get_co(q1['companies'], sc)
            if not c1: continue
            for f in SUM_FIELDS:
                co[f] = co.get(f,0) + c1.get(f,0)
            recalc_rates(co); cnt += 1
        save(q2, year, 'Q2')
        print(f'[{year} Q2] {cnt}개 → Q1+Q2 누계 저장')

    if q3 and q2:
        cnt = 0
        for sc, co in q3['companies'].items():
            c2 = get_co(q2['companies'], sc)
            if not c2: continue
            for f in SUM_FIELDS:
                co[f] = co.get(f,0) + c2.get(f,0)
            recalc_rates(co); cnt += 1
        save(q3, year, 'Q3')
        print(f'[{year} Q3] {cnt}개 → Q1+Q2+Q3 누계 저장')

# ── 2단계: 각 연도 prev* → 전년도 누계값으로 업데이트 ────────
for year in years:
    prev_year = str(int(year) - 1)
    print(f'\n--- {year} prev* 필드 → {prev_year} 누계 기준 ---')
    for q in ['Q1','Q2','Q3']:
        d_prev = load(prev_year, q)
        d_curr = load(year, q)
        if not d_prev or not d_curr: print(f'[SKIP] {year} {q}'); continue
        cnt = 0
        for sc, co in d_curr['companies'].items():
            p = get_co(d_prev['companies'], sc)
            if not p: continue
            for pf, sf in PREV_MAP.items():
                co[pf] = p.get(sf, 0)
            recalc_rates(co); cnt += 1
        save(d_curr, year, q)
        print(f'[{year} {q}] {cnt}개 prev* 업데이트')

print('\n완료!')
