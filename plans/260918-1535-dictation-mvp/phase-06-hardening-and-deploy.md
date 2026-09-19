---
phase: 6
title: "Hardening and deploy"
status: pending
priority: P1
effort: "4-5d"
dependencies: [5]
---

# Phase 6: Hardening and deploy

## Overview
Đo và đạt mọi NFR, e2e Playwright cho luồng chính, deploy VPS với backup, seed ≥ 30 bài thật. Exit: production chạy, mọi NFR có số đo.

## Requirements
- Non-functional: NFR-01..14 (toàn bộ).
- Content: ≥ 30 bài published, ≥ 10 bài mỗi level, đủ 4 topic, mỗi bài có license/nguồn.

## Architecture
- Prod compose: Caddy (TLS tự động, CSP, HSTS, gzip/brotli, cache static bất biến) · api (uvicorn workers=2) · worker (concurrency 1) · postgres (volume) · backup cron (`pg_dump` hằng ngày → R2, giữ 7 bản).
- Migration chạy như bước riêng trước khi api khởi động (`alembic upgrade head` trong entrypoint một lần).
- Log JSON có `request_id` (middleware), healthcheck compose cho api/worker.

## Related Code Files
- Create: `docker-compose.prod.yml`, `deploy/backup.sh`, `deploy/README.md` (hoặc `docs/deployment.md`), `web/e2e/*.spec.ts`, `web/playwright.config.ts`, `api/tests/perf/lookup_load.py` (k6 hoặc locust script)
- Modify: `Caddyfile` (CSP, HSTS), `.github/workflows/ci.yml` (thêm e2e), `docs/system-architecture.md` (tạo mới: kiến trúc thực tế)

## Implementation Steps
1. E2E Playwright (compose dev + fake Google + fake LLM): login Google (fake) → thư viện lọc → làm 1 bài bằng bàn phím → tra & lưu từ → ôn → dashboard streak = 1.
2. Accessibility: axe-core trong e2e cho library, workspace, review; sửa vi phạm; kiểm tra tương phản.
3. Performance: Lighthouse CI (mobile) cho library + workspace; kiểm tra bundle size; load test API không-LLM 50 req/s p95 ≤ 300 ms.
4. Security pass: `/ck:security-scan` + rà checklist NFR-04/05 (CSP, CORS, CSRF, headers, upload); dependency audit (`pip-audit`, `npm audit`).
   - Trước khi bật `MAGIC_LINK_ENABLED` ở production: rate limit theo IP (và IP+email) cho `POST /auth/magic-link` — hiện chỉ theo email nên một IP có thể gửi tới nhiều địa chỉ. <!-- Updated: phase 2 review -->
   - Đo thời gian align bài 15 phút; nếu dài, tách tải S3 + align ra ngoài transaction DB của handler. <!-- Updated: phase 2 review -->
5. Deploy VPS: DNS, compose prod (`EMAIL_REMINDERS_ENABLED=false`, `MAGIC_LINK_ENABLED=false` tới khi domain gửi mail có SPF/DKIM), secrets qua `.env` trên server (không commit), backup + thử restore 1 lần.
6. Seed nội dung: ingest ≥ 30 bài VOA qua admin, review, publish.
7. Viết `docs/system-architecture.md` + cập nhật README (deploy, backup/restore).

## Success Criteria
- [ ] E2E luồng chính xanh trong CI.
- [ ] Lighthouse: LCP ≤ 2.5 s; bundle workspace ≤ 250 KB gzip; API p95 ≤ 300 ms @ 50 req/s.
- [ ] Không còn vi phạm axe mức serious/critical.
- [ ] Restore backup thành công trên môi trường thử.
- [ ] ≥ 30 bài published đạt tiêu chí nội dung.

## Risk Assessment
- Ingest 30 bài trên CPU mất vài giờ → chạy nền qua đêm; theo dõi RAM.
- Lighthouse trên CI dao động → dùng median 3 lần chạy.
