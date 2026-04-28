#!/usr/bin/env python3
"""
DART 재무데이터 수집 스크립트
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

def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def parse_num(s):
    if not s:
        return 0
    try:
        return int(str(s).replace(',', '').strip())
    except Exception:
        return 0

def fetch_multi(corp_codes, year, reprt_code, retry=2):
    url = f'{DART_BASE}/fnlttMultiAcnt.json'
    params = {
        'crtfc_key': DART_API_KEY,
        'corp_code': ','.join(corp_codes),
        'bsns_year': year,
        'reprt_code': reprt_code,
    }
    for attempt in range(retry + 1):
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            if data.get('status') == '000':
                return data.get('list', [])
            print(f'  DART 응답 오류: {data.get("status")} {data.get("message")}')
            return []
        except Exception as e:
            if attempt < retry:
                time.sleep(2)
            else:
                print(f'  요청 실패: {e}')
                return []

def extract_metrics(stock_code, corp_code, rows):
    # 연결(CFS) 우선, 없으면 별도(OFS)
    cfs = [r for r in rows if r.get('fs_div') == 'CFS']
    target = cfs if cfs else rows
    is_rows = [r for r in target if r.get('sj_div') in ('IS', 'CIS')]

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

    rev = get(['매출액', '수익(매출액)', '영업수익'])
    cogs = get(['매출원가'])
    sga = get(['판매비와관리비', '판매비및관리비', '판매관리비'])
    op = get(['영업이익(손실)', '영업이익'])
    pretax = get(['법인세비용차감전순이익(손실)', '법인세차감전순이익'])
    net = get(['당기순이익(손실)', '당기순이익'])

    r = rev['current']
    pr = rev['prev']
    growth = round((r - pr) / abs(pr) * 100, 2) if pr else 0

    return {
        'stockCode': stock_code,
        'corpCode': corp_code,
        'revenue': r, 'prevRevenue': pr, 'revenueGrowth': growth,
        'cogs': cogs['current'], 'prevCogs': cogs['prev'],
        'cogsRate': round(cogs['current'] / r * 100, 2) if r else 0,
        'sga': sga['current'], 'prevSga': sga['prev'],
        'sgaRate': round(sga['current'] / r * 100, 2) if r else 0,
        'opIncome': op['current'], 'prevOpIncome': op['prev'],
        'opMargin': round(op['current'] / r * 100, 2) if r else 0,
        'pretaxIncome': pretax['current'], 'prevPretaxIncome': pretax['prev'],
        'netIncome': net['current'], 'prevNetIncome': net['prev'],
        'netMargin': round(net['current'] / r * 100, 2) if r else 0,
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
    year = today.year
    prev = year - 1
    periods = []

    # 전년도 전체 분기 (3월 이후 annual, 나머지는 이미 확정)
    periods.append((str(prev), 'annual'))
    periods.append((str(prev), 'Q1'))
    periods.append((str(prev), 'Q2'))
    periods.append((str(prev), 'Q3'))

    # 당해연도 분기 (공시 일정 기준)
    if today.month >= 5:
        periods.append((str(year), 'Q1'))
    if today.month >= 8:
        periods.append((str(year), 'Q2'))
    if today.month >= 11:
        periods.append((str(year), 'Q3'))
    if today.month >= 4:
        periods.append((str(year), 'annual'))

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
        q_label = QUARTER_LABELS.get(quarter, quarter)
        pq_label = PREV_QUARTER_LABELS.get(quarter, '전기')
        periods.append({
            'key': f'{year}_{quarter}',
            'year': year,
            'quarter': quarter,
            'label': f'{year}년 {q_label}',
            'prevLabel': f'{int(year)-1}년 {pq_label} 대비',
        })

    # 최신 기간 = periods[0] (역순 정렬이므로)
    manifest = {
        'updated_at': datetime.now().strftime('%Y-%m-%d'),
        'latest': periods[0]['key'] if periods else None,
        'periods': periods,
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

    # 전체 stock_code 수집
    all_stock_codes = set()
    for companies in industry_data['companies'].values():
        for c in companies:
            all_stock_codes.add(c['stock_code'])

    stock_to_corp = {}
    for sc in all_stock_codes:
        cc = corp_code_map.get(sc) or corp_code_map.get(sc.zfill(6))
        if cc:
            stock_to_corp[sc] = cc

    print(f'총 {len(all_stock_codes)}개 기업, corp_code 매핑 {len(stock_to_corp)}개')

    os.makedirs(os.path.join(base_dir, 'data'), exist_ok=True)

    for year, quarter in periods:
        output_path = os.path.join(base_dir, 'data', f'financial_{year}_{quarter}.json')

        if os.path.exists(output_path):
            print(f'이미 존재, 건너뜀: {output_path}')
            continue

        print(f'\n[{year} {quarter}] 데이터 수집 시작...')
        reprt_code = REPRT_CODE.get(quarter, '11011')

        corp_codes = list(stock_to_corp.values())
        all_rows = []
        batches = list(chunk(corp_codes, 100))
        for i, batch in enumerate(batches):
            print(f'  배치 {i+1}/{len(batches)} ({len(batch)}개)...')
            rows = fetch_multi(batch, year, reprt_code)
            all_rows.extend(rows)
            if i < len(batches) - 1:
                time.sleep(0.5)  # rate limit 방지

        print(f'  수신 rows: {len(all_rows)}')

        by_corp = {}
        for row in all_rows:
            cc = row.get('corp_code')
            by_corp.setdefault(cc, []).append(row)

        companies_result = {}
        for sc, cc in stock_to_corp.items():
            rows = by_corp.get(cc, [])
            companies_result[sc] = extract_metrics(sc, cc, rows)

        non_zero = sum(1 for m in companies_result.values() if m['revenue'] > 0)
        print(f'  결과: {len(companies_result)}개 중 {non_zero}개 실데이터')

        output = {
            'updated_at': datetime.now().strftime('%Y-%m-%d'),
            'year': year,
            'quarter': quarter,
            'companies': companies_result,
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False)

        print(f'  저장 완료: {output_path}')

    # manifest.json 항상 갱신
    build_manifest(os.path.join(base_dir, 'data'))
    print('\n완료!')

if __name__ == '__main__':
    main()
