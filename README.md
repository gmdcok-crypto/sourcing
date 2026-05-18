# sourcing

FastAPI-based sourcing backend for Naver keyword search, Railway deployment,
Cloudflare R2 storage, and Bright Data support for later Coupang sales-data crawling.

## Features

- `GET /health`: deployment and integration status check
- `GET /admin`: dark-mode admin console concept screen
- `GET /api/keywords/search`: query Naver Shopping API by keyword
- Optional raw-response archiving to Cloudflare R2
- Bright Data configuration scaffold for later-stage Coupang crawling workflows

## Local Run

1. Create a virtual environment and install dependencies.
2. Set environment variables.
3. Start the server with `uvicorn app.main:app --reload`.

## Environment Variables

- `NAVER_CLIENT_ID`
- `NAVER_CLIENT_SECRET`
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET_NAME`
- `R2_PUBLIC_BASE_URL`
- `BRIGHT_DATA_API_KEY`
- `BRIGHT_DATA_ZONE`

## Railway

This repo includes a `Procfile` for Railway deployment.
