#!/usr/bin/env python3
"""2·3분기 '3개월 값 ≠ 누적 − 앞 분기 누적' 항목을 공시 원문(document.xml)과 대조해 scripts/q_corrections.json 에 기록.
  fixes      : 원문 3개월 = 누적 차이 → DART API 값이 틀림 → 수집 때 보정
  keep       : 원문 3개월 = DART 값 → 앞 분기 재작성·반올림 차이 → 보정하지 않음
  unverified : 원문 단위가 원이 아니거나 숫자를 못 찾음 → 보정하지 않고 표시만
이미 기록된 (종목, 기간)은 다시 확인하지 않는다(추가만 한다).
Usage: python scripts/check_q_mismatch.py
"""
import io, json, os, re, sys, zipfile
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_dart_data as f

DATA = os.path.join(f.BASE_DIR, 'data')
CFG = os.path.join(f.HERE, 'q_corrections.json')
ITEMS = ['revenue', 'cogs', 'grossProfit', 'sga', 'rd', 'opIncome', 'pretax', 'netIncome']


def load_cfg():
    if os.path.exists(CFG):
        return json.load(open(CFG, encoding='utf-8'))
    return {'fixes': [], 'keep': [], 'unverified': []}


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    cfg = load_cfg()
    known = {(e['stockCode'], e['period']) for k in ('fixes', 'keep', 'unverified') for e in cfg[k]}
    cands = {}
    for fn in sorted(os.listdir(DATA)):
        m = re.match(r'financial_(\d{4})_(Q2|Q3)\.json$', fn)
        if not m:
            continue
        year, q = m.groups()
        pq = {'Q2': 'Q1', 'Q3': 'Q2'}[q]
        pp = os.path.join(DATA, f'financial_{year}_{pq}.json')
        if not os.path.exists(pp):
            continue
        cur = json.load(open(os.path.join(DATA, fn), encoding='utf-8'))['companies']
        prev = json.load(open(pp, encoding='utf-8'))['companies']
        for sc, r in cur.items():
            a, pa = r.get('amounts'), (prev.get(sc) or {}).get('amounts')
            code = sc.zfill(6)
            if not a or not pa or (code, f'{year}_{q}') in known:
                continue
            for k in ITEMS:
                qv, yv, pv = a[k][0], a[k][1], pa[k][1]
                if None in (qv, yv, pv) or qv == yv - pv:
                    continue
                cands.setdefault((code, f'{year}_{q}', r.get('rceptNo')), []).append((k, qv, yv - pv))
    print(f'새로 대조할 회사·기간: {len(cands)}')
    fmt = lambda v: f'{abs(v):,}'
    for (code, per, rc), items in sorted(cands.items()):
        fix, keep, unk = [], [], []
        try:
            r = requests.get(f.DART_BASE + '/document.xml', params={'crtfc_key': f.DART_API_KEY, 'rcept_no': rc}, timeout=60)
            z = zipfile.ZipFile(io.BytesIO(r.content))
            plain = re.sub(r'<[^>]+>', ' ', ''.join(z.read(n).decode('utf-8', errors='ignore') for n in z.namelist()))
            won = bool(re.search(r'단위\s*:\s*원\)', plain))
        except Exception as e:
            plain, won = '', False
            print(f'  {code} {per}: 원문 열기 실패({type(e).__name__}) → 미확인')
        for k, qv, ev in items:
            if not won:
                unk.append(k)
                continue
            has_o, has_e = fmt(qv) in plain, fmt(ev) in plain
            (fix if has_e and not has_o else keep if has_o and not has_e else unk).append(k)
        for key, lst, basis in (
            ('fixes', fix, f'공시 원문(접수번호 {rc}) 확인: 3개월 값이 누적 − 앞 분기 누적과 같음 (DART API 값 오류)'),
            ('keep', keep, f'공시 원문(접수번호 {rc}) 확인: 3개월 값이 DART 값과 같음 (앞 분기 재작성·반올림 차이) → 보정 안 함'),
            ('unverified', unk, f'원문 대조 불가(단위가 원이 아니거나 숫자를 못 찾음) → 보정 안 함 · 접수 {rc}'),
        ):
            if lst:
                cfg[key].append({'stockCode': code, 'period': per, 'rceptNo': rc, 'items': lst, 'basis': basis})
        print(f'  {code} {per}: 보정 {len(fix)} / 유지 {len(keep)} / 미확인 {len(unk)}')
    with open(CFG, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=1)
    print({k: sum(len(e['items']) for e in v) for k, v in cfg.items()})


if __name__ == '__main__':
    main()
