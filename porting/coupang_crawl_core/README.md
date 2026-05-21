# Coupang crawl core — 이식용 복사본

BlueOcean `docs/PORTING_COUPANG_CRAWL.md` **§11.1** 파일을 이 폴더에 모아 둔 **스냅샷**입니다.  
다른 프로젝트에는 이 디렉터리 통째로 복사한 뒤, 프로젝트 루트에 맞게 import·`db` 통합을 하세요.

> **주의:** 원본과 **동기화되지 않습니다.** BlueOcean에서 크롤 로직을 수정하면 필요 시 이 폴더를 다시 갱신하세요.

---

## 포함 파일

| 경로 | 설명 |
|------|------|
| `coupang_crawler.py` | Bright + Playwright + 스모크 worker |
| `coupang_mode2_session.py` | Tab4 2번 — 단일창 연속 수집 |
| `coupang_mode2_probe_eval.js` | Top10 DOM probe (스모크와 동일 로직 유지) |
| `coupang_ranked_data.py` | 순위표 resolver (memory → DB → JSON) |
| `coupang_partners_api.py` | Partners API + Throttler (**§11.1 선택**, throttler 테스트용 포함) |
| `db.py` | BlueOcean **전체** DB 모듈 복사본 — coupang INSERT/QUERY 포함. 새 프로젝트에서는 **coupang 관련 함수만 발췌** 권장 |
| `sql/003_coupang_keyword_snapshot_mariadb.sql` | `coupang_search_runs`, `coupang_search_ranked_items` |
| `sql/007_coupang_autocollect_mode2_usage.sql` | Mode2 배치 usage (2번 자동수집) |
| `tests/test_coupang_bright_request.py` | Bright gating 단위 테스트 |
| `tests/test_coupang_throttler.py` | Partners throttler 테스트 |

---

## 이식 후 최소 연결

1. `pip install playwright playwright-stealth requests beautifulsoup4 pymysql pandas`
2. `playwright install --with-deps chromium`
3. SQL `003` (+ Mode2면 `007`) 적용
4. DB DSN 환경변수 설정
5. 루트에서: `python coupang_crawler.py --keyword "테스트"`

체크리스트 전체: `docs/PORTING_COUPANG_CRAWL.md` **§12**

---

## 런타임 디렉터리 (복사하지 않음, 실행 시 생성)

```
.coupang_chrome_profile_crawl/
.coupang_chrome_profile_prep/
.smoke/coupang_state.json
.smoke/last_smoke_extract.json
```

---

## BlueOcean에 없는 것 (별도 구현)

- Streamlit Tab3/4 UI (`coupang_tab.py`, `view_pages/04_*.py`)
- 키워드 큐 (`recommended_keyword_candidates`, batch_token)
- Naver datalab / 추천 엔진

상세: `docs/PORTING_COUPANG_CRAWL.md` §11.2
