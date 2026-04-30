#!/usr/bin/env python3
"""
개별 분기값 → 누계값으로 합산 변환 (재수집 없이)
  Q1 누계 = Q1
  Q2 누계 = Q1 + Q2
  Q3 누계 = Q1 + Q2 + Q3
2025 prev* 필드도 2024 누계 기준으로 업데이트
"""
import json, os

base     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(base, 'data')

# 합산할 손익 필드
SUM_FIELDS = ['revenue','cogs','sga','opIncome','pretaxIncome','netIncome']

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

# ── 1단계: 각 연도별 누계 합산 ──────────────────────────
for year in ['2025', '2024']:
    q1 = load(year, 'Q1')
    q2 = load(year, 'Q2')
    q3 = load(year, 'Q3')
    if not q1:
        print(f'[SKIP] {year} Q1 파일 없음'); continue

    # Q2 누계 = Q1 + Q2
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

    # Q3 누계 = (Q1+Q2 누계) + Q3
    if q3 and q2:
        cnt = 0
        for sc, co in q3['companies'].items():
            c2 = get_co(q2['companies'], sc)   # 이미 Q1+Q2 누계
            if not c2: continue
            for f in SUM_FIELDS:
                co[f] = co.get(f,0) + c2.get(f,0)
            recalc_rates(co); cnt += 1
        save(q3, year, 'Q3')
        print(f'[{year} Q3] {cnt}개 → Q1+Q2+Q3 누계 저장')

# ── 2단계: 2025 prev* → 2024 누계값으로 업데이트 ────────
print('\n--- 2025 prev* 필드 → 2024 누계 기준 ---')
PREV_MAP = {'prevRevenue':'revenue','prevCogs':'cogs','prevSga':'sga',
            'prevOpIncome':'opIncome','prevPretaxIncome':'pretaxIncome','prevNetIncome':'netIncome'}

for q in ['Q1','Q2','Q3']:
    d24 = load('2024', q)
    d25 = load('2025', q)
    if not d24 or not d25: print(f'[SKIP] {q}'); continue
    cnt = 0
    for sc, co in d25['companies'].items():
        p = get_co(d24['companies'], sc)
        if not p: continue
        for pf, sf in PREV_MAP.items():
            co[pf] = p.get(sf, 0)
        recalc_rates(co); cnt += 1
    save(d25, '2025', q)
    print(f'[2025 {q}] {cnt}개 prev* 업데이트')

print('\n✓ 완료!')
