#!/usr/bin/env python3
"""
DART 재무데이터 수집 스크립트 (fnlttSinglAcntAll 버전 - 별도기준)
Usage: python scripts/fetch_dart_data.py [year] [quarter]
  year:    연도 (예: 2024)  기본값: 전년도
  quarter: annual / Q1 / Q2 / Q3 / Q4  기본값: annual
"""
import json, os, sys, time, requests
from datetime import datetime, date

DART_API_KEY = os.environ.get('DART_API_KEY', '')
DART_BASE = 'https://opendart.fss.or.kr/api'

REPRT_CODE = {
    'Q1': '11013',
    'Q2': '11012',
    'Q3': '11014',
    'Q4': '11011',
    'annual': '11011',
}

def parse_num(s):
    if not s:
        return 0
    try:
        return int(str(s).replace(',', '').strip())
    except Exception:
        return 0

def fetch_single_all(corp_code, year, reprt_code, retry=2):
    """
    fnlttSinglAcntAll: 단일회사 전체 재무제표 조회
    OFS(별도) 우선 시도 → 없으면 CFS(연결) 폴백
    반환: (rows, fs_div_used)
    """
    url = f'{DART_BASE}/fnlttSinglAcntAll.json'

    for fs_div in ['OFS', 'CFS']:
        params = {
            'crtfc_key': DART_API_KEY,
            'corp_code': corp_code,
            'bsns_year': year,
            'reprt_code': reprt_code,
            'fs_div': fs_div,
        }
        for attempt in range(retry + 1):
            try:
                resp = requests.get(url, params=params, timeout=30)
                data = resp.json()
                status = data.get('status')
                if status == '000':
                    rows = data.get('list', [])
                    if rows:
                        return rows, fs_div
                    break  # 빈 결과 → 다음 fs_div 시도
                elif status in ('013', '020'):
                    # 013: 조회 데이터 없음, 020: 요청 제한
                    break
                # 그 외 오류는 재시도
                if attempt < retry:
                    time.sleep(1)
            except Exception as e:
                if attempt < retry:
                    time.sleep(2)
                else:
                    break
        # OFS 실패 시 CFS로 계속

    return [], None

def extract_metrics(stock_code, corp_code, rows):
    """IS(손익계산서) 항목에서 필요한 지표 추출"""
    is_rows = [r for r in rows if r.get('sj_div') in ('IS', 'CIS')]

    def get(keywords):
        for kw in keywords:
            for row in is_rows:
                nm = row.get('account_nm', '').replace(' ', '')
                if kw in nm:
                    return {
                        'current': parse_num(row.get('thstrm_amount')),
                        'prev': parse_num(row.get('frmtrm_amount')),
                    }
        return {'current': 0, 'prev': 0}

    rev    = get(['매출액', '수익(매출액)', '영업수익'])
    cogs   = get(['매출원가'])
    sga    = get(['판매비와관리비', '판매비및관리비', '판매관리비', '판매비및일반관리비'])
    op     = get(['영업이익(손실)', '영업이익'])
    pretax = get(['법인세비용차감전순이익(손실)', '법인세차감전순이익', '법인세차감전당기순이익'])
    net    = get(['당기순이익(손실)', '당기순이익'])

    r  = rev['current']
    pr = rev['prev']
    growth = round((r - pr) / abs(pr) * 100, 2) if pr else 0

    return {
        'stockCode':        stock_code,
        'corpCode':         corp_code,
        'revenue':          r,
        'prevRevenue':      pr,
        'revenueGrowth':    growth,
        'cogs':             cogs['current'],
        'prevCogs':         cogs['prev'],
        'cogsRate':         round(cogs['current'] / r * 100, 2) if r else 0,
        'sga':              sga['current'],
        'prevSga':          sga['prev'],
        'sgaRate':          round(sga['current'] / r * 100, 2) if r else 0,
        'opIncome':         op['current'],
        'prevOpIncome':     op['prev'],
        'opMargin':         round(op['current'] / r * 100, 2) if r else 0,
        'pretaxIncome':     pretax['current'],
        'prevPretaxIncome': pretax['prev'],
        'netIncome':        net['current'],
        'prevNetIncome':    net['prev'],
        'netMargin':        round(net['current'] / r * 100, 2) if r else 0,
    }

QUARTER_LABELS = {
    'annual': '연간',
    'Q1': '1분기',
    'Q2': '상반기',
    'Q3': '3분기(누적)',
}

PREV_QUARTER_LABELS = {
    'annual': '연간',
    'Q1': '1분기',
    'Q2': '상반기',
    'Q3': '3분기',
}

def auto_detect_periods():
    """현재 날짜 기준으로 수집할 연도/분기 자동 결정"""
    today = date.today()
    year  = today.year
    prev  = year - 1
    periods = []

    # 전년도 전체 분기
    periods.append((str(prev), 'annual'))
    periods.append((str(prev), 'Q1'))
    periods.append((str(prev), 'Q2'))
    periods.append((str(prev), 'Q3'))

    # 당해연도 분기 (공시 일정 기준)
    if today.month >= 4:
        periods.append((str(year), 'annual'))
    if today.month >= 5:
        periods.append((str(year), 'Q1'))
    if today.month >= 8:
        periods.append((str(year), 'Q2'))
    if today.month >= 11:
        periods.append((str(year), 'Q3'))

    return periods


def build_manifest(data_dir):
    """수집된 파일 목록으로 manifest.json 생성"""
    import re
    periods = []
    for fname in sorted(os.listdir(data_dir), reverse=True):
        m = re.match(r'financial_(\d{4})_(annual|Q1|Q2|Q3|Q4)\.json', fname)
        if not m:
            continue
        year, quarter = m.group(1), m.group(2)
        q_label  = QUARTER_LABELS.get(quarter, quarter)
        pq_label = PREV_QUARTER_LABELS.get(quarter, '전기')
        periods.append({
            'key':       f'{year}_{quarter}',
            'year':      year,
            'quarter':   quarter,
            'label':     f'{year}년 {q_label}',
            'prevLabel': f'{int(year)-1}년 {pq_label} 대비',
        })

    manifest = {
        'updated_at': datetime.now().strftime('%Y-%m-%d'),
        'latest':     periods[0]['key'] if periods else None,
        'periods':    periods,
    }
    manifest_path = os.path.join(data_dir, 'manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f'manifest.json 업데이트: {len(periods)}개 기간')


def main():
    if not DART_API_KEY:
        print('오류: DART_API_KEY 환경변수가 없습니다.')
        sys.exit(1)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 수집 대상 결정
    if len(sys.argv) >= 3:
        periods = [(sys.argv[1], sys.argv[2])]
    elif len(sys.argv) == 2:
        periods = [(sys.argv[1], 'annual')]
    else:
        periods = auto_detect_periods()

    print(f'수집 대상: {periods}')

    # 매핑 로드
    with open(os.path.join(base_dir, 'industry_data.json'), encoding='utf-8') as f:
        industry_data = json.load(f)
    with open(os.path.join(base_dir, 'api-worker', 'corp_code_map.json'), encoding='utf-8') as f:
        corp_code_map = json.load(f)

    # stock_code → corp_code 매핑
    all_stock_codes = set()
    for companies in industry_data['companies'].values():
        for c in companies:
            all_stock_codes.add(c['stock_code'])

    stock_to_corp = {}
    for sc in all_stock_codes:
        cc = corp_code_map.get(sc) or corp_code_map.get(sc.zfill(6))
        if cc:
            stock_to_corp[sc] = cc

    total = len(stock_to_corp)
    print(f'총 {len(all_stock_codes)}개 기업, corp_code 매핑 {total}개')
    print(f'fnlttSinglAcntAll 방식: 회사별 개별 조회 (OFS 우선 → CFS 폴백)')
    est_min = round(total * 0.35 / 60, 1)
    print(f'예상 소요시간: 약 {est_min}분\n')

    os.makedirs(os.path.join(base_dir, 'data'), exist_ok=True)

    for year, quarter in periods:
        output_path = os.path.join(base_dir, 'data', f'financial_{year}_{quarter}.json')

        if os.path.exists(output_path):
            print(f'이미 존재, 건너뜀: {output_path}')
            continue

        print(f'[{year} {quarter}] 데이터 수집 시작...')
        reprt_code = REPRT_CODE.get(quarter, '11011')

        companies_result = {}
        ofs_count = 0
        cfs_count = 0
        empty_count = 0

        items = list(stock_to_corp.items())
        for idx, (sc, cc) in enumerate(items):
            if (idx + 1) % 50 == 0 or (idx + 1) == total:
                print(f'  [{idx+1}/{total}] OFS:{ofs_count} CFS:{cfs_count} 데이터없음:{empty_count}')

            rows, fs_used = fetch_single_all(cc, year, reprt_code)
            companies_result[sc] = extract_metrics(sc, cc, rows)

            if fs_used == 'OFS':
                ofs_count += 1
            elif fs_used == 'CFS':
                cfs_count += 1
            else:
                empty_count += 1

            # rate limit 방지: 0.3초 대기
            time.sleep(0.3)

        non_zero = sum(1 for m in companies_result.values() if m['revenue'] > 0)
        has_cogs  = sum(1 for m in companies_result.values() if m['cogs'] > 0)
        has_sga   = sum(1 for m in companies_result.values() if m['sga'] > 0)
        print(f'  완료: {total}개 중 매출 {non_zero}개 / 매출원가 {has_cogs}개 / 판관비 {has_sga}개 실데이터')
        print(f'  기준: OFS(별도) {ofs_count}개, CFS(연결) {cfs_count}개, 없음 {empty_count}개')

        output = {
            'updated_at': datetime.now().strftime('%Y-%m-%d'),
            'year':       year,
            'quarter':    quarter,
            'companies':  companies_result,
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False)

        print(f'  저장 완료: {output_path}\n')

    # manifest.json 갱신
    build_manifest(os.path.join(base_dir, 'data'))
    print('\n완료!')


if __name__ == '__main__':
    main()
