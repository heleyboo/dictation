---
phase: 1
title: "Scaffold"
status: pending
priority: P1
effort: "2-3d"
dependencies: []
---

# Phase 1: Scaffold

## Overview
Dựng monorepo chạy được end-to-end rỗng: web gọi api `/healthz`, api nói chuyện Postgres, worker poll job queue, CI xanh, TS client sinh từ OpenAPI.

## Requirements
- SRS §1.5 (stack), NFR-14 (lint/type/test), DoD §7.
- `docker compose up` khởi động web · api · worker · postgres (+ minio ở dev thay R2).

## Architecture
- `api` và `worker` cùng package `api/app`; khác entrypoint (`uvicorn app.main:app` vs `python -m app.worker`).
- Dockerfile multi-target: `api` (slim) và `worker` (thêm dependency group `alignment`: stable-ts/torch CPU) để image API không kéo torch.
- Job queue: bảng `jobs`; worker loop `SELECT … FOR UPDATE SKIP LOCKED LIMIT 1` mỗi 2 s; handler registry theo `type`.
- Web gọi API cùng origin qua Caddy (`/api/*` → api) → không cần CORS ở prod; dev dùng Vite proxy.
- TS client: `openapi-typescript` sinh `web/src/lib/api/schema.d.ts` từ `/openapi.json`; wrapper `openapi-fetch`.

## Related Code Files
- Create: `api/pyproject.toml`, `api/app/{main,config,db,cli}.py`, `api/app/models/base.py`, `api/app/models/job.py`, `api/app/worker/{__main__,queue,registry}.py`, `api/alembic/*`, `api/tests/test_healthz.py`, `api/tests/test_job_queue.py`, `api/Dockerfile`
- Create: `web/package.json`, `web/vite.config.ts`, `web/tsconfig.json`, `web/src/main.tsx`, `web/src/routes/*`, `web/src/lib/api/{client.ts,schema.d.ts}`, `web/eslint.config.js`, `web/Dockerfile`
- Create: `docker-compose.yml`, `Caddyfile`, `.env.example`, `.github/workflows/ci.yml`, `README.md`
- Modify: `.gitignore` (thêm `.venv`, `__pycache__`, `web/dist`, `.env`)

## Implementation Steps
1. `api/`: uv project Python 3.12; deps fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, pydantic-settings; dev: pytest, pytest-asyncio, httpx, ruff, mypy. Group `alignment`: stable-ts (torch CPU wheel).
2. `config.py` (pydantic-settings, đọc env); `db.py` async engine/session; `GET /healthz` kiểm tra DB.
3. Alembic init + migration đầu: bảng `jobs` (SRS §4).
4. Worker: `enqueue(type, payload, run_after)`, `claim_next()`, retry với backoff (`attempts`, `last_error`), heartbeat log; test claim đồng thời 2 worker không lấy trùng job.
5. `web/`: Vite React TS strict, React Router, TanStack Query, Tailwind + shadcn init, ESLint + Prettier, Vitest; trang placeholder gọi `/api/v1/healthz`.
6. Script `web: npm run gen:api` sinh schema từ api đang chạy (hoặc từ file `api/openapi.json` export bằng `python -m app.cli export-openapi` để CI không cần chạy server).
7. `docker-compose.yml` + `Caddyfile` (static web, reverse proxy `/api`, security headers cơ bản); `.env.example` liệt kê mọi biến (DB, R2, ANTHROPIC_API_KEY, GOOGLE_*, RESEND_*, SESSION_SECRET, APP_BASE_URL).
8. CI: ruff, mypy, pytest (service postgres), web lint/typecheck/vitest, kiểm tra `schema.d.ts` không lệch (`gen:api` rồi `git diff --exit-code`).
9. README: yêu cầu hệ thống, lệnh dev, lệnh test.

## Success Criteria
- [ ] `docker compose up` → mở web thấy "API OK" từ `/healthz`.
- [ ] Test job queue: 2 worker song song, 20 job, mỗi job chạy đúng 1 lần.
- [ ] CI xanh trên PR; lệch OpenAPI ↔ TS client làm CI đỏ.
- [ ] Không secret trong repo; `.env.example` đầy đủ.

## Risk Assessment
- Image worker nặng (torch ~ GB) → build riêng target, dùng torch CPU wheel; cache layer.
- Async SQLAlchemy + Alembic cấu hình dễ sai → migration chạy bằng sync URL riêng.
