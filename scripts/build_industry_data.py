#!/usr/bin/env python3
"""
KOSDAQ 기업 추가 스크립트 v4 (DART 코드 매핑 방식)

Step 1: FDR로 KOSDAQ 종목 목록 수집
Step 2: 기존 KOSPI 기업 1개/업종 × 58업종 → DART induty_code 조회
        → DART코드 → 우리업종코드 매핑 테이블 구축
Step 3: KOSDAQ 기업별 DART induty_code 조회 → 매핑 테이블로 우리 업종 결정
Step 4: industry_data.json, corp_code_map.json 저장
"""
import json, os, sys, time, requests

DART_API_KEY = os.environ.get('DART_API_KEY', '')
DART_BASE    = 'https://opendart.fss.or.kr/api'
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INDUSTRY_DATA_PATH = os.path.join(BASE_DIR, 'industry_data.json')
CORP_CODE_MAP_PATH = os.path.join(BASE_DIR, 'api-worker', 'corp_code_map.json')


def fetch_company_info(corp_code, retry=2):
    for attempt in range(retry + 1):
        try:
            r = requests.get(f'{DART_BASE}/company.json',
                params={'crtfc_key': DART_API_KEY, 'corp_code': corp_code},
                timeout=15)
            d = r.json()
            if d.get('status') == '000':
                return d
            if attempt < retry:
                time.sleep(1)
        except Exception:
            if attempt < retry:
                time.sleep(2)
    return None


def build_corp_code_map_from_dart(corp_map):
    """CORPCODE.xml로 stock_code→corp_code 보완"""
    import zipfile, io
    from xml.etree import ElementTree as ET
    print('DART CORPCODE.xml 다운로드...')
    r = requests.get(f'{DART_BASE}/corpCode.xml',
                     params={'crtfc_key': DART_API_KEY}, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        xml = zf.read([n for n in zf.namelist() if n.endswith('.xml')][0])
    root = ET.fromstring(xml)
    added = 0
    for item in root.findall('list'):
        cc = (item.findtext('corp_code') or '').strip()
        sc = (item.findtext('stock_code') or '').strip()
        if cc and sc:
            sc_strip = sc.lstrip('0') or sc
            if sc not in corp_map:
                corp_map[sc] = cc
                added += 1
            if sc_strip not in corp_map:
                corp_map[sc_strip] = cc
                added += 1
    print(f'  매핑 추가: {added}개 → 총 {len(corp_map)}개')


def main():
    if not DART_API_KEY:
        print('오류: DART_API_KEY 환경변수가 없습니다.')
        sys.exit(1)

    try:
        import FinanceDataReader as fdr
    except ImportError:
        print('pip install finance-datareader  후 재실행')
        sys.exit(1)

    # ── 데이터 로드 ──────────────────────────────
    with open(INDUSTRY_DATA_PATH, encoding='utf-8') as f:
        ind = json.load(f)
    with open(CORP_CODE_MAP_PATH, encoding='utf-8') as f:
        corp_map = json.load(f)

    existing_codes = {i['code'] for i in ind['industries']}
    existing_sc    = set()
    for companies in ind['companies'].values():
        for c in companies:
            c.setdefault('market', 'KOSPI')
            existing_sc.add(c['stock_code'])
            existing_sc.add(c['stock_code'].zfill(6))

    total_before = sum(len(v) for v in ind['companies'].values())
    print(f'기존: {len(existing_codes)}개 업종, {total_before}개 기업')

    # ── CORPCODE.xml 보완 ─────────────────────────
    build_corp_code_map_from_dart(corp_map)

    # ── Step 2: KOSPI 기업으로 DART→우리코드 매핑 구축 ────
    print(f'\n[Step 2] KOSPI 기업으로 DART induty_code 매핑 구축 ({len(existing_codes)}개 업종)...')
    dart_to_ours = {}   # dart_induty_code(str) → our_ind_code(str)

    for our_code, companies in ind['companies'].items():
        mapped = False
        for c in companies[:5]:   # 최대 5개 시도
            sc = c['stock_code']
            cc = corp_map.get(sc) or corp_map.get(sc.zfill(6))
            if not cc:
                continue
            info = fetch_company_info(cc)
            time.sleep(0.25)
            if not info:
                continue
            dart_code = str(info.get('induty_code') or '').strip()
            if not dart_code:
                continue
            # 정확한 코드 매핑
            dart_to_ours[dart_code] = our_code
            # 앞 3~4자리 prefix 매핑 (같은 대분류 KOSDAQ 기업 포괄)
            for plen in (4, 3, 2):
                if len(dart_code) > plen:
                    dart_to_ours.setdefault(dart_code[:plen], our_code)
            mapped = True
            break
        if not mapped:
            print(f'  매핑 실패: {our_code} ({c["industry_name"][:20]})')

    print(f'  DART→우리코드 매핑 완성: {len(dart_to_ours)}개 항목')

    # ── Step 3: FDR로 KOSDAQ 목록 수집 ───────────────
    print('\n[Step 3] FDR로 KOSDAQ 종목 목록 수집...')
    kosdaq_df = fdr.StockListing('KOSDAQ')
    code_col  = next((c for c in kosdaq_df.columns
                      if c.lower() in ('code', 'symbol', '종목코드')), None)
    name_col  = next((c for c in kosdaq_df.columns
                      if c.lower() in ('name', '종목명', '회사명')), None)
    print(f'  KOSDAQ {len(kosdaq_df)}개')

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
    print(f'  신규 후보: {len(candidates)}개 (약 {round(len(candidates)*0.3/60,1)}분 예상)')

    # ── Step 4: KOSDAQ 기업별 DART 조회 + 매핑 ──────────
    print('\n[Step 4] KOSDAQ company.json 조회 중...')
    added    = 0
    no_corp  = 0
    no_match = 0
    new_inds = {}

    for idx, c in enumerate(candidates):
        if (idx + 1) % 200 == 0 or (idx + 1) == len(candidates):
            print(f'  [{idx+1}/{len(candidates)}] 추가:{added} 코드없음:{no_corp} 미매핑:{no_match}')

        cc = corp_map.get(c['sc']) or corp_map.get(c['sc_raw'])
        if not cc:
            no_corp += 1
            continue

        info = fetch_company_info(cc)
        time.sleep(0.3)
        if not info:
            no_corp += 1
            continue

        dart_code = str(info.get('induty_code') or '').strip()
        corp_name = (info.get('corp_name') or c['name']).strip()

        if not dart_code:
            no_match += 1
            continue

        # 매핑: 정확→4자리prefix→3자리prefix→2자리prefix
        our_code = dart_to_ours.get(dart_code)
        for plen in (4, 3, 2):
            if our_code:
                break
            if len(dart_code) > plen:
                our_code = dart_to_ours.get(dart_code[:plen])

        if not our_code:
            # 신규 업종 생성
            induty_nm = (info.get('induty_nm') or '').strip() or dart_code
            if dart_code not in ind['companies']:
                ind['industries'].append({'code': dart_code, 'name': induty_nm})
                ind['companies'][dart_code] = []
                existing_codes.add(dart_code)
                dart_to_ours[dart_code] = dart_code
                new_inds[dart_code] = induty_nm
            our_code = dart_code

        # 중복 확인 후 추가
        group = ind['companies'].setdefault(our_code, [])
        if any(x['stock_code'] == c['sc'] for x in group):
            continue

        ind_nm = next((i['name'] for i in ind['industries'] if i['code'] == our_code), our_code)
        group.append({
            'stock_code':    c['sc'],
            'name':          corp_name,
            'industry_code': our_code,
            'industry_name': ind_nm,
            'market':        'KOSDAQ',
        })
        added += 1

    # ── 저장 ──────────────────────────────────────
    ind['industries'] = sorted(ind['industries'], key=lambda x: x['name'])

    with open(INDUSTRY_DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(ind, f, ensure_ascii=False, indent=2)
    with open(CORP_CODE_MAP_PATH, 'w', encoding='utf-8') as f:
        json.dump(corp_map, f, ensure_ascii=False)

    total_after = sum(len(v) for v in ind['companies'].values())
    kp  = sum(1 for v in ind['companies'].values() for x in v if x.get('market', 'KOSPI') == 'KOSPI')
    kq  = sum(1 for v in ind['companies'].values() for x in v if x.get('market') == 'KOSDAQ')

    print(f'\n저장 완료')
    if new_inds:
        print(f'신규 업종 {len(new_inds)}개: {list(new_inds.values())[:5]}')
    print(f'\n최종: 전체 {total_after}개 | KOSPI {kp} | KOSDAQ {kq} | 업종 {len(ind["industries"])}개')
    print('완료!')


if __name__ == '__main__':
    main()
