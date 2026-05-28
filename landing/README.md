# Modiba GoodPrice — Netlify 랜딩

다크 모드 마케팅 랜딩 페이지. **방법 A**: Netlify(메인 도메인) → 로그인 → Railway PWA.

## 로컬 미리보기

```bash
cd landing
npx --yes serve .
# http://localhost:3000
```

## Netlify 배포

1. Netlify → **Add site** → Import Git → 이 저장소
2. **Base directory**: `landing`
3. **Publish directory**: `landing` (또는 base가 landing이면 `.`)
4. **Build command**: 비움 (정적 HTML)

또는 Netlify CLI:

```bash
cd landing
netlify deploy --prod
```

## PWA URL 변경

`js/config.js`:

```js
window.SOURCING_APP = {
  pwaUrl: "https://sourcing.yourdomain.com/user",
};
```

## 로그인 (추후)

현재 CTA·로그인 버튼은 `config.pwaUrl`로 리다이렉트합니다.  
카카오/네이버/이메일 OAuth 연동 시 `js/main.js`의 `goToApp` 전에 Netlify Identity / Supabase Auth 등을 붙이면 됩니다.

## 관련 문서

- [PWA 커스텀 도메인](../docs/PWA_CUSTOM_DOMAIN_SETUP.md)
