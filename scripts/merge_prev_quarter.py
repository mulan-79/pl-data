#!/usr/bin/env python3
"""
2024 분기 데이터를 2025 분기 파일의 prev* 필드에 병합
Usage: python scripts/merge_prev_quarter.py
"""
import json, os, glob

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(base, 'data')

for quarter in ['Q1', 'Q2', 'Q3']:
    path_2024 = os.path.join(data_dir, f'financial_2024_{quarter}.json')
    path_2025 = os.path.join(data_dir, f'financial_2025_{quarter}.json')
    
    if not os.path.exists(path_2024):
        print(f'[SKIP] 2024_{quarter}.json 없음')
        continue
    if not os.path.exists(path_2025):
        print(f'[SKIP] 2025_{quarter}.json 없음')
        continue
    
    with open(path_2024, encoding='utf-8') as f:
        d2024 = json.load(f)
    with open(path_2025, encoding='utf-8') as f:
        d2025 = json.load(f)
    
    prev_map = d2024['companies']
    updated = 0
    
    for sc, co in d2025['companies'].items():
        # 6자리 패딩 포함 조회
        prev = prev_map.get(sc) or prev_map.get(sc.zfill(6)) or prev_map.get(sc.lstrip('0'))
        if not prev:
            continue
        co['prevRevenue']      = prev.get('revenue', 0)
        co['prevCogs']         = prev.get('cogs', 0)
        co['prevSga']          = prev.get('sga', 0)
        co['prevOpIncome']     = prev.get('opIncome', 0)
        co['prevPretaxIncome'] = prev.get('pretaxIncome', 0)
        co['prevNetIncome']    = prev.get('netIncome', 0)
        # 증감률 재계산
        r, pr = co.get('revenue', 0), co['prevRevenue']
        co['revenueGrowth'] = round((r - pr) / abs(pr) * 100, 2) if pr else 0
        updated += 1
    
    with open(path_2025, 'w', encoding='utf-8') as f:
        json.dump(d2025, f, ensure_ascii=False)
    
    print(f'[OK] 2025_{quarter}: {updated}개 기업 prev* 업데이트 완료')

print('병합 완료')
