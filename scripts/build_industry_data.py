#!/usr/bin/env python3
"""
KOSDAQ 기업 추가 스크립트 (하이브리드: FDR 목록 + DART 업종명 매핑)

Step 1: FDR로 KOSDAQ 전체 종목 코드+이름 수집 (API 불필요, 수초)
Step 2: 기존 KOSPI 기업 1개/업종씩 DART company.json → induty_nm 수집 (58회)
Step 3: KOSDAQ 기업별 DART company.json → induty_nm → 우리 업종코드 매핑 (~1800회)
Step 4: industry_data.json 업데이트

Usage:
  set DART_API_KEY=<키>
  cd Desktop\\pl-data
  python scripts/build_industry_data.py
"""
import json, os, sys, time, requests

DART_API_KEY = os.environ.get('DART_API_KEY', '')
DART_BASE    = 'https://opendart.fss.or.kr/api'

BASE_DIR          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDUSTRY_DATA_PATH = os.path.join(BASE_DIR, 'industry_data.json')
CORP_CODE_MAP_PATH = os.path.join(BASE_DIR, 'api-worker', 'corp_code_map.json')


# ──────────────────────────────────────────────
# DART company.json 호출
# ──────────────────────────────────────────────
def fetch_company_info(corp_code, retry=2):
    url    = f'{DART_BASE}/company.json'
    params = {'crtfc_key': DART_API_KEY, 'corp_code': corp_code}
    for attempt in range(retry + 1):
        try:
            r    = requests.get(url, params=params, timeout=15)
            data = r.json()
            if data.get('status') == '000':
                return data
            if attempt < retry:
                time.sleep(1)
        except Exception:
            if attempt < retry:
                time.sleep(2)
    return None


# ──────────────────────────────────────────────
# induty_nm 키워드 → 우리 업종코드 사전
# (DART induty_nm은 짧은 한국어 명칭)
# ──────────────────────────────────────────────
KW_MAP = [
    # (검색 키워드, 우리 업종코드)
    ('의약품',      '32100'),
    ('의료기기',    '32700'),
    ('정밀기기',    '32700'),
    ('광학기기',    '32700'),
    ('전기전자',    '32600'),
    ('전자부품',    '32600'),
    ('반도체',      '32600'),
    ('통신장비',    '32600'),
    ('컴퓨터',      '32600'),
    ('전기장비',    '32800'),
    ('전기기계',    '32800'),
    ('자동차',      '33000'),
    ('트레일러',    '33000'),
    ('기타운송',    '33100'),
    ('조선',        '33100'),
    ('항공기',      '33100'),
    ('기계',        '32900'),
    ('산업기계',    '32900'),
    ('1차금속',     '32400'),
    ('철강',        '32400'),
    ('비철금속',    '32400'),
    ('금속가공',    '32500'),
    ('화학물질',    '32000'),
    ('화학제품',    '32000'),
    ('기초화학',    '32000'),
    ('플라스틱',    '32200'),
    ('고무',        '32200'),
    ('비금속광물',  '32300'),
    ('석유',        '31900'),
    ('코크스',      '31900'),
    ('섬유',        '31300'),
    ('의복',        '31400'),
    ('모피',        '31400'),
    ('가죽',        '31500'),
    ('가방',        '31500'),
    ('신발',        '31500'),
    ('식료품',      '31000'),
    ('음료',        '31100'),
    ('담배',        '31200'),
    ('목재',        '31600'),
    ('나무',        '31600'),
    ('펄프',        '31700'),
    ('종이',        '31700'),
    ('인쇄',        '31800'),
    ('가구',        '33200'),
    ('기타제품',    '33300'),
    ('소프트웨어',  '106200'),
    ('프로그래밍',  '106200'),
    ('시스템통합',  '106200'),
    ('정보서비스',  '106300'),
    ('데이터베이스','106300'),
    ('통신',        '106100'),
    ('방송',        '106000'),
    ('영상',        '105900'),
    ('음향',        '105900'),
    ('출판',        '105800'),
    ('연구개발',    '137000'),
    ('전문서비스',  '137100'),
    ('엔지니어링',  '137200'),
    ('건축기술',    '137200'),
    ('종합건설',    '64100'),
    ('전문건설',    '64200'),
    ('도매',        '74600'),
    ('소매',        '74700'),
    ('자동차판매',  '74500'),
    ('육상운송',    '84900'),
    ('항공운송',    '85100'),
    ('수상운송',    '85000'),
    ('창고',        '85200'),
    ('운송관련',    '85200'),
    ('숙박',        '95500'),
    ('음식점',      '95600'),
    ('주점',        '95600'),
    ('부동산',      '126800'),
    ('임대',        '147600'),
    ('사업지원',    '147500'),
    ('교육',        '168500'),
    ('스포츠',      '189100'),
    ('오락',        '189100'),
    ('은행',        '116501'),
    ('여신금융',    '117101'),
    ('증권',        '116701'),
    ('보험',        '116601'),
    ('기타금융',    '117201'),
    ('어업',        '10300'),
    ('광업',        '20000'),
    ('전기가스',    '43500'),
    ('수도',        '44000'),
]


def induty_nm_to_code(induty_nm, existing_codes):
    """DART induty_nm → 우리 업종코드 반환. 없으면 None"""
    nm = induty_nm.replace(' ', '')
    for kw, code in KW_MAP:
        if code in existing_codes and kw in nm:
            return code
    return None


# ──────────────────────────────────────────────
# CORPCODE.xml 다운로드 (stock_code → corp_code)
# ──────────────────────────────────────────────
def build_corp_code_map_from_dart():
    import zipfile, io
    from xml.etree import ElementTree as ET
    if not DART_API_KEY:
        return {}
    print('  DART CORPCODE.xml 다운로드...')
    r = requests.get(f'{DART_BASE}/corpCode.xml',
                     params={'crtfc_key': DART_API_KEY}, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        xml = zf.read([n for n in zf.namelist() if n.endswith('.xml')][0])
    root    = ET.fromstring(xml)
    mapping = {}
    for item in root.findall('list'):
        cc = (item.findtext('corp_code') or '').strip()
        sc = (item.findtext('stock_code') or '').strip()
        if cc and sc:
            mapping[sc]                          = cc
            mapping[sc.lstrip('0') or sc]        = cc
    print(f'  CORPCODE 매핑: {len(mapping)}개')
    return mapping


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────
def main():
    if not DART_API_KEY:
        print('오류: DART_API_KEY 환경변수가 없습니다.')
        print('  set DART_API_KEY=<키>  후 재실행하세요.')
        sys.exit(1)

    try:
        import FinanceDataReader as fdr
    except ImportError:
        print('pip install finance-datareader')
        sys.exit(1)

    # 1. 기존 industry_data 로드
    with open(INDUSTRY_DATA_PATH, encoding='utf-8') as f:
        ind_data = json.load(f)
    with open(CORP_CODE_MAP_PATH, encoding='utf-8') as f:
        corp_map = json.load(f)

    existing_ind_codes = {i['code'] for i in ind_data['industries']}
    existing_sc        = set()
    for companies in ind_data['companies'].values():
        for c in companies:
            existing_sc.add(c['stock_code'])
            existing_sc.add(c['stock_code'].zfill(6))

    kospi_count = sum(len(v) for v in ind_data['companies'].values())
    print(f'기존: {len(existing_ind_codes)}개 업종, {kospi_count}개 기업')

    # market 필드 추가 (없으면 KOSPI)
    for companies in ind_data['companies'].values():
        for c in companies:
            c.setdefault('market', 'KOSPI')

    # 2. CORPCODE.xml로 매핑 보완
    dart_map = build_corp_code_map_from_dart()
    corp_map.update(dart_map)

    # 3. FDR로 KOSDAQ 기업 목록 취득
    print('\nFDR로 KOSDAQ 종목 목록 수집 중...')
    kosdaq_df  = fdr.StockListing('KOSDAQ')
    code_col   = next((c for c in kosdaq_df.columns if c.lower() in ('code','symbol','종목코드')), None)
    name_col   = next((c for c in kosdaq_df.columns if c.lower() in ('name','종목명','회사명')), None)
    if not code_col:
        print('종목코드 컬럼을 찾을 수 없습니다. 컬럼:', list(kosdaq_df.columns))
        sys.exit(1)
    print(f'  KOSDAQ {len(kosdaq_df)}개')

    # 신규 KOSDAQ 후보만 필터
    candidates = []
    for _, row in kosdaq_df.iterrows():
        sc_raw = str(row[code_col]).strip().zfill(6)
        sc     = sc_raw.lstrip('0') or sc_raw
        if sc not in existing_sc and sc_raw not in existing_sc:
            candidates.append({
                'sc':     sc,
                'sc_raw': sc_raw,
                'name':   str(row[name_col]).strip() if name_col else sc,
            })
    print(f'  신규 KOSDAQ 후보: {len(candidates)}개')

    # 4. company.json 조회 → induty_nm → 업종코드 매핑
    print(f'\nDART company.json 조회 시작 (약 {round(len(candidates)*0.35/60,1)}분 예상)...')
    added       = 0
    no_corp     = 0
    no_match    = 0
    new_inds    = {}

    for idx, c in enumerate(candidates):
        if (idx + 1) % 200 == 0 or (idx + 1) == len(candidates):
            print(f'  [{idx+1}/{len(candidates)}] 추가:{added} 코드없음:{no_corp} 업종불일치:{no_match}')

        # corp_code 조회
        corp_code = corp_map.get(c['sc']) or corp_map.get(c['sc_raw'])
        if not corp_code:
            no_corp += 1
            continue

        # DART company.json 호출
        info = fetch_company_info(corp_code)
        time.sleep(0.3)
        if not info:
            no_corp += 1
            continue

        induty_nm   = (info.get('induty_nm') or '').strip()
        induty_code = str(info.get('induty_code') or '').strip()
        corp_name   = (info.get('corp_name') or c['name']).strip()

        if not induty_nm:
            no_match += 1
            continue

        # 우리 업종코드 매핑
        matched = induty_nm_to_code(induty_nm, existing_ind_codes)

        if not matched:
            # 새 업종 생성 (induty_code + induty_nm 기반)
            key = induty_code or induty_nm[:10]
            if key and key not in ind_data['companies']:
                ind_data['industries'].append({'code': key, 'name': induty_nm})
                ind_data['companies'][key] = []
                existing_ind_codes.add(key)
                new_inds[key] = induty_nm
            matched = key if key else None

        if not matched:
            no_match += 1
            continue

        # 중복 확인 후 추가
        group = ind_data['companies'].setdefault(matched, [])
        if any(x['stock_code'] == c['sc'] for x in group):
            continue

        ind_nm = next((i['name'] for i in ind_data['industries'] if i['code'] == matched), induty_nm)
        group.append({
            'stock_code':    c['sc'],
            'name':          corp_name,
            'industry_code': matched,
            'industry_name': ind_nm,
            'market':        'KOSDAQ',
        })
        added += 1

    print(f'\nKOSDAQ 추가 완료: {added}개')
    if new_inds:
        print(f'새 업종 {len(new_inds)}개:')
        for code, nm in list(new_inds.items())[:10]:
            print(f'  {code}: {nm}')

    # 5. industries 정렬
    ind_data['industries'] = sorted(ind_data['industries'], key=lambda x: x['name'])

    # 6. 저장
    with open(INDUSTRY_DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(ind_data, f, ensure_ascii=False, indent=2)
    with open(CORP_CODE_MAP_PATH, 'w', encoding='utf-8') as f:
        json.dump(corp_map, f, ensure_ascii=False)
    print('industry_data.json / corp_code_map.json 저장 완료')

    # 7. 통계
    total  = sum(len(v) for v in ind_data['companies'].values())
    kp     = sum(1 for v in ind_data['companies'].values()
                 for x in v if x.get('market', 'KOSPI') == 'KOSPI')
    kq     = sum(1 for v in ind_data['companies'].values()
                 for x in v if x.get('market') == 'KOSDAQ')
    print(f'\n최종: 전체 {total}개 | KOSPI {kp}개 | KOSDAQ {kq}개 | 업종 {len(ind_data["industries"])}개')
    print('완료!')


if __name__ == '__main__':
    main()
