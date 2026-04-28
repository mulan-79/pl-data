# DART 재무정보 조회 시스템

정적 웹사이트 형태로 제작된 DART 재무정보 조회 도구입니다.

## 포함 파일

- `dart_financial_website.html`: 메인 웹 애플리케이션
- `index.html`: Cloudflare Pages 진입용 리다이렉트 파일
- `industry_data.json`: 업종/기업 데이터
- `USAGE_GUIDE.md`: 사용 가이드
- `dart_system_guide.png`: 시각적 안내 이미지

## 로컬 실행

브라우저에서 `index.html` 또는 `dart_financial_website.html` 파일을 직접 열어 확인할 수 있습니다.

## GitHub 업로드

```bash
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

## Cloudflare Pages 배포

1. Cloudflare Dashboard > Workers & Pages > Create > Pages > Connect to Git
2. GitHub 저장소 선택
3. Framework preset: `None`
4. Build command: 비워둠
5. Build output directory: `/`
6. Deploy

정적 사이트이므로 별도 빌드 과정 없이 즉시 배포됩니다.
