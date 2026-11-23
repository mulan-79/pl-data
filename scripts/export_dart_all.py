#!/usr/bin/env python3
"""data/financial_*.json (새 형식) → export/dart_all.json  (scripts/targets.json 65곳, 전 기간)"""
import json, os, re, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
FOUR = ['revenue', 'cogs', 'grossProfit', 'sga', 'rd', 'sgaTotal', 'opIncome', 'pretax', 'netIncome']
TWO = ['assets', 'liabilities', 'equity']

FIELDS_DOC = {
    'stockCode': '종목코드 6자리 문자열', 'corpCode': 'DART 고유번호 8자리', 'corpName': '회사 표시명',
    'competitor': '경쟁사 12곳이면 true',
    'period': '예: 2026_Q3 / 2025_annual (Q2=반기, Q3=3분기)',
    'fsDiv': 'OFS=별도, CFS=연결(별도가 없어 대체)', 'rceptNo': 'DART 접수번호(공시 원문 식별)',
    '4값 항목': 'revenue, cogs, grossProfit, sga, rd, sgaTotal, opIncome, pretax, netIncome = '
              '[3개월 당기, 누적 당기, 3개월 전년동기, 누적 전년동기] (원, 정수, 없으면 null; 연간은 3개월 칸 null)',
    '2값 항목': 'assets, liabilities, equity = [당기말, 전기말]',
    'sga': '손익계산서에 적힌 판관비(연구개발비를 따로 적는 회사는 제외된 값)', 'rd': '따로 적힌 연구개발비',
    'sgaTotal': '매출총이익 − 영업이익 (회사 간 비교용 판관비)',
}


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    with open(os.path.join(HERE, 'targets.json'), encoding='utf-8') as f:
        tg = json.load(f)
    comp = {t['code'] for t in tg['competitors']}
    data_dir = os.path.join(BASE, 'data')
    files = sorted(fn for fn in os.listdir(data_dir) if re.match(r'financial_\d{4}_(annual|Q\d)\.json$', fn))

    periods = {}
    for fn in files:
        key = fn[len('financial_'):-len('.json')]
        with open(os.path.join(data_dir, fn), encoding='utf-8') as f:
            periods[key] = json.load(f)['companies']

    records, missing = [], []
    for t in tg['targets']:
        code = t['code']
        for key in sorted(periods):
            c = periods[key].get(code.lstrip('0')) or periods[key].get(code)
            if not c or 'amounts' not in c:
                missing.append({'stockCode': code, 'period': key})
                continue
            a = c['amounts']
            rec = {'stockCode': code, 'corpCode': c['corpCode'], 'corpName': t['name'],
                   'competitor': code in comp, 'period': key,
                   'fsDiv': c.get('fsDiv'), 'rceptNo': c.get('rceptNo')}
            for k in FOUR:
                rec[k] = a[k]
            for k in TWO:
                rec[k] = a[k]
            records.append(rec)

    out = {'generatedAt': datetime.now().strftime('%Y-%m-%d %H:%M'), 'unit': 'KRW(원)',
           'source': 'DART OpenAPI fnlttSinglAcntAll', 'fields': FIELDS_DOC,
           'companies': len(tg['targets']), 'periods': sorted(periods), 'records': records, 'missing': missing}
    os.makedirs(os.path.join(BASE, 'export'), exist_ok=True)
    path = os.path.join(BASE, 'export', 'dart_all.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False)
    print(f'{path}: 레코드 {len(records)}건 / 자료 없음 {len(missing)}건')


if __name__ == '__main__':
    main()
