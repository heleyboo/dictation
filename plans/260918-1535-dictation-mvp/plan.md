---
title: Dictation webapp MVP
description: >-
  Webapp luyện nghe chép chính tả EN cho người Việt: player thông minh, diff
  real-time, thư viện theo level, vocab + FSRS, retention
status: pending
priority: P2
branch: main
tags:
  - mvp
  - react
  - vite
  - fastapi
  - postgres
  - stable-ts
  - fsrs
blockedBy: []
blocks: []
created: '2026-09-18T09:54:25.893Z'
createdBy: 'ck:plan'
source: skill
---

# Dictation webapp MVP

## Overview
Build MVP theo `docs/srs-mvp.md` (nguồn sự thật cho FR/AC/NFR). Phase file chỉ tham chiếu ID (`FR-M5-02`, `AC-M4-01.1`), không chép lại AC. Quyết định & lý do: `plans/reports/brainstorm-260918-1535-dictation-mvp-srs-report.md`.

Stack khoá: React/Vite/TS + TanStack Query + Tailwind/shadcn · FastAPI + SQLAlchemy 2 + Alembic · worker Python (Postgres job queue) · stable-ts (alignment) · `claude-haiku-4-5` · `fsrs` (Python) · R2 · Resend · Docker Compose 1 VPS.

## Repo layout (mục tiêu)
```
api/                 Python package (uv); app/{main,config,db,cli}.py, app/models, app/routers, app/services, app/worker; alembic/; tests/
web/                 Vite app; src/{routes,features/<module>,components,lib/api(generated)}; tests (vitest) + e2e (playwright)
docker-compose.yml   web(caddy) · api · worker · postgres (+ minio chỉ ở dev thay R2)
Caddyfile · .env.example · .github/workflows/ci.yml
```

## Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | [Scaffold](./phase-01-scaffold.md) | Completed |
| 2 | [Auth and content ingestion](./phase-02-auth-and-content-ingestion.md) | Completed |
| 3 | [Core learning loop](./phase-03-core-learning-loop.md) | Pending |
| 4 | [Vocabulary builder](./phase-04-vocabulary-builder.md) | Pending |
| 5 | [Retention](./phase-05-retention.md) | Pending |
| 6 | [Hardening and deploy](./phase-06-hardening-and-deploy.md) | Pending |

Thứ tự tuần tự: 1 → 2 → 3 → 4 → 5 → 6. Phase 4 và 5 độc lập nhau (có thể song song sau phase 3) nhưng cùng chạm `daily_activity` và header badge → làm tuần tự cho an toàn.

## Acceptance (toàn plan)
- Mọi AC trong `docs/srs-mvp.md` §2 pass (test tự động hoặc checklist manual trong PR).
- Mọi NFR §3 đo và đạt (phase 6).
- DoD §7 áp dụng cho từng FR.

## Dependencies
- Không có plan khác trong repo.
- Ngoài: tài khoản Google OAuth, Anthropic API key, Cloudflare R2 bucket, Resend + domain có SPF/DKIM, VPS ≥ 4 vCPU / 8 GB RAM.

## Open questions
Tên sản phẩm/domain · Resend vs SMTP · cấu hình VPS cuối cùng · tương đương số–chữ (sau MVP).

## Validation Log

### Session 1 — 2026-09-18
Verification Results
- Tier: Full (6 phases) · greenfield → không có file/symbol hiện hữu để grep; kiểm tra claim thư viện ngoài.
- Claims checked: 10 · Verified: 9 (fsrs 6.3.2, stable-ts 2.19.1, pysbd, itsdangerous, filetype, openapi-typescript, openapi-fetch, whisperx tồn tại; stable-ts `model.align(audio, text)`) · Failed: 1 · Unverified: 0
- Failure: `whisperx.align()` nhận `transcript: Iterable[SingleSegment]` có start/end (whisperx/alignment.py:117), không nhận transcript thuần như phase 2 giả định → đưa vào phỏng vấn, đã giải quyết.

Questions & decisions (4)
1. Alignment: **stable-ts `model.align`** thay WhisperX (đảo quyết định brainstorm dựa trên bằng chứng API; user xác nhận).
2. Sửa bài published: **sửa text/dịch/thời gian tại chỗ**, merge/split vẫn cần unpublish (SRS AC-M2-04.3 v1.1; AC-M2-04.1 cho publish lại từ `unpublished`).
3. Dùng thử không login: **giữ bắt login** (SRS AC-M1-04.1 không đổi).
4. Email nhắc: **code đủ, bật bằng `EMAIL_REMINDERS_ENABLED`** (mặc định tắt, không chặn launch; SRS AC-M7-04.6).

Propagation: SRS v1.1 (§1.5, AC-M2-02.2, AC-M2-04.1, AC-M2-04.3, AC-M7-04.6, §8) · plan.md · phase-01 · phase-02 · phase-05 · phase-06 · brainstorm report (ghi chú cập nhật).

### Whole-Plan Consistency Sweep
- Files reread/grepped: plan.md, phase-01..06, docs/srs-mvp.md, brainstorm report
- Decision deltas checked: 4
- Reconciled stale references: 12 (mọi "WhisperX" trong plan/SRS; quy tắc sửa bài published; trạng thái publish lại; cờ email)
- Unresolved contradictions: 0 — mâu thuẫn magic link cần domain email đã giải quyết: user chọn đặt magic link sau cờ `MAGIC_LINK_ENABLED` (SRS AC-M1-02.4; phase-02, phase-06 cập nhật; e2e dùng Google fake).

### Session 2 — 2026-09-18 (UI handoff reconciliation)
Nguồn: gói handoff `Form configuration decisions.zip` (commit b042ee3) so với SRS v1.1. User duyệt đề xuất:
- Giữ SRS: điểm `correct / (expected + extra)`; revealed giữ điểm trước khi reveal; chuẩn hoá luôn case-insensitive + nháy cong + gạch nối; chấm không debounce; transcript bắt buộc (bỏ ASR tự tách).
- Theo handoff: không hiện ô trống cho từ chưa gõ tới (AC-M5-02.2/02.3); gợi ý sửa đúng 1 từ (AC-M5-04.1); `GET /lookup?word&segment_id`; thư mục `features/{vocabulary,review,dashboard,history}`.
- Ngoài phạm vi (SRS §1.4): ♡ yêu thích, "ôn thêm" thẻ chưa đến hạn, ASR tự tách.
- Nợ code handoff ghi vào phase 3: 18/≥30 test, listener `error`/`loadedmetadata`, `durationMs`, validate A-B.
Propagation: SRS v1.2 · phase-01 (dựng khung quanh code handoff) · phase-03 · phase-04 · phase-05 · docs/ui/{interaction-notes,component-map,handoff-readme}.md.

### Whole-Plan Consistency Sweep (session 2)
- Decision deltas checked: 9
- Files grepped: plan.md, phase-01..06, docs/srs-mvp.md, docs/ui/*.md
- Reconciled stale references: 14 (lookup method, thư mục vocab/retention, công thức điểm, revealed "—", debounce 120 ms, chuẩn hoá strict, ASR, ♡, ôn thêm, số test)
- Unresolved contradictions: 0
