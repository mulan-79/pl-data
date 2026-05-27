#!/usr/bin/env python3
"""
네이버 증권 테마 데이터 수집 스크립트
- 테마 목록 (263개) + 각 테마별 종목 수집
- theme_data.json 저장
"""
import requests, re, json, time, os, sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT   = os.path.join(BASE_DIR, 'theme_data.json')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://finance.naver.com/',
}

def fetch(url, encoding='euc-kr', retry=3):
    for attempt in range(retry):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.encoding = encoding
            return r.text
        except Exception as e:
            if attempt < retry - 1:
                time.sleep(2)
            else:
                print(f'  fetch 실패: {url} -> {e}')
                return ''

def get_all_themes():
    """테마 목록 전체 수집 (페이지 순회)"""
    themes = {}
    for page in range(1, 20):
        html = fetch(f'https://finance.naver.com/sise/theme.naver?page={page}')
        matches = re.findall(
            r'sise_group_detail\.naver\?type=theme&no=(\d+)"[^>]*>([^<]+)</a>', html)
        if not matches:
            break
        new = {no: name.strip() for no, name in matches if no not in themes}
        if not new:
            break
        themes.update(new)
        print(f'  page {page}: {len(themes)}개 누계')
        time.sleep(0.3)
    return themes  # {no: name}

def get_theme_stocks(theme_no):
    """테마 상세 페이지에서 종목 코드+이름 수집"""
    html = fetch(
        f'https://finance.naver.com/sise/sise_group_detail.naver?type=theme&no={theme_no}')
    # 종목 링크: /item/main.naver?code=005930 > 회사명
    stocks = re.findall(
        r'/item/main\.naver\?code=([A-Z0-9]{6})"[^>]*>\s*([^<]+)\s*</a>', html)
    return [{'stock_code': sc.lstrip('0') or sc, 'name': name.strip()}
            for sc, name in stocks]

def main():
    print('=== 네이버 증권 테마 데이터 수집 ===')

    # 1. 테마 목록
    print('\n[1단계] 테마 목록 수집...')
    themes_map = get_all_themes()
    print(f'총 {len(themes_map)}개 테마')

    # 2. 각 테마별 종목
    print('\n[2단계] 테마별 종목 수집...')
    theme_list = []
    companies  = {}
    no_stock   = []

    items = list(themes_map.items())
    for idx, (no, name) in enumerate(items):
        stocks = get_theme_stocks(no)
        theme_list.append({'code': no, 'name': name})
        companies[no] = stocks

        if not stocks:
            no_stock.append(name)
        if (idx + 1) % 20 == 0 or (idx + 1) == len(items):
            print(f'  [{idx+1}/{len(items)}] {name[:20]}: {len(stocks)}개')
        time.sleep(0.25)

    # 3. 저장
    theme_data = {
        'themes':    sorted(theme_list, key=lambda x: x['name']),
        'companies': companies,
    }
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(theme_data, f, ensure_ascii=False, indent=2)

    total_stocks = sum(len(v) for v in companies.values())
    print(f'\n저장 완료: {OUTPUT}')
    print(f'테마: {len(theme_list)}개 | 종목 매핑: {total_stocks}건')
    if no_stock:
        print(f'종목 없는 테마 {len(no_stock)}개: {no_stock[:5]}')

if __name__ == '__main__':
    main()
