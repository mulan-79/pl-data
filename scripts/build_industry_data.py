#!/usr/bin/env python3
"""
KOSDAQ 기업 추가 스크립트 (FinanceDataReader 버전)
- FinanceDataReader로 KOSPI/KOSDAQ 전체 종목 + 업종 정보 취득
- KRX 업종코드 기반으로 industry_data.json의 기존 업종과 매핑
- KOSDAQ 기업을 같은 업종에 추가, market 필드로 구분

Usage: pip install finance-datareader
       python scripts/build_industry_data.py
"""
import json, os, sys, time, requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDUSTRY_DATA_PATH = os.path.join(BASE_DIR, 'industry_data.json')
CORP_CODE_MAP_PATH = os.path.join(BASE_DIR, 'api-worker', 'corp_code_map.json')

def get_dart_corp_code_map():
    """corp_code_map.json 로드"""
    with open(CORP_CODE_MAP_PATH, encoding='utf-8') as f:
        return json.load(f)


def download_corpcode_xml():
    """DART CORPCODE.xml 다운로드 → stock_code → corp_code 매핑"""
    import zipfile, io
    from xml.etree import ElementTree as ET

    DART_API_KEY = os.environ.get('DART_API_KEY', '')
    if not DART_API_KEY:
        print('  DART_API_KEY 없음, corp_code_map.json만 사용합니다.')
        return {}

    print('  DART CORPCODE.xml 다운로드 중...')
    url = 'https://opendart.fss.or.kr/api/corpCode.xml'
    resp = requests.get(url, params={'crtfc_key': DART_API_KEY}, timeout=60)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        xml_name = [n for n in zf.namelist() if n.endswith('.xml')][0]
        xml_data = zf.read(xml_name)

    root = ET.fromstring(xml_data)
    mapping = {}
    for item in root.findall('list'):
        corp_code  = (item.findtext('corp_code') or '').strip()
        stock_code = (item.findtext('stock_code') or '').strip()
        if stock_code and corp_code:
            mapping[stock_code] = corp_code
            mapping[stock_code.lstrip('0') or stock_code] = corp_code
    print(f'  CORPCODE 매핑: {len(mapping)}개')
    return mapping


def main():
    try:
        import FinanceDataReader as fdr
    except ImportError:
        print('FinanceDataReader가 설치되지 않았습니다.')
        print('실행: pip install finance-datareader')
        sys.exit(1)

    # 1. 기존 industry_data.json 로드
    with open(INDUSTRY_DATA_PATH, encoding='utf-8') as f:
        industry_data = json.load(f)

    existing_industry_codes = {ind['code'] for ind in industry_data['industries']}

    # 기존 stock_code → industry_code 매핑 (빠른 중복 확인용)
    existing_stock_codes = set()
    for ind_code, companies in industry_data['companies'].items():
        for c in companies:
            existing_stock_codes.add(c['stock_code'])
            existing_stock_codes.add(c['stock_code'].zfill(6))

    print(f'기존 KOSPI 기업: {len(industry_data["companies"])} 업종, '
          f'{sum(len(v) for v in industry_data["companies"].values())}개')

    # 2. KOSPI/KOSDAQ 기업에 market 필드 추가 (없으면 KOSPI 기본값)
    updated = 0
    for companies in industry_data['companies'].values():
        for c in companies:
            if 'market' not in c:
                c['market'] = 'KOSPI'
                updated += 1
    print(f'KOSPI market 필드 추가: {updated}개')

    # 3. FinanceDataReader로 KOSPI + KOSDAQ 전체 종목 취득
    print('\nFinanceDataReader로 종목 정보 수집 중...')
    try:
        kospi_df  = fdr.StockListing('KOSPI')
        kosdaq_df = fdr.StockListing('KOSDAQ')
    except Exception as e:
        print(f'오류: {e}')
        sys.exit(1)

    print(f'  KOSPI: {len(kospi_df)}개, KOSDAQ: {len(kosdaq_df)}개')

    # 컬럼명 통일 (버전에 따라 다를 수 있음)
    def normalize_cols(df, market):
        col_map = {}
        cols = [c.lower() for c in df.columns]
        # Symbol / Code
        for cand in ['symbol','code','종목코드']:
            if cand in cols:
                col_map['code'] = df.columns[cols.index(cand)]; break
        # Name
        for cand in ['name','종목명','회사명']:
            if cand in cols:
                col_map['name'] = df.columns[cols.index(cand)]; break
        # Industry / Sector
        for cand in ['industry','sector','업종','industrycode','sectorcode']:
            if cand in cols:
                col_map['industry'] = df.columns[cols.index(cand)]; break
        # IndustryCode
        for cand in ['industrycode','sectorcode','업종코드']:
            if cand in cols:
                col_map['industry_code'] = df.columns[cols.index(cand)]; break

        print(f'  [{market}] 컬럼: {list(df.columns[:10])} → 매핑: {col_map}')
        return col_map

    kospi_cols  = normalize_cols(kospi_df, 'KOSPI')
    kosdaq_cols = normalize_cols(kosdaq_df, 'KOSDAQ')

    # 4. DART corp_code 매핑 로드
    corp_code_map = get_dart_corp_code_map()
    dart_mapping  = download_corpcode_xml()
    if dart_mapping:
        corp_code_map.update(dart_mapping)

    # 5. KOSDAQ 기업 추가
    #    industry_data.json의 기존 업종 이름으로 매핑 (업종명 기준)
    # KRX 업종명 → 우리 업종코드 역방향 매핑 (정확 일치 + 부분 일치)
    industry_name_map = {}  # 업종명(소문자, 공백제거) → code
    for ind in industry_data['industries']:
        key = ind['name'].replace(' ', '').replace('·', '').replace(';', '').lower()
        industry_name_map[key] = ind['code']

    def find_industry_code(ind_name_raw, ind_code_raw=None):
        """FDR 업종명/코드로 우리 industry_data의 코드를 찾음"""
        # 1) 코드 직접 매핑 (FDR 업종코드가 우리 코드와 같을 경우)
        if ind_code_raw:
            code_str = str(ind_code_raw).strip()
            if code_str in existing_industry_codes:
                return code_str

        # 2) 이름 완전 일치
        if ind_name_raw:
            key = str(ind_name_raw).replace(' ', '').replace('·', '').replace(';', '').lower()
            if key in industry_name_map:
                return industry_name_map[key]

            # 3) 부분 포함 일치 (우리 업종명이 FDR 업종명을 포함하거나 vice versa)
            for stored_key, code in industry_name_map.items():
                if stored_key in key or key in stored_key:
                    return code

        return None

    added = 0
    new_industries_added = {}

    code_col  = kosdaq_cols.get('code')
    name_col  = kosdaq_cols.get('name')
    ind_col   = kosdaq_cols.get('industry')
    indc_col  = kosdaq_cols.get('industry_code')

    if not code_col:
        print('오류: KOSDAQ 종목코드 컬럼을 찾을 수 없습니다.')
        print(f'사용 가능한 컬럼: {list(kosdaq_df.columns)}')
        sys.exit(1)

    for _, row in kosdaq_df.iterrows():
        sc_raw  = str(row[code_col]).strip().zfill(6)
        sc      = sc_raw.lstrip('0') or sc_raw
        co_name = str(row[name_col]).strip() if name_col else sc

        if sc in existing_stock_codes or sc_raw in existing_stock_codes:
            continue  # 이미 존재 (KOSPI)

        ind_name = str(row[ind_col]).strip() if ind_col and ind_col in row.index else ''
        ind_code_fdr = str(row[indc_col]).strip() if indc_col and indc_col in row.index else ''

        matched_code = find_industry_code(ind_name, ind_code_fdr)
        if not matched_code:
            # 업종 없으면 새 업종으로 추가
            if ind_name and ind_code_fdr:
                if ind_code_fdr not in industry_data['companies']:
                    industry_data['industries'].append({
                        'code': ind_code_fdr,
                        'name': ind_name,
                    })
                    industry_data['companies'][ind_code_fdr] = []
                    existing_industry_codes.add(ind_code_fdr)
                    new_industries_added[ind_code_fdr] = ind_name
                matched_code = ind_code_fdr
            else:
                continue

        # 중복 확인 후 추가
        group = industry_data['companies'].setdefault(matched_code, [])
        if any(c['stock_code'] == sc for c in group):
            continue

        # industry_name 구하기
        ind_info = next((i for i in industry_data['industries'] if i['code'] == matched_code), None)
        ind_nm = ind_info['name'] if ind_info else ind_name

        group.append({
            'stock_code':    sc,
            'name':          co_name,
            'industry_code': matched_code,
            'industry_name': ind_nm,
            'market':        'KOSDAQ',
        })

        # corp_code_map에도 추가
        corp_code = corp_code_map.get(sc) or corp_code_map.get(sc_raw)
        if not corp_code:
            # 없으면 DART에서 나중에 가져올 수 있도록 빈값은 남기지 않음
            pass

        added += 1

    print(f'\nKOSDAQ 추가: {added}개')
    if new_industries_added:
        print(f'새 업종 {len(new_industries_added)}개 추가:')
        for code, name in list(new_industries_added.items())[:10]:
            print(f'  {code}: {name}')

    # 6. industries 정렬
    industry_data['industries'] = sorted(
        industry_data['industries'], key=lambda x: x['name']
    )

    # 7. 저장
    with open(INDUSTRY_DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(industry_data, f, ensure_ascii=False, indent=2)
    print(f'\nindustry_data.json 저장 완료')

    with open(CORP_CODE_MAP_PATH, 'w', encoding='utf-8') as f:
        json.dump(corp_code_map, f, ensure_ascii=False)
    print(f'corp_code_map.json 저장 완료')

    # 8. 통계
    total  = sum(len(v) for v in industry_data['companies'].values())
    kospi  = sum(1 for v in industry_data['companies'].values()
                 for c in v if c.get('market','KOSPI') == 'KOSPI')
    kosdaq = sum(1 for v in industry_data['companies'].values()
                 for c in v if c.get('market') == 'KOSDAQ')
    print(f'\n최종 통계:')
    print(f'  전체 기업: {total}개')
    print(f'  KOSPI: {kospi}개')
    print(f'  KOSDAQ: {kosdaq}개')
    print(f'  업종 수: {len(industry_data["industries"])}개')
    print('\n완료!')


if __name__ == '__main__':
    main()
