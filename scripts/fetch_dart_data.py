#!/usr/bin/env python3
"""
DART 재무데이터 수집 스크립트 (병렬 버전 - ThreadPoolExecutor)
Usage: python scripts/fetch_dart_data.py [year] [quarter]
"""
import json, os, sys, time, requests, threading
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed

DART_API_KEY = os.environ.get('DART_API_KEY', '')
DART_BASE    = 'https://opendart.fss.or.kr/api'
WORKERS      = 5   # 동시 요청 수 (DART rate limit 고려)

REPRT_CODE = {
    'Q1': '11013', 'Q2': '11012', 'Q3': '11014',
    'Q4': '11011', 'annual': '11011',
}

_lock = threading.Lock()

def parse_num(s):
    if not s:
        return 0
    try:
        return int(str(s).replace(',', '').strip())
    except Exception:
        return 0


def fetch_single_all(corp_code, year, reprt_code, retry=1):
    """OFS 우선 → CFS 폴백. timeout 단축(15s), retry 1회"""
    url = f'{DART_BASE}/fnlttSinglAcntAll.json'
    for fs_div in ['OFS', 'CFS']:
        params = {
            'crtfc_key': DART_API_KEY,
            'corp_code':  corp_code,
            'bsns_year':  year,
            'reprt_code': reprt_code,
            'fs_div':     fs_div,
        }
        for attempt in range(retry + 1):
            try:
                resp = requests.get(url, params=params, timeout=15)
                data = resp.json()
                status = data.get('status')
                if status == '000':
                    rows = data.get('list', [])
                    if rows:
                        return rows, fs_div
                    break
                elif status in ('013', '020'):
                    break
                if attempt < retry:
                    time.sleep(0.5)
            except Exception:
                if attempt < retry:
                    time.sleep(1)
                else:
                    break
    return [], None


def fetch_one(args):
    """스레드 작업 단위: (sc, cc, year, reprt_code) → (sc, metrics, fs_used)"""
    sc, cc, year, reprt_code = args
    rows, fs_used = fetch_single_all(cc, year, reprt_code)
    metrics = extract_metrics(sc, cc, rows)
    return sc, metrics, fs_used


def extract_metrics(stock_code, corp_code, rows):
    is_rows = [r for r in rows if r.get('sj_div') in ('IS', 'CIS')]

    def get(keywords):
        for kw in keywords:
            for row in is_rows:
                nm = row.get('account_nm', '').replace(' ', '')
                if kw in nm:
                    return {
                        'current': parse_num(row.get('thstrm_amount')),
                        'prev':    parse_num(row.get('frmtrm_amount')),
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


QUARTER_LABELS      = {'annual':'연간','Q1':'1분기','Q2':'상반기','Q3':'3분기(누적)'}
PREV_QUARTER_LABELS = {'annual':'연간','Q1':'1분기','Q2':'상반기','Q3':'3분기'}


def build_manifest(data_dir):
    import re
    periods = []
    for fname in sorted(os.listdir(data_dir), reverse=True):
        m = re.match(r'financial_(\d{4})_(annual|Q1|Q2|Q3|Q4)\.json', fname)
        if not m:
            continue
        year, quarter = m.group(1), m.group(2)
        periods.append({
            'key':       f'{year}_{quarter}',
            'year':      year,
            'quarter':   quarter,
            'label':     f'{year}년 {QUARTER_LABELS.get(quarter, quarter)}',
            'prevLabel': f'{int(year)-1}년 {PREV_QUARTER_LABELS.get(quarter,"전기")} 대비',
        })
    manifest = {
        'updated_at': datetime.now().strftime('%Y-%m-%d'),
        'latest':     periods[0]['key'] if periods else None,
        'periods':    periods,
    }
    with open(os.path.join(data_dir, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f'manifest.json 업데이트: {len(periods)}개 기간')


def main():
    if not DART_API_KEY:
        print('오류: DART_API_KEY 환경변수가 없습니다.')
        sys.exit(1)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if len(sys.argv) >= 3:
        periods = [(sys.argv[1], sys.argv[2])]
    elif len(sys.argv) == 2:
        periods = [(sys.argv[1], 'annual')]
    else:
        periods = auto_detect_periods()

    print(f'수집 대상: {periods}')

    with open(os.path.join(base_dir, 'industry_data.json'), encoding='utf-8') as f:
        industry_data = json.load(f)
    with open(os.path.join(base_dir, 'api-worker', 'corp_code_map.json'), encoding='utf-8') as f:
        corp_code_map = json.load(f)

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
    est_min = round(total / WORKERS * 1.2 / 60, 1)
    print(f'총 {total}개 기업 | 동시 {WORKERS}개 요청 | 예상 약 {est_min}분/기간\n')

    os.makedirs(os.path.join(base_dir, 'data'), exist_ok=True)

    for year, quarter in periods:
        output_path = os.path.join(base_dir, 'data', f'financial_{year}_{quarter}.json')

        if os.path.exists(output_path):
            print(f'이미 존재, 건너뜀: {output_path}')
            continue

        print(f'[{year} {quarter}] 수집 시작...')
        reprt_code = REPRT_CODE.get(quarter, '11011')

        items = list(stock_to_corp.items())
        task_args = [(sc, cc, year, reprt_code) for sc, cc in items]

        companies_result = {}
        ofs_count = cfs_count = empty_count = 0
        done = 0
        start_t = time.time()

        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            futures = {executor.submit(fetch_one, arg): arg for arg in task_args}
            for future in as_completed(futures):
                sc, metrics, fs_used = future.result()
                companies_result[sc] = metrics
                if fs_used == 'OFS':   ofs_count   += 1
                elif fs_used == 'CFS': cfs_count   += 1
                else:                  empty_count += 1
                done += 1
                if done % 200 == 0 or done == total:
                    elapsed = time.time() - start_t
                    rate = done / elapsed if elapsed else 0
                    remain = (total - done) / rate / 60 if rate else 0
                    print(f'  [{done}/{total}] OFS:{ofs_count} CFS:{cfs_count} 없음:{empty_count} '
                          f'| 남은시간 ~{remain:.1f}분')

        elapsed_total = (time.time() - start_t) / 60
        non_zero = sum(1 for m in companies_result.values() if m['revenue'] > 0)
        print(f'  완료 ({elapsed_total:.1f}분): 매출데이터 {non_zero}개 / OFS {ofs_count} / CFS {cfs_count} / 없음 {empty_count}')

        output = {
            'updated_at': datetime.now().strftime('%Y-%m-%d'),
            'year': year, 'quarter': quarter,
            'companies': companies_result,
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False)
        print(f'  저장: {output_path}\n')

    build_manifest(os.path.join(base_dir, 'data'))
    print('\n완료!')


def auto_detect_periods():
    today = date.today()
    year  = today.year
    prev  = year - 1
    periods = [
        (str(prev), 'annual'),
        (str(prev), 'Q1'),
        (str(prev), 'Q2'),
        (str(prev), 'Q3'),
    ]
    if today.month >= 4:  periods.append((str(year), 'annual'))
    if today.month >= 5:  periods.append((str(year), 'Q1'))
    if today.month >= 8:  periods.append((str(year), 'Q2'))
    if today.month >= 11: periods.append((str(year), 'Q3'))
    return periods


if __name__ == '__main__':
    main()
