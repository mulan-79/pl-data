#!/usr/bin/env python3
"""
DART 재무데이터 수집 스크립트 (aiohttp 비동기 버전)
Usage:
  python scripts/fetch_dart_data.py              # 자동 감지
  python scripts/fetch_dart_data.py 2024 Q3      # 특정 연도/분기
  python scripts/fetch_dart_data.py 2024 Q3 --force   # 기존 파일 덮어쓰기
"""
import asyncio, json, os, sys, time
from datetime import datetime, date

DART_API_KEY = os.environ.get('DART_API_KEY', '')
DART_BASE    = 'https://opendart.fss.or.kr/api'
CONCURRENT   = 1    # 동시 요청 수
RATE_PER_SEC = 2    # 초당 최대 요청 수

REPRT_CODE = {
    'Q1': '11013', 'Q2': '11012', 'Q3': '11014',
    'Q4': '11011', 'annual': '11011',
}
QUARTER_LABELS      = {'annual':'연간','Q1':'1분기','Q2':'상반기','Q3':'3분기(누적)'}
PREV_QUARTER_LABELS = {'annual':'연간','Q1':'1분기','Q2':'상반기','Q3':'3분기'}


def parse_num(s):
    if not s:
        return 0
    try:
        return int(str(s).replace(',', '').strip())
    except Exception:
        return 0


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

    r, pr = rev['current'], rev['prev']
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


class RateLimiter:
    """글로벌 레이트리밋 제어: 020 감지 시 점진적으로 긴 pause"""
    def __init__(self):
        self._lock    = asyncio.Lock()
        self._paused  = False
        self._until   = 0.0   # 이 시각까지 대기
        self._hits    = 0     # 연속 020 횟수

    async def wait(self):
        now = time.monotonic()
        remaining = self._until - now
        if remaining > 0:
            if remaining > 3:
                print(f'\r  ⏳ 레이트리밋 대기 중... {remaining:.0f}s 남음', end='', flush=True)
            await asyncio.sleep(remaining)

    async def on_rate_limit(self):
        async with self._lock:
            self._hits += 1
            # 첫 번째 30초, 이후 60초씩 증가 (최대 180초)
            pause = min(30 * self._hits, 180)
            resume_at = time.monotonic() + pause
            if resume_at > self._until:
                self._until = resume_at
                print(f'\n  ⚠ 요청제한(020) #{self._hits} — {pause}초 전체 대기 중...')

    def reset_hits(self):
        self._hits = 0


def _fetch_sync(corp_code, year, reprt_code):
    """순수 동기 requests 방식 (aiohttp TCP 오류 폴백용)"""
    import requests as req
    url = f'{DART_BASE}/fnlttSinglAcntAll.json'
    for fs_div in ['OFS', 'CFS']:
        params = {'crtfc_key': DART_API_KEY, 'corp_code': corp_code,
                  'bsns_year': year, 'reprt_code': reprt_code, 'fs_div': fs_div}
        for attempt in range(3):
            try:
                r = req.get(url, params=params, timeout=20)
                d = r.json()
                status = d.get('status')
                if status == '000' and d.get('list'):
                    return d['list'], fs_div, False
                elif status == '013':
                    break
                elif status == '020':
                    time.sleep(30)
                    if attempt == 2:
                        return [], None, True
                    continue
                else:
                    if attempt < 2:
                        time.sleep(1)
            except Exception:
                if attempt < 2:
                    time.sleep(2)
    return [], None, False


async def fetch_single_all_async(session, corp_code, year, reprt_code, rl: RateLimiter):
    """OFS 우선 → CFS 폴백.
    반환: (rows, fs_div, rate_limited)
      rate_limited=True  → 레이트리밋으로 실패 (나중에 재시도 필요)
      rate_limited=False → 정상 or 데이터 없음(013)
    """
    url = f'{DART_BASE}/fnlttSinglAcntAll.json'
    for fs_div in ['OFS', 'CFS']:
        params = {
            'crtfc_key':  DART_API_KEY,
            'corp_code':  corp_code,
            'bsns_year':  year,
            'reprt_code': reprt_code,
            'fs_div':     fs_div,
        }
        for attempt in range(3):
            await rl.wait()
            try:
                async with session.get(url, params=params, timeout=20) as resp:
                    data = await resp.json(content_type=None)
                status = data.get('status')
                if status == '000':
                    rows = data.get('list', [])
                    if rows:
                        rl.reset_hits()
                        return rows, fs_div, False
                    break  # 빈 데이터 → CFS 시도
                elif status == '013':
                    break  # 이 회사 보고서 없음 (정상)
                elif status == '020':
                    await rl.on_rate_limit()
                    if attempt == 2:
                        return [], None, True
                    continue
                else:
                    if attempt < 2:
                        await asyncio.sleep(1)
            except Exception as e:
                err = str(e)
                # WinError 64 / OSError: aiohttp TCP 연결 실패 → 동기 requests로 즉시 폴백
                if 'WinError' in err or isinstance(e, OSError):
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(
                        None, _fetch_sync, corp_code, year, reprt_code
                    )
                if attempt < 2:
                    await asyncio.sleep(2 + attempt * 2)
    return [], None, False  # 013 or 진짜 데이터 없음


async def fetch_one_async(session, sem, sc, cc, year, reprt_code, rl):
    async with sem:
        rows, fs_used, rate_limited = await fetch_single_all_async(session, cc, year, reprt_code, rl)
        metrics = extract_metrics(sc, cc, rows)
        return sc, metrics, fs_used, rate_limited


async def fetch_all_async(stock_to_corp, year, reprt_code, checkpoint_path=None):
    import aiohttp
    sem      = asyncio.Semaphore(CONCURRENT)
    rate_sem = asyncio.Semaphore(RATE_PER_SEC)
    rl       = RateLimiter()
    # force_close=True: 연결 재사용 안 함 (DART가 TCP를 끊어도 WinError 64 방지)
    connector = aiohttp.TCPConnector(limit=CONCURRENT, ttl_dns_cache=300, force_close=True)
    timeout   = aiohttp.ClientTimeout(total=30, connect=10)

    # 체크포인트: revenue>0 이거나 명시적 nodata인 것만 저장
    companies_result = {}
    retry_later      = {}   # 레이트리밋으로 실패한 종목
    if checkpoint_path and os.path.exists(checkpoint_path):
        with open(checkpoint_path, encoding='utf-8-sig') as f:
            ckpt = json.load(f)
        companies_result = ckpt.get('done', {})
        retry_later      = ckpt.get('retry', {})
        print(f'  체크포인트 로드: 완료 {len(companies_result)}개, 재시도 대기 {len(retry_later)}개')

    # 처리 대상: 완료 목록에 없는 것 + 이전에 레이트리밋 걸린 것
    done_set  = set(companies_result.keys())
    remaining = {sc: cc for sc, cc in stock_to_corp.items() if sc not in done_set}
    remaining.update(retry_later)   # 재시도 포함
    total_all = len(stock_to_corp)
    total     = len(remaining)
    print(f'  처리 대상: {total}개 (완료: {len(done_set)}개)')

    ofs_count = cfs_count = empty_count = rl_count = done = 0
    start_t = time.time()

    async def rate_limited_fetch(session, sc, cc):
        async with rate_sem:
            result = await fetch_one_async(session, sem, sc, cc, year, reprt_code, rl)
            await asyncio.sleep(1.0 / RATE_PER_SEC)
            return result

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [rate_limited_fetch(session, sc, cc) for sc, cc in remaining.items()]
        for coro in asyncio.as_completed(tasks):
            sc, metrics, fs_used, rate_limited = await coro
            if rate_limited:
                # 레이트리밋 실패 → 나중에 재시도 목록에 보관 (저장 안 함)
                retry_later[sc] = remaining[sc]
                rl_count += 1
            else:
                companies_result[sc] = metrics
                retry_later.pop(sc, None)
                if fs_used == 'OFS':   ofs_count   += 1
                elif fs_used == 'CFS': cfs_count   += 1
                else:                  empty_count += 1
            done += 1
            if done % 50 == 0 or done == total:
                elapsed = time.time() - start_t
                rate    = done / elapsed if elapsed else 1
                remain  = (total - done) / rate if rate else 0
                empty_rate = empty_count / max(done - rl_count, 1) * 100
                rl_str = f' RL:{rl_count}' if rl_count else ''
                print(f'  [{done+total_all-total}/{total_all}] OFS:{ofs_count} CFS:{cfs_count} 없음:{empty_count}({empty_rate:.0f}%){rl_str}'
                      f' | {elapsed:.0f}s 경과 / 남은 ~{remain:.0f}s')
                # 체크포인트 저장 (50개마다) - done/retry 모두 저장
                if checkpoint_path:
                    with open(checkpoint_path, 'w', encoding='utf-8', newline='\n') as f:
                        json.dump({'done': companies_result, 'retry': retry_later}, f, ensure_ascii=False)

    elapsed_total = time.time() - start_t
    non_zero = sum(1 for m in companies_result.values() if m['revenue'] > 0)
    print(f'  완료 ({elapsed_total:.1f}초): 매출데이터 {non_zero}개 / OFS {ofs_count} / CFS {cfs_count} / 없음 {empty_count}')
    # 체크포인트 정리
    if checkpoint_path and os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)
    return companies_result


def fetch_all_sync_fallback(stock_to_corp, year, reprt_code):
    """aiohttp 없을 때 ThreadPoolExecutor 폴백 (workers=30)"""
    import requests as req
    from concurrent.futures import ThreadPoolExecutor, as_completed

    WORKERS = 30
    url = f'{DART_BASE}/fnlttSinglAcntAll.json'

    def _fetch(sc, cc):
        for fs_div in ['OFS', 'CFS']:
            params = {'crtfc_key': DART_API_KEY, 'corp_code': cc,
                      'bsns_year': year, 'reprt_code': reprt_code, 'fs_div': fs_div}
            for attempt in range(2):
                try:
                    r = req.get(url, params=params, timeout=15)
                    d = r.json()
                    if d.get('status') == '000' and d.get('list'):
                        return extract_metrics(sc, cc, d['list']), fs_div
                    if d.get('status') in ('013', '020'):
                        break
                    if attempt == 0:
                        time.sleep(0.2)
                except Exception:
                    if attempt == 0:
                        time.sleep(0.5)
        return extract_metrics(sc, cc, []), None

    total = len(stock_to_corp)
    companies_result = {}
    ofs_count = cfs_count = empty_count = done = 0
    start_t = time.time()

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(_fetch, sc, cc): sc for sc, cc in stock_to_corp.items()}
        for future in as_completed(futures):
            sc = futures[future]
            metrics, fs_used = future.result()
            companies_result[sc] = metrics
            if fs_used == 'OFS':   ofs_count   += 1
            elif fs_used == 'CFS': cfs_count   += 1
            else:                  empty_count += 1
            done += 1
            if done % 200 == 0 or done == total:
                elapsed = time.time() - start_t
                rate    = done / elapsed if elapsed else 1
                remain  = (total - done) / rate
                print(f'  [{done}/{total}] OFS:{ofs_count} CFS:{cfs_count} 없음:{empty_count}'
                      f' | 남은시간 ~{remain:.0f}초')

    elapsed_total = time.time() - start_t
    non_zero = sum(1 for m in companies_result.values() if m['revenue'] > 0)
    print(f'  완료 ({elapsed_total:.1f}초): 매출데이터 {non_zero}개 / OFS {ofs_count} / CFS {cfs_count} / 없음 {empty_count}')
    return companies_result


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


def auto_detect_periods():
    today = date.today()
    year, prev = today.year, today.year - 1
    periods = [(str(prev), 'annual'), (str(prev), 'Q1'),
               (str(prev), 'Q2'),    (str(prev), 'Q3')]
    if today.month >= 4:  periods.append((str(year), 'annual'))
    if today.month >= 5:  periods.append((str(year), 'Q1'))
    if today.month >= 8:  periods.append((str(year), 'Q2'))
    if today.month >= 11: periods.append((str(year), 'Q3'))
    return periods


def main():
    if not DART_API_KEY:
        print('오류: DART_API_KEY 환경변수가 없습니다.')
        sys.exit(1)

    force = '--force' in sys.argv
    args  = [a for a in sys.argv[1:] if not a.startswith('-')]

    if len(args) >= 2:
        year = args[0]
        quarters = args[1:]  # 예: 2024 Q1 Q2 Q3 → 순차 실행
        # 'all' 단축어 지원
        if quarters == ['all']:
            quarters = ['Q1', 'Q2', 'Q3', 'annual']
        periods = [(year, q) for q in quarters]
    elif len(args) == 1:
        periods = [(args[0], 'annual')]
    else:
        periods = auto_detect_periods()

    # aiohttp 사용 가능 여부 확인
    try:
        import aiohttp
        use_async = True
        print('✓ aiohttp 감지 → 비동기 모드')
    except ImportError:
        use_async = False
        print('⚠ aiohttp 없음 → ThreadPoolExecutor 폴백')
        print('  pip install aiohttp 로 설치하면 더 빠릅니다.')

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
    est_sec = round(total / RATE_PER_SEC)
    print(f'총 {total}개 기업 | 초당 {RATE_PER_SEC}req | 예상 ~{est_sec}초/기간 | {len(periods)}개 기간 순차 실행\n')

    os.makedirs(os.path.join(base_dir, 'data'), exist_ok=True)

    for year, quarter in periods:
        output_path = os.path.join(base_dir, 'data', f'financial_{year}_{quarter}.json')

        if os.path.exists(output_path) and not force:
            print(f'이미 존재 (건너뜀): {output_path}  ← 덮어쓰려면 --force 옵션 추가')
            continue

        print(f'[{year} {quarter}] 수집 시작...')
        reprt_code = REPRT_CODE.get(quarter, '11011')

        checkpoint_path = output_path + '.ckpt'
        if use_async:
            companies_result = asyncio.run(
                fetch_all_async(stock_to_corp, year, reprt_code, checkpoint_path)
            )
        else:
            companies_result = fetch_all_sync_fallback(stock_to_corp, year, reprt_code)

        output = {
            'updated_at': datetime.now().strftime('%Y-%m-%d'),
            'year': year, 'quarter': quarter,
            'companies': companies_result,
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False)
        print(f'  저장: {output_path}\n')

    build_manifest(os.path.join(base_dir, 'data'))
    print('\n✓ 완료!')


if __name__ == '__main__':
    main()
