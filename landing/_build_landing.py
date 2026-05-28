"""Build landing/index.html from html_PWA.txt (Kakao export)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = Path(r"c:\Users\gmdco\OneDrive\문서\카카오톡 받은 파일\html_PWA.txt")
OUT = ROOT / "index.html"
HERO = ROOT / "partials" / "hero-banner.html"
PWA_URL = "https://sourcing-production-8102.up.railway.app/user"

raw = SRC.read_text(encoding="utf-8")
body = re.sub(r"<veepn-lock-screen.*", "", raw, flags=re.S)
body = re.sub(r"<template[^>]*>.*", "", body, flags=re.S)
body = re.sub(r"^<body[^>]*>", "", body)
body = re.sub(r"</body>\s*$", "", body).strip()
body = body.replace(' ap-style=""', "")

# Drop desktop app sidebar; keep main marketing column.
aside_end = body.find("</aside>")
if aside_end >= 0:
    body = body[aside_end + len("</aside>") :].strip()

# Drop mobile bottom tab bar (app routes not used on static landing).
body = re.sub(
    r'<nav[^>]*class="[^"]*fixed bottom-0[^"]*"[^>]*>.*?</nav>',
    "",
    body,
    flags=re.S,
)

# Extension / crawler injected nodes.
body = re.sub(r'<div id="(?:itemscout|its-image|__next)[^"]*"[^>]*>.*', "", body, flags=re.S)

# Primary CTAs / app routes -> PWA (static landing has no /keywords etc.)
body = body.replace('href="/login"', 'href="#" data-go-pwa')
for app_path in ("/keywords", "/products", "/margin", "/my"):
    body = body.replace(f'href="{app_path}"', 'href="#" data-go-pwa')
body = re.sub(
    r'(<a[^>]*from-brand-500[^>]*)(href="[^"]*")',
    r'\1href="#" data-go-pwa',
    body,
)

head = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content="네이버 트렌드와 쿠팡 실매출을 크로스 검증하는 실전형 소싱 엔진 BlueOcean" />
  <meta name="theme-color" content="#2563eb" />
  <title>BlueOcean — 실전형 크로스 소싱</title>
  <link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin />
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" />
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {{
      theme: {{
        extend: {{
          colors: {{
            brand: {{
              50: "#eff6ff",
              100: "#dbeafe",
              200: "#bfdbfe",
              300: "#93c5fd",
              400: "#60a5fa",
              500: "#3b82f6",
              600: "#2563eb",
              700: "#1d4ed8",
              800: "#1e40af",
              900: "#1e3a8a",
            }},
          }},
          fontFamily: {{
            sans: ["Pretendard", "system-ui", "sans-serif"],
          }},
        }},
      }},
    }};
  </script>
  <link rel="stylesheet" href="css/hero.css" />
  <style>
    html {{ scroll-behavior: smooth; }}
    body {{ font-family: Pretendard, system-ui, sans-serif; }}
    [data-go-pwa] {{ cursor: pointer; }}
  </style>
</head>
<body class="min-h-screen bg-slate-50 antialiased">
"""

hero_html = HERO.read_text(encoding="utf-8") if HERO.is_file() else ""

tail = f"""
  <script>window.SOURCING_APP = {{ pwaUrl: "{PWA_URL}" }};</script>
  <script src="js/config.js"></script>
  <script src="js/main.js"></script>
</body>
</html>
"""

OUT.write_text(head + hero_html + body + tail, encoding="utf-8")
print("wrote", OUT, OUT.stat().st_size, "bytes")
