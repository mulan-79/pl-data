#!/usr/bin/env python3
"""
DART 재무데이터 수집 스크립트 (aiohttp 비동기)
Usage:
  python scripts/fetch_dart_data.py                       # 자동 감지 (공시 기한이 지난 기간만)
  python scripts/fetch_dart_data.py 2026 Q3               # 특정 기간 (파일이 불완전하면 빈 종목만 재시도)
  python scripts/fetch_dart_data.py 2026 Q3 --force       # 전 종목 다시 받기
  python scripts/fetch_dart_data.py 2025 Q1 Q2 Q3 annual --targets   # scripts/targets.json 65곳만 다시 받아 병합

API 키: 환경변수 DART_API_KEY, 없으면 저장소 루트의 .dart_key 파일(한 줄). 키는 어디에도 출력하지 않는다.
"""
import asyncio, json, os, re, sys, time
from datetime import datetime, date

HERE     = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(HERE)
DART_BASE    = 'https://opendart.fss.or.kr/api'
CONCURRENT   = 1    # 동시 요청 수
RATE_PER_SEC = 2    # 초당 최대 요청 수
COMPLETE_RATIO = 0.85   # 매출 데이터가 있는 종목 비율이 이 이상이면 해당 기간을 '완료'로 본다

REPRT_CODE = {
    'Q1': '11013', 'Q2': '11012', 'Q3': '11014',
    'Q4': '11011', 'annual': '11011',
}
QUARTER_LABELS      = {'annual':'연간','Q1':'1분기','Q2':'상반기','Q3':'3분기(누적)'}
PREV_QUARTER_LABELS = {'annual':'연간','Q1':'1분기','Q2':'상반기','Q3':'3분기'}
# 공시 기한(45일) 다음 날부터 해당 분기를 수집한다
DEADLINES = {'Q1': (5, 15), 'Q2': (8, 15), 'Q3': (11, 15)}


def load_api_key():
    k = os.environ.get('DART_API_KEY', '').strip()
    if not k:
        p = os.path.join(BASE_DIR, '.dart_key')
        if os.path.exists(p):
            with open(p, encoding='utf-8-sig') as f:
                k = f.read()
    m = re.search(r'[0-9a-fA-F]{40}', k)   # 'KEY=값' 형태로 붙여넣어도 40자리 키만 사용
    return m.group(0) if m else k.strip()


DART_API_KEY = load_api_key()


def scrub(s):
    s = str(s)
    return s.replace(DART_API_KEY, '***') if DART_API_KEY else s


# ───────────────────────── 계정 찾기 ─────────────────────────
IS_DIVS = ('IS', 'CIS')
BS_DIVS = ('BS',)

# ids: DART 표준 계정코드(접두어 ifrs-full_/ifrs_/dart_ 제외). 없을 때만 names(공백 제거 후 부분일치)로 찾는다.
LINES = {
    'revenue':     {'ids': {'Revenue'},
                    'names': ['매출액', '수익(매출액)', '영업수익', '수익', '매출'],
                    'exact_only': ('수익', '매출')},
    'cogs':        {'ids': {'CostOfSales'}, 'names': ['매출원가']},
    'grossProfit': {'ids': {'GrossProfit'}, 'names': ['매출총이익', '매출총손익']},
    'sga':         {'ids': {'TotalSellingGeneralAdministrativeExpenses', 'SellingGeneralAndAdministrativeExpense'},
                    'names': ['판매비와관리비', '판매비와일반관리비', '판매비및관리비', '판매관리비', '판매비및일반관리비']},
    'rd':          {'ids': {'ResearchAndDevelopmentExpense'},
                    'names': ['경상연구개발비', '연구개발비', '경상개발비', '연구와개발비용']},
    'opIncome':    {'ids': {'OperatingIncomeLoss'}, 'names': ['영업이익(손실)', '영업이익', '영업손실']},
    'pretax':      {'ids': {'ProfitLossBeforeTax'},
                    'names': ['법인세비용차감전순이익(손실)', '법인세차감전순이익(손실)', '법인세차감전순이익', '법인세차감전당기순이익']},
    'netIncome':   {'ids': {'ProfitLoss'},
                    'names': ['당기순이익(손실)', '분기순이익(손실)', '반기순이익(손실)', '당기순이익', '분기순이익', '반기순이익']},
}
BS_LINES = {
    'assets':      {'ids': {'Assets'},      'names': ['자산총계']},
    'liabilities': {'ids': {'Liabilities'}, 'names': ['부채총계']},
    'equity':      {'ids': {'Equity'},      'names': ['자본총계']},
}


def _num(v):
    if v is None:
        return None
    s = str(v).replace(',', '').strip()
    if s in ('', '-'):
        return None
    try:
        return int(s)
    except Exception:
        return None


def _nm(r):
    return re.sub(r'\s+', '', r.get('account_nm') or '')


def _norm_id(i):
    i = (i or '').strip()
    return i.split('_', 1)[1] if '_' in i else i


def _ord(r):
    try:
        return int(r.get('ord') or 0)
    except Exception:
        return 0


def _prefer_ytd(rs):
    # 같은 계정에 '3개월' 전용 행이 따로 올 때는 누계 행을 우선
    y = [r for r in rs if '3개월' not in (r.get('thstrm_nm') or '')]
    return (y or rs)[0]


def find_row(rows, spec, divs):
    cands = [r for r in rows if r.get('sj_div') in divs]
    cands.sort(key=lambda r: (0 if r.get('sj_div') == 'IS' else 1, _ord(r)))
    if not cands:
        return None
    by_id = [r for r in cands if _norm_id(r.get('account_id')) in spec['ids']]
    if by_id:
        return _prefer_ytd(by_id)
    for kw in spec['names']:
        matched = [r for r in cands if kw in _nm(r)]
        if not matched:
            continue
        exact = [r for r in matched if _nm(r) == kw]
        if exact:
            matched = exact
        elif kw in spec.get('exact_only', ()):
            continue   # '수익'처럼 흔한 단어의 부분일치는 '금융수익' 등을 잘못 집음
        return _prefer_ytd(matched)
    return None


def income_slots(row, quarter):
    """[3개월 당기, 누적 당기, 3개월 전년동기, 누적 전년동기]. 연간은 3개월 칸이 None."""
    g = lambda k: _num(row.get(k))
    if quarter in ('annual', 'Q4'):
        return [None, g('thstrm_amount'), None, g('frmtrm_amount')]
    cq, cy = g('thstrm_amount'), g('thstrm_add_amount')
    pq, py = g('frmtrm_q_amount'), g('frmtrm_add_amount')
    if quarter == 'Q1':      # 1분기는 3개월 = 누적
        if pq is None:
            pq = g('frmtrm_amount')
        cy = cq if cy is None else cy
        py = pq if py is None else py
    return [cq, cy, pq, py]


def _sub(a, b):
    return [(x - y) if x is not None and y is not None else None for x, y in zip(a, b)]


def extract_all(stock_code, corp_code, rows, quarter, fs_div):
    flags = []
    amounts = {}
    for k in ('revenue', 'cogs', 'grossProfit', 'sga', 'rd', 'opIncome', 'pretax', 'netIncome'):
        row = find_row(rows, LINES[k], IS_DIVS)
        amounts[k] = income_slots(row, quarter) if row else [None] * 4
        if k == 'revenue' and row and quarter in ('Q2', 'Q3') and amounts[k][1] is None:
            flags.append('noAdd')   # 누적 칸이 없는 보고서
    if all(v is None for v in amounts['grossProfit']):
        gp = _sub(amounts['revenue'], amounts['cogs'])
        if any(v is not None for v in gp):
            amounts['grossProfit'] = gp
            flags.append('gpDerived')
    amounts['sgaTotal'] = _sub(amounts['grossProfit'], amounts['opIncome'])
    for k, spec in BS_LINES.items():
        row = find_row(rows, spec, BS_DIVS)
        amounts[k] = [_num(row.get('thstrm_amount')), _num(row.get('frmtrm_amount'))] if row else [None, None]

    cur = lambda k: amounts[k][1] or 0
    prv = lambda k: amounts[k][3] or 0
    r, pr = cur('revenue'), prv('revenue')
    growth = round((r - pr) / abs(pr) * 100, 2) if pr else 0
    rate = lambda v: round(v / r * 100, 2) if r else 0
    rec = {
        'stockCode': stock_code, 'corpCode': corp_code,
        'revenue': r, 'prevRevenue': pr, 'revenueGrowth': growth,
        'cogs': cur('cogs'), 'prevCogs': prv('cogs'), 'cogsRate': rate(cur('cogs')),
        'sga': cur('sga'), 'prevSga': prv('sga'), 'sgaRate': rate(cur('sga')),
        'opIncome': cur('opIncome'), 'prevOpIncome': prv('opIncome'), 'opMargin': rate(cur('opIncome')),
        'pretaxIncome': cur('pretax'), 'prevPretaxIncome': prv('pretax'),
        'netIncome': cur('netIncome'), 'prevNetIncome': prv('netIncome'), 'netMargin': rate(cur('netIncome')),
        # ── 새 필드 (기존 필드는 그대로) ──
        'grossProfit': cur('grossProfit'), 'prevGrossProfit': prv('grossProfit'),
        'rd': cur('rd'), 'prevRd': prv('rd'),
        'sgaTotal': cur('sgaTotal'), 'prevSgaTotal': prv('sgaTotal'), 'sgaTotalRate': rate(cur('sgaTotal')),
        'assets': amounts['assets'][0] or 0, 'prevAssets': amounts['assets'][1] or 0,
        'liabilities': amounts['liabilities'][0] or 0, 'prevLiabilities': amounts['liabilities'][1] or 0,
        'equity': amounts['equity'][0] or 0, 'prevEquity': amounts['equity'][1] or 0,
        'fsDiv': fs_div,
        'rceptNo': (rows[0].get('rcept_no') if rows else None),
        'amounts': amounts,
    }
    if flags:
        rec['flags'] = flags
    if not rows:
        rec.pop('amounts')
        rec['flags'] = ['noData']
    return rec


# ───────────────────────── 수집 ─────────────────────────
class RateLimiter:
    """글로벌 레이트리밋 제어: 020 감지 시 점진적으로 긴 pause"""
    def __init__(self):
        self._lock  = asyncio.Lock()
        self._until = 0.0
        self._hits  = 0

    async def wait(self):
        remaining = self._until - time.monotonic()
        if remaining > 0:
            if remaining > 3:
                print(f'\r  레이트리밋 대기 중... {remaining:.0f}s 남음', end='', flush=True)
            await asyncio.sleep(remaining)

    async def on_rate_limit(self):
        async with self._lock:
            self._hits += 1
            pause = min(30 * self._hits, 180)
            resume_at = time.monotonic() + pause
            if resume_at > self._until:
                self._until = resume_at
                print(f'\n  요청제한(020) #{self._hits} — {pause}초 전체 대기 중...')

    def reset_hits(self):
        self._hits = 0


def _fetch_sync(corp_code, year, reprt_code):
    """동기 requests 방식 (aiohttp TCP 오류 폴백용)"""
    import requests as req
    url = f'{DART_BASE}/fnlttSinglAcntAll.json'
    for fs_div in ['OFS', 'CFS']:
        params = {'crtfc_key': DART_API_KEY, 'corp_code': corp_code,
                  'bsns_year': year, 'reprt_code': reprt_code, 'fs_div': fs_div}
        for attempt in range(3):
            try:
                d = req.get(url, params=params, timeout=20).json()
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
                elif attempt < 2:
                    time.sleep(1)
            except Exception:
                if attempt < 2:
                    time.sleep(2)
    return [], None, False


async def fetch_single_all_async(session, corp_code, year, reprt_code, rl):
    """OFS(별도) 우선 → CFS(연결) 폴백. 반환: (rows, fs_div, rate_limited)"""
    url = f'{DART_BASE}/fnlttSinglAcntAll.json'
    for fs_div in ['OFS', 'CFS']:
        params = {'crtfc_key': DART_API_KEY, 'corp_code': corp_code,
                  'bsns_year': year, 'reprt_code': reprt_code, 'fs_div': fs_div}
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
                    break
                elif status == '013':
                    break
                elif status == '020':
                    await rl.on_rate_limit()
                    if attempt == 2:
                        return [], None, True
                    continue
                elif attempt < 2:
                    await asyncio.sleep(1)
            except Exception as e:
                if 'WinError' in str(e) or isinstance(e, OSError):
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, _fetch_sync, corp_code, year, reprt_code)
                if attempt < 2:
                    await asyncio.sleep(2 + attempt * 2)
    return [], None, False


async def fetch_one_async(session, sem, sc, cc, year, reprt_code, quarter, rl):
    async with sem:
        rows, fs_used, rate_limited = await fetch_single_all_async(session, cc, year, reprt_code, rl)
        return sc, extract_all(sc, cc, rows, quarter, fs_used), fs_used, rate_limited


async def fetch_all_async(todo, year, reprt_code, quarter, checkpoint_path=None):
    """todo: {stock_code: corp_code}. 반환: ({stock_code: record}, 레이트리밋으로 못 받은 종목 수)"""
    import aiohttp
    sem      = asyncio.Semaphore(CONCURRENT)
    rate_sem = asyncio.Semaphore(RATE_PER_SEC)
    rl       = RateLimiter()
    connector = aiohttp.TCPConnector(limit=CONCURRENT, ttl_dns_cache=300, force_close=True)
    timeout   = aiohttp.ClientTimeout(total=30, connect=10)

    results, retry_later = {}, {}
    if checkpoint_path and os.path.exists(checkpoint_path):
        with open(checkpoint_path, encoding='utf-8-sig') as f:
            ckpt = json.load(f)
        results = ckpt.get('done', {})
        print(f'  체크포인트 로드: 완료 {len(results)}개')

    remaining = {sc: cc for sc, cc in todo.items() if sc not in results}
    total_all, total = len(todo), len(remaining)
    print(f'  처리 대상: {total}개 (체크포인트 완료: {len(results)}개)')

    ofs = cfs = empty = rl_count = done = 0
    start_t = time.time()

    async def limited(session, sc, cc):
        async with rate_sem:
            res = await fetch_one_async(session, sem, sc, cc, year, reprt_code, quarter, rl)
            await asyncio.sleep(1.0 / RATE_PER_SEC)
            return res

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [limited(session, sc, cc) for sc, cc in remaining.items()]
        for coro in asyncio.as_completed(tasks):
            sc, rec, fs_used, rate_limited = await coro
            if rate_limited:
                retry_later[sc] = remaining[sc]
                rl_count += 1
            else:
                results[sc] = rec
                if fs_used == 'OFS':   ofs   += 1
                elif fs_used == 'CFS': cfs   += 1
                else:                  empty += 1
            done += 1
            if done % 50 == 0 or done == total:
                el = time.time() - start_t
                rate = done / el if el else 1
                rl_str = f' RL:{rl_count}' if rl_count else ''
                print(f'  [{done}/{total}] OFS:{ofs} CFS:{cfs} 없음:{empty}{rl_str} | {el:.0f}s 경과 / 남은 ~{(total-done)/rate:.0f}s')
                if checkpoint_path:
                    with open(checkpoint_path, 'w', encoding='utf-8', newline='\n') as f:
                        json.dump({'done': results}, f, ensure_ascii=False)

    non_zero = sum(1 for m in results.values() if m['revenue'] > 0)
    print(f'  완료 ({time.time()-start_t:.1f}초): 매출데이터 {non_zero}개 / OFS {ofs} / CFS {cfs} / 없음 {empty} / 레이트리밋 미수집 {len(retry_later)}')
    if checkpoint_path and os.path.exists(checkpoint_path) and not retry_later:
        os.remove(checkpoint_path)
    return results, len(retry_later)


# ───────────────────────── 검증 리포트 ─────────────────────────
DAEWON = {  # 2026 Q3 대원제약 별도 누적 (기대값)
    'revenue': 407_804_204_837, 'cogs': 209_369_743_881, 'opIncome': 5_211_484_411,
    'netIncome': 4_282_820_394,
}
DAEWON_ASSETS = 560_181_948_821


def _fmt(v):
    return '-' if v is None else f'{v:,}'


def write_verify(year, quarter, companies, names, target_codes):
    key = f'{year}_{quarter}'
    nm = lambda sc: names.get(sc.zfill(6), sc)
    full = {sc: r for sc, r in companies.items() if 'amounts' in r}
    nodata = sorted(sc for sc, r in companies.items() if 'noData' in (r.get('flags') or []))
    old_fmt = len(companies) - len(full) - len(nodata)
    L = []
    L.append(f'# 검증 리포트 {key}')
    L.append(f'\n생성: {datetime.now().strftime("%Y-%m-%d %H:%M")} · 전체 {len(companies)}개 중 새 형식 {len(full)}개 / 자료 없음 {len(nodata)}개 / 이전 형식(검증 제외) {old_fmt}개\n')

    bs_fail, bs_miss, gp_fail, line_miss, cfs, noadd = [], [], [], [], [], []
    for sc, r in sorted(full.items()):
        a = r['amounts']
        for i, lab in ((0, '당기말'), (1, '전기말')):
            A, Li, E = a['assets'][i], a['liabilities'][i], a['equity'][i]
            if None in (A, Li, E):
                if i == 0:
                    bs_miss.append(f'{nm(sc)}({sc.zfill(6)})')
            elif A != Li + E:
                bs_fail.append(f'{nm(sc)}({sc.zfill(6)}) {lab}: 자산 {A:,} ≠ 부채+자본 {Li+E:,} (차 {A-Li-E:,})')
        if 'gpDerived' not in (r.get('flags') or []):
            for i, lab in ((0, '3개월'), (1, '누적')):
                R, C, G = a['revenue'][i], a['cogs'][i], a['grossProfit'][i]
                if None not in (R, C, G) and R - C != G:
                    gp_fail.append(f'{nm(sc)}({sc.zfill(6)}) {lab}: 매출−원가 {R-C:,} ≠ 매출총이익 {G:,}')
        miss = [lab for k, lab in (('revenue', '매출'), ('opIncome', '영업이익'), ('netIncome', '순이익')) if a[k][1] is None and a[k][0] is None]
        if miss:
            line_miss.append(f'{nm(sc)}({sc.zfill(6)}): {", ".join(miss)}')
        if r.get('fsDiv') == 'CFS':
            cfs.append(f'{nm(sc)}({sc.zfill(6)})')
        if 'noAdd' in (r.get('flags') or []):
            noadd.append(f'{nm(sc)}({sc.zfill(6)})')

    def section(title, items, ok='이상 없음'):
        L.append(f'## {title}  — {len(items)}건' if items else f'## {title}  — {ok}')
        for it in items[:200]:
            L.append(f'- {it}')
        if len(items) > 200:
            L.append(f'- … 외 {len(items)-200}건')
        L.append('')

    section('1. 자산총계 = 부채총계 + 자본총계 불일치', bs_fail)
    section('1-b. 재무상태표 줄(자산·부채·자본)을 못 찾은 회사', bs_miss)
    section('2. 매출 − 매출원가 ≠ 매출총이익 (확인 필요)', gp_fail)
    section('3. 매출·영업이익·순이익 줄을 못 찾은 회사', line_miss)
    tgt_nodata = [f'{nm(sc)}({sc.zfill(6)})' for sc in nodata if sc.zfill(6) in target_codes]
    L.append(f'## 4. 자료가 없는 회사 — 전체 {len(nodata)}건 (이 중 65곳 대상 {len(tgt_nodata)}건)')
    if tgt_nodata:
        L.append('- 65곳 대상: ' + ', '.join(tgt_nodata))
    L.append('- 전체 종목코드: ' + (', '.join(sc.zfill(6) for sc in nodata[:300]) or '없음') + (' …' if len(nodata) > 300 else ''))
    L.append('')
    section('5. 별도(OFS)가 없어 연결(CFS)로 대체한 회사 (fsDiv=CFS)', cfs, ok='없음')
    if quarter in ('Q2', 'Q3'):
        section('6. 누적 칸이 없는 반기·분기 보고서(누적 값 null)', noadd, ok='없음')

    if year == '2026' and quarter == 'Q3':
        r = companies.get('3220') or companies.get('003220')
        L.append('## 7. 대원제약(003220) 2026 Q3 별도 누적 기준값 대조')
        if not r or 'amounts' not in r:
            L.append('- 대원제약 데이터 없음 → 확인 필요')
        else:
            a = r['amounts']
            L.append(f'- fsDiv: {r.get("fsDiv")} (OFS여야 함)')
            L.append('\n| 항목 | 기준값 | 수집값 | 결과 |\n|---|---:|---:|:---:|')
            rows = [(lab, DAEWON[k], a[k][1]) for k, lab in (('revenue', '매출'), ('cogs', '매출원가'), ('opIncome', '영업이익'), ('netIncome', '순이익'))]
            rows.append(('자산총계', DAEWON_ASSETS, a['assets'][0]))
            for lab, exp, got in rows:
                L.append(f'| {lab} | {exp:,} | {_fmt(got)} | {"통과" if exp == got else "불일치"} |')
        L.append('')

    path = os.path.join(BASE_DIR, 'data', f'verify_{key}.md')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L))
    return {'balanceFail': len(bs_fail), 'gpFail': len(gp_fail), 'lineMissing': len(line_miss),
            'noData': len(nodata), 'cfs': len(cfs)}


# ───────────────────────── 보조 ─────────────────────────
def build_manifest(data_dir):
    periods = []
    for fname in sorted(os.listdir(data_dir), reverse=True):
        m = re.match(r'financial_(\d{4})_(annual|Q1|Q2|Q3|Q4)\.json$', fname)
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
    manifest = {'updated_at': datetime.now().strftime('%Y-%m-%d'),
                'latest': periods[0]['key'] if periods else None, 'periods': periods}
    with open(os.path.join(data_dir, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f'manifest.json 업데이트: {len(periods)}개 기간')


def auto_detect_periods(today=None):
    today = today or date.today()
    md, year = (today.month, today.day), today.year
    prev = year - 1
    periods = []
    if md >= (4, 1):
        periods.append((str(prev), 'annual'))
    periods += [(str(prev), q) for q in ('Q1', 'Q2', 'Q3')]
    for q, (m, d) in DEADLINES.items():
        if md >= (m, d):
            periods.append((str(year), q))
    return periods


def revenue_ratio(companies, total):
    nz = sum(1 for v in companies.values() if v.get('revenue', 0) > 0)
    return nz / max(total, 1)


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    if not DART_API_KEY:
        print('오류: DART_API_KEY 환경변수 또는 .dart_key 파일이 없습니다.')
        sys.exit(1)
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        print('오류: aiohttp가 필요합니다. pip install aiohttp requests')
        sys.exit(1)

    force       = '--force' in sys.argv
    targets_only = '--targets' in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith('-')]

    if len(args) >= 2:
        year, quarters = args[0], args[1:]
        if quarters == ['all']:
            quarters = ['Q1', 'Q2', 'Q3', 'annual']
        periods = [(year, q) for q in quarters]
    elif len(args) == 1:
        periods = [(args[0], 'annual')]
    else:
        periods = auto_detect_periods()

    with open(os.path.join(BASE_DIR, 'industry_data.json'), encoding='utf-8') as f:
        industry_data = json.load(f)
    with open(os.path.join(BASE_DIR, 'api-worker', 'corp_code_map.json'), encoding='utf-8') as f:
        corp_code_map = json.load(f)
    with open(os.path.join(HERE, 'targets.json'), encoding='utf-8') as f:
        tg = json.load(f)
    target_codes = {t['code'] for t in tg['targets']}

    names, stock_to_corp = {}, {}
    for companies in industry_data['companies'].values():
        for c in companies:
            sc = c['stock_code']
            names[sc.zfill(6)] = c.get('name', sc)
            cc = corp_code_map.get(sc) or corp_code_map.get(sc.zfill(6))
            if cc:
                stock_to_corp[sc] = cc
    for t in tg['targets']:
        names[t['code']] = t['name']

    if targets_only:
        stock_to_corp = {sc: cc for sc, cc in stock_to_corp.items() if sc.zfill(6) in target_codes}
        missing = target_codes - {sc.zfill(6) for sc in stock_to_corp}
        if missing:
            print(f'경고: 대상 종목 중 industry_data/corp_code_map에 없는 종목: {sorted(missing)}')

    mode = '65곳만 병합' if targets_only else '전 종목'
    print(f'{len(stock_to_corp)}개 기업({mode}) | 초당 {RATE_PER_SEC}req | {len(periods)}개 기간 순차 실행\n')

    data_dir = os.path.join(BASE_DIR, 'data')
    os.makedirs(data_dir, exist_ok=True)
    this_year = str(date.today().year)
    run_log = []

    for year, quarter in periods:
        output_path = os.path.join(data_dir, f'financial_{year}_{quarter}.json')
        existing = {}
        if os.path.exists(output_path):
            with open(output_path, encoding='utf-8') as f:
                existing = json.load(f).get('companies', {})

        if targets_only:
            todo = {sc: cc for sc, cc in stock_to_corp.items() if force or 'amounts' not in existing.get(sc, {})}
        elif existing and not force:
            ratio = revenue_ratio(existing, len(stock_to_corp))
            if ratio >= COMPLETE_RATIO and year != this_year:
                print(f'[{year} {quarter}] 완료된 기간 (매출 보유 {ratio:.0%}) — 건너뜀')
                run_log.append({'period': f'{year}_{quarter}', 'action': 'skipped', 'revenueRatio': round(ratio, 3)})
                continue
            todo = {sc: cc for sc, cc in stock_to_corp.items()
                    if sc not in existing or existing[sc].get('revenue', 0) == 0}
            print(f'[{year} {quarter}] 매출 보유 {ratio:.0%} — 비어 있는 {len(todo)}개만 다시 시도')
        else:
            todo = dict(stock_to_corp)

        if not todo:
            print(f'[{year} {quarter}] 받을 종목 없음\n')
            run_log.append({'period': f'{year}_{quarter}', 'action': 'nothing-to-do'})
            continue

        print(f'[{year} {quarter}] 수집 시작... ({len(todo)}개)')
        reprt_code = REPRT_CODE.get(quarter, '11011')
        new, rl_missed = asyncio.run(fetch_all_async(todo, year, reprt_code, quarter, output_path + '.ckpt'))
        merged = dict(existing)
        merged.update(new)
        if revenue_ratio(merged, len(stock_to_corp)) == 0 and not existing:
            print('  매출 데이터가 전혀 없어 파일을 저장하지 않습니다 (공시 전이거나 오류).\n')
            run_log.append({'period': f'{year}_{quarter}', 'action': 'no-data-not-saved'})
            continue
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({'updated_at': datetime.now().strftime('%Y-%m-%d'),
                       'year': year, 'quarter': quarter, 'companies': merged}, f, ensure_ascii=False)
        summary = write_verify(year, quarter, merged, names, target_codes)
        print(f'  저장: {output_path} (+ verify_{year}_{quarter}.md)\n')
        run_log.append({'period': f'{year}_{quarter}', 'action': 'fetched', 'requested': len(todo),
                        'rateLimitedMissed': rl_missed, **summary})

    build_manifest(data_dir)
    with open(os.path.join(data_dir, 'last_run.json'), 'w', encoding='utf-8') as f:
        json.dump({'run_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'mode': mode,
                   'periods': run_log}, f, ensure_ascii=False, indent=2)
    print('\n완료!')


if __name__ == '__main__':
    main()
