#!/usr/bin/env python3
import sys, io, os, time, requests, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DART_API_KEY = os.environ.get('DART_API_KEY', '')
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(BASE_DIR, 'api-worker', 'corp_code_map.json'), encoding='utf-8') as f:
    corp_map = json.load(f)
with open(os.path.join(BASE_DIR, 'industry_data.json'), encoding='utf-8') as f:
    ind_data = json.load(f)

print('=== KOSPI 기업 업종별 induty_nm 샘플 ===')
count = 0
for ind_code, companies in list(ind_data['companies'].items())[:15]:
    c = companies[0]
    sc = c['stock_code']
    cc = corp_map.get(sc) or corp_map.get(sc.zfill(6))
    if not cc:
        continue
    r = requests.get('https://opendart.fss.or.kr/api/company.json',
        params={'crtfc_key': DART_API_KEY, 'corp_code': cc}, timeout=10)
    d = r.json()
    nm = d.get('induty_nm', 'N/A')
    code = d.get('induty_code', 'N/A')
    print(f'  우리코드={ind_code} | 우리업종명={c["industry_name"][:18]:20s} | DART nm={nm} / code={code}')
    count += 1
    time.sleep(0.3)

print(f'\n총 {count}개 확인 완료')
