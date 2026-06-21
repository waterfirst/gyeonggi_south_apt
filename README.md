# 아파트 왓 — 경기 남부 아파트 실거래가

> [heekeunlee/seoul_apt](https://github.com/heekeunlee/seoul_apt) 포크 → 경기 남부판.
> 국토부 실거래가 + 네이버/크롬 MCP 좌표 → 지도 대시보드. GitHub Actions로 매일 09시(KST) 자동 갱신.

## 대상 지역 (경기 남부 31개 시군구, 국토부 API 실측 검증 완료)
수원(4구)·성남(3구)·용인(3구)·안양(2구)·안산(2구)·부천(3구)·화성·평택·오산·시흥·군포·의왕·광명·과천·하남·이천·안성·김포·광주·여주
- 필터: 20억 이하 · 전용 84㎡ 이상 · 최근 12개월
- 우선관심(파란색): 용인 수지·성남 분당·수원 영통·과천·안양 동안·하남 — `scripts/fetch_data.py`의 `PRIORITY_DISTRICTS`에서 편집

## ⚙️ 셋업 (필수)
1. **GitHub Actions secrets** (Settings → Secrets and variables → Actions)에 본인 키 등록:
   - `MOLIT_API_KEY` — 국토부 실거래가(공공데이터포털 RTMSDataSvcAptTradeDev) 키
   - `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` — 네이버 지역검색 API (좌표 조회용, 없어도 데이터는 수집됨)
   - ※ 원본의 하드코딩 키는 보안상 제거됨(헌법 제2조). 반드시 본인 키 사용.
2. **Actions 활성화** 후 `workflow_dispatch`로 수동 1회 실행 → `data/transactions.json` 생성.
3. **지도 경계(geojson)**: `index.html`의 `GEO_URL`이 `./data/gyeonggi_south.geojson`을 가리킴. 경기 남부 시군구 geojson 추가 필요(구별 경계 오버레이용). 없어도 거래표/네이버링크는 작동.

## 변경 이력 (fork)
- `scripts/fetch_data.py`: 서울 25구 → 경기 남부 31시군구(코드 API 검증). 부천 41190→원미/소사/오정, 화성 41590→41591 정정. 하드코딩 키 제거.
- `index.html`/`dashboard.js`: 타이틀·라벨·지도 중심좌표(37.30,127.05)·geojson 경로 변경.

## 내 갈아타기 분석
- `analysis.html` — 대화 기반 의사결정 분석(생애단계·반도체클러스터·구성역·추천단지·점수·체크리스트). 메인 우상단 "🧭 내 갈아타기 분석"에서 진입.
