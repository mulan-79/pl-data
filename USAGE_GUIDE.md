
# 🚀 DART 재무정보 조회 시스템 - Claude Code 사용 가이드

## 📦 준비된 파일들
1. **dart_financial_website.html** - 완성된 웹사이트 (단일 파일)
2. **industry_data.json** - 업종/기업 데이터 (참고용)

---

## 🎯 시스템 특징

### ✅ 포함된 데이터
- **총 상장사**: 805개 (코스닥 포함)
- **업종 분류**: 58개 산업
- **기본 설정**: 의료용 물질 및 의약품 제조업 (45개 기업)

### 🎨 디자인 특징
- **현대적인 그라데이션 UI**: 보라색 계열 색상
- **반응형 디자인**: 모바일/태블릿/데스크톱 모두 지원
- **인터랙티브**: 호버 효과, 애니메이션
- **직관적 UX**: 3단계 선택 (API키 → 업종 → 기업)

### 🔧 주요 기능
1. **업종별 필터링**: 58개 업종 중 선택 가능
2. **기업 검색**: 선택한 업종의 모든 상장사 표시
3. **DART API 연동**: 실시간 재무정보 조회
4. **재무정보 시각화**: 
   - 주요 지표 카드 (총자산, 매출액, 영업이익, 당기순이익)
   - 상세 재무제표 테이블
   - 전기 대비 비교

---

## 🖥️ Claude Code에서 사용하는 방법

### 방법 1: HTML 파일 직접 업로드
1. **dart_financial_website.html** 파일 다운로드
2. Claude에게 다음과 같이 요청:
   ```
   이 HTML 파일을 실행해서 웹사이트로 보여줘
   ```

### 방법 2: 코드 복사/붙여넣기
HTML 파일의 전체 코드를 복사하여 Claude에게 다음과 같이 요청:
```
다음 HTML 코드를 artifact로 실행해줘

[여기에 HTML 코드 붙여넣기]
```

---

## 🔑 DART API 키 설정 방법

### 1. API 키 발급 (이미 완료하셨다면 생략)
1. https://opendart.fss.or.kr/ 접속
2. 회원가입 및 로그인
3. "인증키 신청/관리" 메뉴 클릭
4. 이메일 인증 후 API 키 발급

### 2. 웹사이트에서 사용
- 웹사이트 상단 "DART API 인증키" 입력란에 발급받은 키 입력
- 입력 후 기업 선택 및 조회 가능

---

## 📱 사용 흐름

```
1. API 키 입력
   ↓
2. 업종 선택 (기본값: 의료용 물질 및 의약품 제조업)
   ↓
3. 기업 선택 (예: 삼성바이오로직스)
   ↓
4. "재무정보 조회" 버튼 클릭
   ↓
5. 실시간 DART 데이터 표시
```

---

## ⚙️ 기술 스펙

### 사용 기술
- **HTML5**: 시맨틱 마크업
- **CSS3**: 그라데이션, 애니메이션, Flexbox, Grid
- **Vanilla JavaScript**: 외부 라이브러리 없음
- **DART Open API**: 금융감독원 공식 API

### 브라우저 지원
- Chrome, Edge, Safari, Firefox (최신 버전)
- 모바일 브라우저 완벽 지원

### API 엔드포인트
```javascript
// 재무제표 조회
https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json
Parameters:
- crtfc_key: API 인증키
- corp_code: 기업 고유번호
- bsns_year: 사업연도
- reprt_code: 보고서 코드 (11011=사업보고서)
```

---

## 🎨 커스터마이징 가능 항목

### 색상 변경
```css
/* 메인 색상 (그라데이션) */
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);

/* 다른 색상 예시 */
/* 파란색 계열 */
background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);

/* 초록색 계열 */
background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);

/* 주황색 계열 */
background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
```

### 기본 업종 변경
```javascript
// 현재: 의료용 물질 및 의약품 제조업 (32100)
document.getElementById('industrySelect').value = '32100';

// 변경 예시: 전자부품 제조업 (32600)
document.getElementById('industrySelect').value = '32600';
```

### 표시 항목 수정
```javascript
// 재무제표 표시 행 수 (현재 20개)
financialItems.slice(0, 20).forEach(item => {
    // ...
});

// 50개로 변경
financialItems.slice(0, 50).forEach(item => {
    // ...
});
```

---

## ⚠️ CORS 이슈 해결 방법

브라우저에서 직접 DART API 호출 시 CORS 에러가 발생할 수 있습니다.

### 해결 방법

#### 방법 1: 백엔드 프록시 서버 구축 (권장)

**Node.js + Express 예시:**
```javascript
const express = require('express');
const axios = require('axios');
const cors = require('cors');

const app = express();
app.use(cors());

app.get('/api/financial', async (req, res) => {
    const { apiKey, corpCode, year } = req.query;
    const url = `https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json?crtfc_key=${apiKey}&corp_code=${corpCode}&bsns_year=${year}&reprt_code=11011`;

    try {
        const response = await axios.get(url);
        res.json(response.data);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.listen(3000, () => console.log('Server running on port 3000'));
```

**Python + Flask 예시:**
```python
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

@app.route('/api/financial')
def get_financial_data():
    api_key = request.args.get('apiKey')
    corp_code = request.args.get('corpCode')
    year = request.args.get('year')

    url = f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json?crtfc_key={api_key}&corp_code={corp_code}&bsns_year={year}&reprt_code=11011"

    response = requests.get(url)
    return jsonify(response.json())

if __name__ == '__main__':
    app.run(port=3000)
```

#### 방법 2: CORS Proxy 사용 (개발/테스트용)
```javascript
// 기존 URL 앞에 CORS Proxy 추가
const proxyUrl = 'https://cors-anywhere.herokuapp.com/';
const apiUrl = 'https://opendart.fss.or.kr/api/...';
fetch(proxyUrl + apiUrl)
```

⚠️ **주의**: CORS Proxy는 프로덕션 환경에서 사용하지 마세요!

#### 방법 3: 브라우저 확장 프로그램 (로컬 테스트용)
- Chrome: "Allow CORS: Access-Control-Allow-Origin"
- Firefox: "CORS Everywhere"

---

## 📊 데이터 구조

### 업종 데이터 형식
```json
{
  "industries": [
    {
      "code": "32100",
      "name": "의료용 물질 및 의약품 제조업"
    }
  ],
  "companies": {
    "32100": [
      {
        "stock_code": "207940",
        "name": "삼성바이오로직스(주)",
        "industry_code": "32100",
        "industry_name": "의료용 물질 및 의약품 제조업"
      }
    ]
  }
}
```

### DART API 응답 예시
```json
{
  "status": "000",
  "message": "정상",
  "list": [
    {
      "account_nm": "매출액",
      "thstrm_amount": "850000000000",
      "frmtrm_amount": "780000000000"
    }
  ]
}
```

---

## 🐛 트러블슈팅

### Q1: API 호출이 안 됩니다
**A**: 
1. API 키가 올바른지 확인
2. 기업 코드가 정확한지 확인
3. CORS 이슈인 경우 → 백엔드 프록시 서버 구축
4. API 사용량 제한 확인 (일 10,000건)

### Q2: 재무정보가 표시되지 않습니다
**A**:
1. 해당 기업의 사업보고서가 제출되었는지 확인
2. 조회 연도 변경 (최근 2-3년 시도)
3. 콘솔에서 에러 메시지 확인

### Q3: 모바일에서 레이아웃이 깨집니다
**A**: 
- 최신 브라우저 사용 권장
- 브라우저 확대/축소 100% 확인
- CSS 미디어 쿼리 확인

---

## 🔄 업데이트 계획

### 추가 가능한 기능
1. **차트 시각화**: Chart.js로 재무 트렌드 그래프
2. **비교 분석**: 여러 기업 동시 비교
3. **엑셀 다운로드**: 재무정보 Excel 내보내기
4. **북마크**: 즐겨찾는 기업 저장
5. **알림 설정**: 공시 알림 기능
6. **AI 분석**: 재무제표 자동 분석 및 코멘트

### Chart.js 추가 예시
```html
<!-- head에 추가 -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<!-- body에 추가 -->
<canvas id="financialChart"></canvas>

<script>
const ctx = document.getElementById('financialChart').getContext('2d');
const chart = new Chart(ctx, {
    type: 'bar',
    data: {
        labels: ['매출액', '영업이익', '당기순이익'],
        datasets: [{
            label: '당기',
            data: [850, 120, 95],
            backgroundColor: '#667eea'
        }, {
            label: '전기',
            data: [780, 105, 82],
            backgroundColor: '#764ba2'
        }]
    }
});
</script>
```

---

## 📞 지원

### DART API 문의
- 공식 사이트: https://opendart.fss.or.kr/
- 고객센터: 1577-2299
- 이메일: opendart@fss.or.kr

### API 개발 가이드
- https://opendart.fss.or.kr/guide/main.do

---

## 📝 라이선스 & 저작권

- **DART API**: 금융감독원 제공 (무료, 상업적 이용 가능)
- **상장사 데이터**: 금융감독원 공개 정보
- **코드**: 자유롭게 사용 및 수정 가능

---

## ✨ 마무리

이 시스템은 **즉시 사용 가능한 완제품**입니다!

**Claude Code에서 바로 실행하려면:**
```
dart_financial_website.html 파일을 artifact로 보여줘
```

**성공적인 사용을 기원합니다! 🎉**
