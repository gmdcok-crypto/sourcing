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

## 5. 참고

- 포팅 코어 원문: `porting/coupang_crawl_core/README.md`
- 이식 절차 문서: `PORTING_COUPANG_CRAWL.md`
- 현재 런처는 DB 저장을 기본적으로 끈 상태(`COUPANG_SMOKE_EXTRACT_DB=false`)로 실행합니다.
