# Local Crawler

이 디렉터리는 이제 기존 자작 `worker.py`가 아니라, 사용자가 제공한 `porting/coupang_crawl_core`를 로컬에서 실행하기 위한 얇은 런처입니다.

실제 쿠팡 크롤 로직은 다음 경로를 사용합니다.

- `d:\sourcing\porting\coupang_crawl_core\coupang_crawler.py`
- `d:\sourcing\porting\coupang_crawl_core\coupang_mode2_session.py`

## 1. 설치

```powershell
cd d:\sourcing\local-crawler
python -m pip install -r requirements.txt
playwright install chromium
```

## 2. 환경변수 준비

`.env.example`을 복사해서 `.env`를 만들고 값을 채웁니다.

최소 예시:

```env
MANUAL_KEYWORD=압축수납박스
COUPANG_HEADLESS=false
COUPANG_SMOKE_HEADLESS=false
COUPANG_BRIGHT_REQUEST=off
COUPANG_SMOKE_EXTRACT_DB=false
```

선택값:

- `BRIGHTDATA_API_TOKEN`
- `BRIGHTDATA_REQUEST_ZONE`
- `COUPANG_PLAYWRIGHT_CHANNEL`
- `COUPANG_SMOKE_GOOGLE_QUERY`
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET_NAME`
- `R2_PUBLIC_BASE_URL`

## 3. 실행

기본 크롤:

```powershell
python ported_coupang.py --keyword "압축수납박스"
```

또는 `.env`의 `MANUAL_KEYWORD` 사용:

```powershell
python ported_coupang.py
```

결과는 `output/ported_last_result.json`에 저장됩니다.

## 3-1. 로컬 운영 UI

Streamlit UI 실행:

```powershell
cd d:\sourcing\local-crawler
streamlit run streamlit_app.py
```

UI에서 할 수 있는 작업:

- DB에 저장된 `final keywords` 배치 실행
- 안전 중지
- 실패 키워드 재실행
- 현재 실행 키워드/진행률/성공/실패/마지막 에러 확인
- 상품 결과 테이블 확인 (`image_url`, 가격, 리뷰수, 배송유형, 링크)
- 실행 로그 확인

주의:

- 로컬 UI는 중앙 서버의 `/api/admin/keyword-sourcing/crawler-keywords` API를 사용합니다.
- `date_value` 없이 호출할 때는 서버가 DB의 `keyword_sourcing_final_keywords` 테이블을 기준으로 배치 대상을 내려줍니다.
- UI 결과 요약 파일은 `output/ui_state.json`, `output/ui_results.json`에 저장됩니다.
- R2 설정이 채워져 있으면 배치 완료 후 결과 JSON을 `crawling/coupang/local-ui-results/` 전용 폴더 경로로 R2에도 업로드합니다.

## 4. 준비/수동 확인 모드

쿠팡 홈 열기:

```powershell
python ported_coupang.py --open-home-ready --wait-seconds 120
```

구글 홈 열기:

```powershell
python ported_coupang.py --open-google-ready --wait-seconds 120
```

쿠팡 검색창 준비:

```powershell
python ported_coupang.py --open-search-ready --wait-seconds 120
```

## 5. 1688 이미지검색 (평균단가)

`ui_results.json`의 `image_url`을 사용해 1688 유사상품 가격을 조회합니다.

사전 준비:

- `.env`에 `BRIGHTDATA_BROWSER_WS_1688` (Browser API, `-country-cn` 포함)
- (선택) `CHINA_SEARCH_TOP_N`, `CHINA_FX_CNY_TO_KRW`

실행:

```powershell
cd d:\sourcing\local-crawler
python test_bright_1688_browser.py
python china_runner.py --limit 3
python china_runner.py --limit 0
```

`--limit 0`은 전체 row 처리입니다. 결과는 `ui_results.json`에 `china_avg_price_cny`, `china_avg_price_krw`, `margin_pct_est` 필드로 merge 됩니다.

## 6. 참고

- 포팅 코어 원문: `porting/coupang_crawl_core/README.md`
- 이식 절차 문서: `PORTING_COUPANG_CRAWL.md`
- 현재 런처는 DB 저장을 기본적으로 끈 상태(`COUPANG_SMOKE_EXTRACT_DB=false`)로 실행합니다.
