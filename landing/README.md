# Landing (PWA 진입 전)

`html_PWA.txt` 기반 **BlueOcean** 마케팅 랜딩. CTA·로그인 링크는 Railway PWA(`/user`)로 이동합니다.

## 로컬 미리보기

```powershell
cd d:\sourcing\landing
python -m http.server 8080
```

http://localhost:8080

## Netlify 배포

1. Netlify → **Add site** → 이 저장소 연결
2. **Base directory**: `landing`
3. **Publish directory**: `.` (base가 landing이면 루트)

## PWA URL 변경

`js/config.js`:

```js
pwaUrl: "https://sourcing-production-8102.up.railway.app/user",
```

## 히어로 배너 이미지

배경 이미지: `images/hero-banner.png` (교체 시 동일 파일명 권장)

문구·스타일 수정: `partials/hero-banner.html`, `css/hero.css`

## HTML 다시 생성

원본 `html_PWA.txt` 수정 후:

```powershell
python d:\sourcing\landing\_build_landing.py
```

`index.html`이 재생성됩니다 (사이드바·하단 앱 탭은 제거된 상태).
