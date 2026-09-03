#!/usr/bin/env python3
"""
[실행 금지 / 1회성 마이그레이션 완료] 2026-09-03 적용 완료된 스크립트.

이후 fetch_dart_data.py가 add_amount(누계)를 직접 읽도록 수정되어
전 기간(2024~2026)을 재수집했으므로 현재 데이터는 이미 정상이다.
지금 실행하면 Q2에서 Q1을, Q3에서 Q2를 빼서 데이터를 훼손한다.
기록 보존 목적으로만 남겨둔다.

--- 이하 원본 설명 ---
잘못된 누계 합산 제거 스크립트
DART는 Q2(반기), Q3(3분기누계)를 이미 누적값으로 반환하므로
accumulate_quarters.py의 Q1/Q2 추가는 이중 계산이었음

수학적 역산:
  Q3_correct = Q3_stored - Q2_stored  (순서: Q3 먼저!)
  Q2_correct = Q2_stored - Q1_stored
"""
import json, os, sys

base     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(base, 'data')
SUM_FIELDS = ['revenue','cogs','sga','opIncome','pretaxIncome','netIncome']

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
    r = co.get('revenue', 0)
    pr = co.get('prevRevenue', 0)
    co['revenueGrowth'] = round((r-pr)/abs(pr)*100,2) if pr else 0
    co['cogsRate']  = round(co.get('cogs',0)/r*100,2) if r else 0
    co['sgaRate']   = round(co.get('sga',0)/r*100,2) if r else 0
    co['opMargin']  = round(co.get('opIncome',0)/r*100,2) if r else 0
    co['netMargin'] = round(co.get('netIncome',0)/r*100,2) if r else 0

years = sys.argv[1:] if len(sys.argv) > 1 else ['2026', '2025']
print(f'역산 대상 연도: {years}')

for year in years:
    q1 = load(year, 'Q1')
    q2 = load(year, 'Q2')
    q3 = load(year, 'Q3')
    if not q1: print(f'[SKIP] {year} Q1 없음'); continue

    # Q3 먼저: Q3_correct = Q3_stored - Q2_stored
    if q3 and q2:
        cnt = 0
        for sc, co in q3['companies'].items():
            c2 = get_co(q2['companies'], sc)
            if not c2: continue
            for f in SUM_FIELDS:
                co[f] = co.get(f, 0) - c2.get(f, 0)
            recalc_rates(co); cnt += 1
        save(q3, year, 'Q3')
        print(f'[{year} Q3] {cnt}개 역산 완료')

    # Q2: Q2_correct = Q2_stored - Q1_stored
    if q2:
        cnt = 0
        for sc, co in q2['companies'].items():
            c1 = get_co(q1['companies'], sc)
            if not c1: continue
            for f in SUM_FIELDS:
                co[f] = co.get(f, 0) - c1.get(f, 0)
            recalc_rates(co); cnt += 1
        save(q2, year, 'Q2')
        print(f'[{year} Q2] {cnt}개 역산 완료')

print('\n완료! 이제 accumulate_quarters.py [year]로 prev* 업데이트하세요.')
