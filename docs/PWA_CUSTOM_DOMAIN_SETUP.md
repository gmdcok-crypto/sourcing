# PWA 커스텀 도메인 연결 가이드 (WHOIS DNS + Netlify + Railway)

메인 사이트는 **Netlify**, 소싱 PWA·API는 **Railway**에 두고, DNS는 **WHOIS**에서 관리하는 구성을 기준으로 정리한 문서입니다.

---

## 1. 권장 구조

| 용도 | URL 예시 | 연결 대상 |
|------|----------|-----------|
| 메인 프론트 (랜딩·마케팅) | `https://yourdomain.com` / `https://www.yourdomain.com` | **Netlify** |
| PWA 사용자 화면 | `https://sourcing.yourdomain.com/user` | **Railway** |
| PWA API | `https://sourcing.yourdomain.com/api/user/feed` | **Railway** |
| Admin | `https://sourcing.yourdomain.com/admin` (동일 앱) | **Railway** |

**원칙:** 루트 도메인(`@`)은 Netlify만 사용하고, Railway에는 **서브도메인 하나**만 연결합니다.

```
[방문자]
   yourdomain.com           → WHOIS DNS → Netlify (메인 프론트)
   sourcing.yourdomain.com  → WHOIS DNS → Railway (PWA / API / Admin)
```

현재 Railway 기본 URL (참고):

- `https://sourcing-production-8102.up.railway.app`

---

## 2. 왜 서브도메인으로 나누는가

| 방식 | 평가 |
|------|------|
| **서브도메인 분리** (`sourcing.` → Railway, `@` → Netlify) | ✅ 권장. DNS 충돌 없음, SSL·API 경로 단순 |
| **URL 리다이렉트만** (내 도메인 → Railway URL) | △ 짧은 링크용. 주소가 Railway로 바뀌거나 API 경로 꼬일 수 있음 |
| **루트 도메인을 Railway와 Netlify에 동시 연결** | ❌ 불가. 한 호스트는 한 목적지만 |

PWA HTML·`/api/user/*`·1688 이미지 프록시는 **같은 origin(같은 서브도메인)** 이면 CORS·북마크·공유 URL이 단순해집니다.

---

## 3. 사전 준비

- [ ] WHOIS에서 도메인 등록·**DNS 관리(네임서버)** 사용 중인지 확인  
  - WHOIS “DNS 관리”에 A/CNAME 레코드가 보이면 WHOIS DNS 사용 중
  - 네임서버를 Netlify로만 바꿔 둔 경우 → 레코드는 **Netlify DNS**에 넣어야 함 (이 문서는 WHOIS DNS 기준)
- [ ] Netlify에 `@` / `www` 연결 완료 (메인 프론트 정상 동작)
- [ ] Railway 프로젝트 배포·기본 URL 접속 확인
- [ ] 사용할 서브도메인 이름 결정 (예: `sourcing`, `app`, `pwa`)

---

## 4. 설정 절차

### 4.1 Railway — 커스텀 도메인 등록

1. [Railway](https://railway.app) → 해당 프로젝트 → **서비스** 선택  
2. **Settings** → **Networking** → **Custom Domain**  
3. 도메인 입력: `sourcing.yourdomain.com` (실제 도메인·서브도메인으로 변경)  
4. Railway가 표시하는 **CNAME 대상** 복사  
   - 예: `xxxx.up.railway.app`  
5. SSL 인증서는 도메인 검증 후 자동 발급 (수분~1시간)

### 4.2 WHOIS — DNS 레코드 추가

WHOIS → **내 도메인** → **DNS 관리** (또는 DNS 설정)

#### 유지 (메인 → Netlify)

이미 Netlify 연결되어 있다면 **수정하지 않음**:

| 타입 | 호스트(이름) | 값 | 비고 |
|------|--------------|-----|------|
| A | `@` | Netlify 안내 IP | 메인 루트 |
| CNAME | `www` | `xxxx.netlify.app` | www (Netlify 설정에 따름) |

#### 신규 추가 (PWA → Railway)

| 타입 | 호스트(이름) | 값/대상 | TTL |
|------|--------------|---------|-----|
| **CNAME** | `sourcing` | Railway가 준 CNAME (예: `xxxx.up.railway.app`) | 기본값(300~3600) |

**입력 시 주의**

- 호스트 칸에 `sourcing.yourdomain.com` 전체가 아니라 **`sourcing`만** 입력하는 UI가 많음  
- `@`(루트) 레코드는 Railway용으로 바꾸지 않음  

### 4.3 전파·SSL 확인

1. DNS 전파 대기 (보통 5분~1시간, 최대 48시간)  
2. Railway 대시보드에서 커스텀 도메인 상태 **Active** / SSL **Valid** 확인  
3. 브라우저에서 접속 테스트:  
   - `https://sourcing.yourdomain.com/user` — PWA  
   - `https://sourcing.yourdomain.com/api/user/feed` — 피드 API (JSON)

### 4.4 Netlify 메인 사이트에서 링크

- 메인 프론트 버튼·메뉴 URL: `https://sourcing.yourdomain.com/user`  
- `sourcing.yourdomain.com`을 Netlify “Custom domains”에 **등록할 필요 없음** (WHOIS → Railway만 연결)

---

## 5. WHOIS DNS 자주 묻는 점

| 질문 | 답변 |
|------|------|
| NS(네임서버)는 어디에 두나? | WHOIS 기본 NS → 레코드는 WHOIS DNS 관리에만 추가 |
| NS를 Netlify로 옮겼나? | 레코드는 Netlify DNS에 추가. WHOIS DNS 화면은 사용 안 함 |
| 루트(`@`)에 CNAME? | 많은 DNS에서 `@` CNAME 불가 → 루트는 Netlify **A**, Railway는 **서브도메인 CNAME** |
| WHOIS에 Cloudflare式 프록시? | WHOIS는 보통 없음. CNAME이 Railway로 직접 연결됨 |

---

## 6. 배포 후 앱 설정 (작업 시)

도메인 연결 후 코드·환경 변수를 새 베이스 URL에 맞출 때 참고:

| 항목 | 변경 예 |
|------|---------|
| 로컬 크롤러 `RAILWAY_API_BASE_URL` | `https://sourcing.yourdomain.com` |
| Admin·외부 연동 문서/북마크 | 동일 도메인 |
| (선택) 루트 `/` → PWA 리다이렉트 | FastAPI에서 `/` → `/user` 302 |

파일 예: `local-crawler/.env.example` 의 `RAILWAY_API_BASE_URL`

---

## 7. 다른 방식 요약 (참고)

### 7.1 URL 리다이렉트만 (302/301)

- `https://yourdomain.com/pwa` → Railway `/user` 로 리다이렉트  
- **단점:** 최종 URL이 Railway로 바뀌거나 상대 API 경로가 어긋날 수 있음 → 운영 PWA 도메인으로는 비권장  

### 7.2 본인 서버 Nginx 리버스 프록시

- `sourcing.yourdomain.com` → Nginx → `sourcing-production-8102.up.railway.app`  
- WHOIS CNAME을 **본인 서버 IP**로 두고 Nginx에서 프록시  
- Railway 커스텀 도메인 대신 쓸 수 있으나 서버·SSL 직접 관리 필요  

### 7.3 Cloudflare를 WHOIS 앞에 두는 경우

- DNS를 Cloudflare로 이전하거나 CNAME flattening 사용 시  
- `sourcing`만 Proxied(주황 구름) → Railway  
- `/api/*` 는 Cache Bypass 권장 (동적 API)  

---

## 8. 체크리스트

- [ ] Railway Custom Domain: `sourcing.yourdomain.com` 등록  
- [ ] WHOIS DNS: `sourcing` CNAME → Railway CNAME 대상  
- [ ] WHOIS DNS: `@` / `www` Netlify 레코드 유지  
- [ ] SSL Active 후 `https://sourcing.yourdomain.com/user` 확인  
- [ ] Netlify 메인에서 PWA 링크 업데이트  
- [ ] (선택) `RAILWAY_API_BASE_URL` 등 env 갱신  

---

## 9. 문제 해결

| 증상 | 확인 |
|------|------|
| `sourcing`만 안 열림 | WHOIS CNAME 호스트·값 오타, 전파 대기 |
| SSL pending | Railway 도메인 검증 대기, CNAME이 Railway 대상과 일치하는지 |
| 메인(`www`) 깨짐 | `@`/`www` 레코드를 Railway로 바꾸지 않았는지 |
| PWA는 되는데 API 404 | 같은 서브도메인인지, 경로 `/api/user/...` 확인 |

---

## 10. 관련 URL (현재 프로덕션)

| 서비스 | 경로 |
|--------|------|
| PWA | `/user` |
| 피드 API | `/api/user/feed` |
| Admin | `/admin` |

커스텀 도메인 적용 후에도 **경로는 동일**하고, 호스트만 `sourcing.yourdomain.com` 으로 바뀝니다.

---

*작성 기준: Railway 프로덕션 `sourcing-production-8102.up.railway.app`, DNS WHOIS, 메인 프론트 Netlify.*
