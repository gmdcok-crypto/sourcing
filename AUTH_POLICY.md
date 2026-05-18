# Auth Policy

우리 소싱 솔루션의 사용자 인증, 기기 제한, 이메일 인증코드 정책에 대한 기획 문서.

주의사항:

- 이 문서는 기획 기준 문서이며, 실제 코드 반영은 별도 요청 시 진행한다.
- 서비스는 `1계정당 최대 2개 기기 허용` 정책을 기본으로 한다.
- 인증은 단순 로그인만이 아니라 `계정 인증 + 기기 인증 + 세션 관리`를 함께 고려한다.

## 기본 인증 원칙

- 계정 인증은 `이메일 + 비밀번호` 기반으로 진행한다.
- 기기 인증은 `이메일 인증코드` 기반으로 진행한다.
- 기존 등록 기기는 바로 로그인 가능하다.
- 신규 기기는 이메일 인증코드를 통과한 뒤 등록 및 로그인 가능하다.

한 줄 요약:

`계정은 이메일/비밀번호로 인증하고, 기기는 이메일 코드로 승인한다.`

## 기기 정책

- 한 계정은 최대 2개 기기까지 로그인 유지 가능하다.
- 기기 제한은 브라우저 수가 아니라 `등록된 기기 슬롯` 개념으로 관리한다.
- 새 기기에서 로그인할 경우:
  - 빈 슬롯이 있으면 새 기기를 등록한다.
  - 이미 2개가 등록되어 있으면 기존 기기 1개를 해제해야 한다.
- 사용자는 자신의 등록 기기 목록을 보고 직접 해제할 수 있어야 한다.
- 관리자는 관리자 화면에서 특정 사용자의 기기를 강제 해제할 수 있어야 한다.

## 기기 식별 방식

PWA 환경에서는 네이티브 디바이스 ID 대신 `device_id`를 사용한다.

- 최초 로그인 전 또는 로그인 시점에 클라이언트가 `device_id`를 생성한다.
- `device_id`는 localStorage 또는 이에 준하는 저장소에 보관한다.
- 서버는 계정과 `device_id`를 묶어 등록 기기로 관리한다.

저장 권장 항목:

- `device_id`
- `device_name`
- `user_agent`
- `platform`
- `first_logged_in_at`
- `last_seen_at`
- `last_ip`
- `is_active`

## 이메일 인증코드 정책

이메일 인증코드는 다음 상황에서 사용한다.

- 회원가입 시 이메일 확인
- 신규 기기 로그인 승인
- 비밀번호 재설정
- 민감 설정 변경 시 재인증

권장 스펙:

- `6자리 숫자 코드`
- 유효시간 `5분`
- 최대 입력 시도 `5회`
- 1회 사용 후 즉시 만료
- 재발송 쿨다운 `30~60초`

초기 버전에서는 매직링크보다 `숫자 코드 방식`을 우선 적용하는 것이 좋다.

## 로그인 프로세스

### 1. 기존 등록 기기 로그인

1. 사용자가 이메일/비밀번호를 입력한다.
2. 서버가 계정 정보를 검증한다.
3. 전달된 `device_id`가 기존 등록 기기인지 확인한다.
4. 등록 기기라면 바로 로그인 허용한다.
5. access token / refresh token을 발급한다.

### 2. 신규 기기 로그인

1. 사용자가 이메일/비밀번호를 입력한다.
2. 서버가 계정 정보를 검증한다.
3. 전달된 `device_id`가 신규 기기인지 확인한다.
4. 신규 기기라면 이메일로 인증코드를 발송한다.
5. 사용자가 인증코드를 입력한다.
6. 코드 검증이 성공하면 기기 등록 가능 여부를 확인한다.
7. 등록 슬롯이 남아 있으면 기기를 등록한다.
8. access token / refresh token을 발급한다.

### 3. 기기 슬롯 초과

1. 신규 기기 로그인 시 이미 2개 기기가 등록된 경우
2. 서버는 `device_limit_exceeded` 상태를 반환한다.
3. 사용자에게 기존 등록 기기 목록을 보여준다.
4. 사용자가 해제할 기기를 선택한다.
5. 기존 기기를 비활성화하고 현재 기기를 등록한다.
6. access token / refresh token을 발급한다.

## 토큰 정책

토큰은 `access token + refresh token` 구조로 운영한다.

### Access Token

- 수명은 짧게 유지한다.
- 권장 만료시간은 `15분 ~ 1시간`
- API 인증용으로 사용한다.

### Refresh Token

- 수명은 길게 유지한다.
- 권장 만료시간은 `30일`
- 기기 단위 세션으로 관리한다.
- 가능하면 원문 저장이 아니라 `hash` 저장을 권장한다.

핵심 원칙:

- access token은 짧고 가볍게
- refresh token은 기기 단위 세션의 핵심 키로 관리

## 권장 API 흐름

### `POST /auth/login`

입력 예시:

- email
- password
- device_id
- device_name
- user_agent

응답:

- 기존 등록 기기면 바로 토큰 발급
- 신규 기기면 이메일 코드 발송 또는 코드 검증 단계로 이동
- 기기 초과 시 `DEVICE_LIMIT_EXCEEDED` 반환

### `POST /auth/verify-code`

입력 예시:

- email
- device_id
- code
- purpose

동작:

- 이메일 인증코드 검증
- 성공 시 기기 등록 또는 후속 로그인 허용

### `POST /auth/refresh`

입력 예시:

- refresh_token
- device_id

동작:

- 해당 기기의 활성 세션인지 검증
- 맞으면 새 access token 발급

### `POST /auth/logout`

동작:

- 현재 기기 세션 종료

### `POST /auth/logout-all`

동작:

- 모든 기기 세션 종료

### `POST /auth/device/replace`

동작:

- 기존 등록 기기 1개 해제
- 현재 신규 기기 등록
- 새 토큰 발급

## 데이터 저장 구조 제안

### `users`

- id
- email
- password_hash
- status
- created_at

### `user_devices`

- id
- user_id
- device_id
- device_name
- user_agent
- platform
- first_logged_in_at
- last_seen_at
- revoked_at
- is_active

### `user_sessions`

- id
- user_id
- device_id
- refresh_token_hash
- expires_at
- revoked_at
- created_at
- last_used_at
- ip_address

### `auth_verification_codes`

- id
- user_id
- email
- device_id
- purpose
- code_hash
- expires_at
- attempt_count
- verified_at
- created_at

## UX 원칙

인증 UX는 복잡하게 보이지 않아야 한다.

권장 문구:

- `이메일로 전송된 인증코드를 입력해주세요.`
- `이 계정은 최대 2개 기기까지 사용할 수 있습니다.`
- `새 기기를 등록하려면 기존 기기 1개를 해제해야 합니다.`

사용자에게 보여줄 기기 정보:

- 기기 이름
- 브라우저/플랫폼
- 최근 접속 시간

## 관리자 기능 연계

관리자 화면에서는 사용자별 기기 세션을 관리할 수 있어야 한다.

필요 기능:

- 사용자별 등록 기기 수 확인
- 활성 기기 목록 확인
- 특정 기기 강제 로그아웃
- 모든 기기 세션 초기화
- 최근 IP / user agent 확인

## 결론

최종 인증 방향은 다음과 같다.

- 로그인은 이메일/비밀번호 기반으로 한다.
- 신규 기기 로그인에는 이메일 인증코드를 사용한다.
- 한 계정당 최대 2개 기기만 허용한다.
- 기기 등록 후 기기 단위 세션에 대해 토큰을 발급한다.
- refresh token 중심으로 기기 세션을 관리한다.

한 줄 요약:

`최초 로그인 시 단순 토큰 발급이 아니라, 기기 등록 후 그 기기 세션에 대한 토큰을 발급하는 구조로 설계한다.`
