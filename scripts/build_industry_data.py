#!/usr/bin/env python3
"""
KOSDAQ 기업 추가 스크립트
- DART CORPCODE.xml 다운로드 → 전체 상장사 corp_code 확보
- 기존 industry_data.json의 KOSPI 기업에 market='KOSPI' 추가
- KOSDAQ 기업 중 기존 업종에 해당하는 기업을 industry_data.json에 추가
- corp_code_map.json에 KOSDAQ corp_code 추가

Usage: python scripts/build_industry_data.py [--all-industries]
  --all-industries  기존 업종 외에도 새로운 업종의 KOSDAQ 기업 추가
"""
import json, os, sys, time, requests, zipfile, io
from xml.etree import ElementTree as ET

DART_API_KEY = os.environ.get('DART_API_KEY', '')
DART_BASE = 'https://opendart.fss.or.kr/api'

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDUSTRY_DATA_PATH = os.path.join(BASE_DIR, 'industry_data.json')
CORP_CODE_MAP_PATH = os.path.join(BASE_DIR, 'api-worker', 'corp_code_map.json')


def download_corpcode_xml():
    """DART에서 CORPCODE.xml 다운로드 (zip → xml 파싱)"""
    print('CORPCODE.xml 다운로드 중...')
    url = f'{DART_BASE}/corpCode.xml'
    resp = requests.get(url, params={'crtfc_key': DART_API_KEY}, timeout=60)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        xml_name = [n for n in zf.namelist() if n.endswith('.xml')][0]
        xml_data = zf.read(xml_name)

    root = ET.fromstring(xml_data)
    companies = []
    for item in root.findall('list'):
        corp_code  = (item.findtext('corp_code')  or '').strip()
        corp_name  = (item.findtext('corp_name')  or '').strip()
        stock_code = (item.findtext('stock_code') or '').strip()
        if stock_code:  # 상장사만
            companies.append({
                'corp_code':  corp_code,
                'corp_name':  corp_name,
                'stock_code': stock_code.lstrip('0') or stock_code,  # 앞 0 제거 (but keep if all 0)
                'stock_code_raw': stock_code,
            })

    print(f'  상장사 {len(companies)}개 파싱 완료')
    return companies


def fetch_company_info(corp_code, retry=2):
    """단일 기업 company.json 조회 → {corp_cls, induty_code, induty_nm, ...}"""
    url = f'{DART_BASE}/company.json'
    params = {'crtfc_key': DART_API_KEY, 'corp_code': corp_code}
    for attempt in range(retry + 1):
        try:
            resp = requests.get(url, params=params, timeout=20)
            data = resp.json()
            if data.get('status') == '000':
                return data
            if attempt < retry:
                time.sleep(1)
        except Exception:
            if attempt < retry:
                time.sleep(2)
    return None


def main():
    if not DART_API_KEY:
        print('오류: DART_API_KEY 환경변수가 없습니다.')
        sys.exit(1)

    add_all_industries = '--all-industries' in sys.argv

    # 1. 현재 industry_data.json 로드
    with open(INDUSTRY_DATA_PATH, encoding='utf-8') as f:
        industry_data = json.load(f)

    # 2. 현재 corp_code_map.json 로드
    with open(CORP_CODE_MAP_PATH, encoding='utf-8') as f:
        corp_code_map = json.load(f)

    # 기존 업종 코드 셋
    existing_industry_codes = {ind['code'] for ind in industry_data['industries']}

    # 기존 stock_code 셋 (모두 KOSPI로 간주)
    existing_stock_codes = set()
    for companies in industry_data['companies'].values():
        for c in companies:
            existing_stock_codes.add(c['stock_code'])
            existing_stock_codes.add(c['stock_code'].zfill(6))  # 패딩 포함

    print(f'기존 KOSPI 기업 수: {len(existing_stock_codes) // 2}')
    print(f'기존 업종 수: {len(existing_industry_codes)}')

    # 3. 기존 기업에 market='KOSPI' 추가
    kospi_updated = 0
    for ind_code, companies in industry_data['companies'].items():
        for c in companies:
            if 'market' not in c:
                c['market'] = 'KOSPI'
                kospi_updated += 1
    print(f'KOSPI market 필드 추가: {kospi_updated}개')

    # 4. CORPCODE.xml 다운로드
    all_listed = download_corpcode_xml()

    # 5. KOSDAQ 후보 (기존에 없는 기업)
    kosdaq_candidates = []
    for c in all_listed:
        sc = c['stock_code']
        sc_raw = c['stock_code_raw']
        if sc not in existing_stock_codes and sc_raw not in existing_stock_codes:
            kosdaq_candidates.append(c)
            # corp_code_map 업데이트 (없으면 추가)
            if sc not in corp_code_map:
                corp_code_map[sc] = c['corp_code']
            if sc_raw not in corp_code_map:
                corp_code_map[sc_raw] = c['corp_code']

    print(f'KOSDAQ 후보 기업 수: {len(kosdaq_candidates)}')

    # 6. KOSDAQ 기업별 company.json 조회
    print(f'\ncompany.json 개별 조회 시작... (약 {round(len(kosdaq_candidates)*0.3/60,1)}분 예상)')
    kosdaq_added = 0
    new_industries = {}

    for idx, c in enumerate(kosdaq_candidates):
        if (idx + 1) % 100 == 0 or (idx + 1) == len(kosdaq_candidates):
            print(f'  [{idx+1}/{len(kosdaq_candidates)}] 추가됨: {kosdaq_added}개')

        info = fetch_company_info(c['corp_code'])
        time.sleep(0.3)

        if not info:
            continue

        corp_cls   = info.get('corp_cls', '')
        induty_code = str(info.get('induty_code', '') or '').strip()
        induty_nm   = (info.get('induty_nm', '') or '').strip()
        corp_name   = info.get('corp_name', c['corp_name'])

        # KOSDAQ(K) 또는 KONEX(N) 중 KOSDAQ만
        if corp_cls != 'K':
            continue

        # 업종 코드 필터링
        if not induty_code:
            continue

        # 기존 업종에만 추가 (--all-industries 없으면)
        if not add_all_industries and induty_code not in existing_industry_codes:
            continue

        # 업종이 없으면 추가
        if induty_code not in existing_industry_codes:
            industry_data['industries'].append({
                'code': induty_code,
                'name': induty_nm,
            })
            existing_industry_codes.add(induty_code)
            print(f'  새 업종 추가: {induty_code} {induty_nm}')

        if induty_code not in industry_data['companies']:
            industry_data['companies'][induty_code] = []

        # 중복 방지
        existing_in_group = {c2['stock_code'] for c2 in industry_data['companies'][induty_code]}
        sc = c['stock_code']
        if sc in existing_in_group:
            continue

        industry_data['companies'][induty_code].append({
            'stock_code':     sc,
            'name':           corp_name,
            'industry_code':  induty_code,
            'industry_name':  induty_nm,
            'market':         'KOSDAQ',
        })
        kosdaq_added += 1

    print(f'\nKOSDAQ 기업 추가 완료: {kosdaq_added}개')

    # 7. industries 리스트 재정렬 (name 순)
    industry_data['industries'] = sorted(
        industry_data['industries'],
        key=lambda x: x['name']
    )

    # 8. 저장
    with open(INDUSTRY_DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(industry_data, f, ensure_ascii=False, indent=2)
    print(f'industry_data.json 저장 완료')

    with open(CORP_CODE_MAP_PATH, 'w', encoding='utf-8') as f:
        json.dump(corp_code_map, f, ensure_ascii=False)
    print(f'corp_code_map.json 저장 완료')

    # 9. 통계
    total_companies = sum(len(v) for v in industry_data['companies'].values())
    kospi_count = sum(
        1 for v in industry_data['companies'].values()
        for c in v if c.get('market') == 'KOSPI'
    )
    kosdaq_count = sum(
        1 for v in industry_data['companies'].values()
        for c in v if c.get('market') == 'KOSDAQ'
    )
    print(f'\n최종 통계:')
    print(f'  전체 기업: {total_companies}개')
    print(f'  KOSPI: {kospi_count}개')
    print(f'  KOSDAQ: {kosdaq_count}개')
    print(f'  업종 수: {len(industry_data["industries"])}개')
    print('\n완료!')


if __name__ == '__main__':
    main()
