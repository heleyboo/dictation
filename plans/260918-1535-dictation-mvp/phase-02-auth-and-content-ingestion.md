---
phase: 2
title: Auth and content ingestion
status: in-progress
priority: P1
effort: 5-7d
dependencies:
  - 1
---

# Phase 2: Auth and content ingestion

## Overview
Đăng nhập (Google + magic link), phân quyền admin, và pipeline admin: upload audio + transcript → stable-ts alignment → Haiku dịch → review/sửa → publish. Exit: 1 bài VOA thật published với timing đúng.

## Requirements
- Functional: FR-M1-01..05, FR-M2-01..04 (toàn bộ AC trong `docs/srs-mvp.md`).
- Non-functional: NFR-04 (cookie, CSRF), NFR-05 (upload an toàn), NFR-06, NFR-11 (log LLM usage).

## Architecture
- **Session**: bảng `sessions`; cookie `sid` httpOnly/Secure/SameSite=Lax; CSRF double-submit: `GET /me` trả `csrf_token`, client gửi header `X-CSRF-Token`; dependency FastAPI `require_csrf` cho method ghi.
- **Google OAuth**: authlib, state + PKCE; `return_to` chỉ cho phép path nội bộ (chống open redirect).
- **Magic link**: sau cờ `MAGIC_LINK_ENABLED` (mặc định tắt, AC-M1-02.4); token 32 byte ngẫu nhiên, lưu `sha256`; rate limit 5/giờ/email (đếm trong bảng `magic_links`).
- **Storage**: module `storage.py` (boto3 S3 API) → R2 prod / minio dev; key `audio/<uuid>.<ext>`; kiểm tra MIME bằng magic bytes (`filetype`), đo duration bằng `ffprobe` (mutagen fallback).
- **Pipeline job `ingest_lesson`**: tải audio tạm → tách câu (`pysbd`) → stable-ts `model.align(audio, full_transcript, language='en')` (không transcribe) → ghép word timings vào câu theo vị trí token → tính `start/end` theo AC-M2-02.2 → đánh cờ AC-M2-02.5 → job `translate_lesson` (Haiku, batch ~40 câu/lần, JSON schema `[{idx, vi}]`, có context cả bài) → `review`.
- **LLM client**: `services/llm_client.py` duy nhất (anthropic SDK, model từ env, mặc định `claude-haiku-4-5`), ghi `llm_usage` mỗi lần gọi.
- **Admin UI**: `web/src/features/admin/*` (lesson list + status poll 5 s, form upload, màn review segment có ▶ phát đoạn, sửa inline, merge/split).

## Related Code Files
- Create (api): `app/models/{user,session,magic_link,lesson,segment,llm_usage}.py`, migration, `app/routers/{auth,me,admin_lessons,admin_segments}.py`, `app/services/{auth,oauth_google,mailer,storage,llm_client,sentence_split,alignment,translation,segment_edit}.py`, `app/worker/handlers/{ingest_lesson,translate_lesson}.py`, `app/cli.py` (`make-admin`)
- Create (web): `src/features/auth/*`, `src/features/admin/*`, `src/lib/csrf.ts`, route guards
- Tests: `api/tests/{test_auth_*,test_admin_*,test_segment_timing,test_segment_edit,test_ingest_pipeline}.py`

## Implementation Steps
1. Models + migration: users, sessions, magic_links, lessons, segments, llm_usage (SRS §4).
2. Auth: Google OAuth flow, magic link (mailer gửi qua Resend; dev in link ra log), session middleware, `require_user`, `require_admin`, CSRF, logout, `GET/PATCH/DELETE /me` (xoá cascade).
3. CLI `make-admin`.
4. Upload endpoint multipart: validate (AC-M2-01.2–01.4), lưu R2, tạo lesson `processing`, enqueue job.
5. Hàm thuần `compute_segment_bounds(words, next_start)` + unit test biên (đầu bài, câu cuối, chồng lấn).
6. Handler alignment (stable-ts CPU, model Whisper `base.en` hoặc `small.en` — chọn theo đo tốc độ/độ chính xác trên 3 bài VOA), lưu `words_json`, cờ `needs_attention`; lỗi → `failed` + `error_message`, retry ≤ 2.
7. Handler dịch qua `llm_client` (structured JSON, validate Pydantic, retry 1 lần khi sai schema).
8. Admin segment edit: sửa text/dịch/thời gian (validate không chồng lấn), merge kề, split tại word index (thời gian lấy từ `words_json`); publish/unpublish theo AC-M2-04.*; bài published cho sửa text/dịch/thời gian tại chỗ, chặn merge/split (409) tới khi unpublish.
9. Web: trang login, callback, guard route; admin screens.
10. Chạy thật 1 bài VOA (≈ 3–5 phút) và ghi thời gian xử lý (AC-M2-02.6).

## Success Criteria
- [x] Mọi AC M1, M2 có test (API test dùng fake Google + fake LLM qua dependency override; alignment test dùng 1 clip ngắn fixture được đánh dấu `slow`).
- [x] Learner gọi `/api/v1/admin/*` → 403; request ghi thiếu CSRF → 403.
- [x] 1 bài VOA thật: published, nghe thử 10 segment ngẫu nhiên không cắt mất đầu/cuối từ.
- [x] Bài 5 phút xử lý ≤ 10 phút trên máy 4 vCPU.

## Risk Assessment
- stable-ts align lệch với audio có nhạc nền/intro → cờ `needs_attention` + admin chỉnh; nếu tỉ lệ lỗi cao, cân nhắc trim intro trước.
- RAM worker (model Whisper small ~2 GB) → worker concurrency = 1.
- Alignment có thể chạy lâu hơn `WORKER_LOCK_TIMEOUT` (900 s) → job bị worker khác reclaim và chạy song song (kết quả vẫn được bảo vệ bằng fencing `locked_at`, nhưng tốn CPU gấp đôi). Trước khi thêm handler alignment: đo thời gian bài 15 phút, đặt timeout > thời gian tối đa hoặc thêm heartbeat cập nhật `locked_at`. <!-- Updated: phase 1 review -->
- Fake LLM trong test chỉ ở ranh giới `llm_client` (dependency override), không mock logic nghiệp vụ.

## Implementation Notes (2026-09-19)
- Slices: A auth (3b7e0a6) · B admin API + storage (1ec6ce2) · C pipeline (cd518d5) · D web (e252503) · E real-run fixes (aadb9b3).
- Tests: api 82 (Postgres thật), web 20; ruff/mypy strict/eslint/tsc sạch.
- Chạy thật (VOA "Monarch Butterfly Count Nears 30-Year Low", 5:54, 589 từ, 39 câu):
  - Pipeline 41–47 s (align stable-ts `base.en` CPU ~7 s; dịch Haiku 1 lần ~24 s, 2.4k in / 2.5k out token). AC-M2-02.6 (≤ 10 phút) đạt.
  - Kiểm tra ranh giới tự động (cắt clip theo start/end → Whisper nhận dạng lại → so từ đầu/cuối): 35/39 khớp; 3 lệch do chính tả ASR (pesticide, 5th, earth justice), 1 câu (29) do vùng align lỗi — đã được cờ, admin sửa trên UI, publish.
  - Browser (agent-browser): guard → /login, magic link → /admin, danh sách, màn review, báo lỗi chồng lấn, lưu timing, phát câu tự dừng lệch 12 ms, publish → gộp/tách bị khoá.
- Lệch so với plan / SRS (v1.3): đệm cuối câu +500 ms (đo: +200 ms cắt từ cuối); ranh giới chỉ theo từ align được; cờ "kém tin cậy" khi ≥ 3 từ hoặc ≥ 20%; lưu câu xoá cờ; dấu nháy đóng dính câu trước; cookie Secure suy ra từ `APP_BASE_URL` https (bỏ `COOKIE_SECURE`); minio init dùng image `minio/minio` (Docker Hub không còn `minio/mc`); S3 endpoint nội bộ cố định trong compose.
- Lock timeout: bài 5–6 phút align ~7 s nên 900 s dư nhiều; chưa cần heartbeat (đo lại với bài 15 phút ở phase 6).
- Chất lượng dịch Haiku: lỗi thành ngữ/địa danh ("spend the winter" → "dành dụm", "Rocky Mountains" → "Núi Hung Ơ", "milkweed" → "khu khố") — cần quyết định của user (xem open question).
- Code review (2026-09-19) — đã sửa: giới hạn body ở Caddy (upload 31 MB, còn lại 1 MB; trước đó body được spool ra đĩa trước khi kiểm tra quyền); cookie session cấp lại khi gia hạn (đúng "30 ngày không hoạt động"); magic link 2 bước (`/login/confirm` xem trước → POST tiêu thụ) chống trình quét link email + hiện email chống login-CSRF; `safeReturnTo` phía web so origin (chặn `/\evil.com`); `llm_usage` ghi bằng session riêng (không mất khi rollback); CSRF so sánh hằng thời gian; lỗi mạng OAuth → `/login?error=google`; tạo user idempotent khi đăng nhập đồng thời + cắt tên 120 ký tự; xoá audio mồ côi khi commit lỗi.
- Hoãn sang phase 6 (ghi trong phase-06): rate limit magic link theo IP (magic link đang tắt khi launch); transaction DB mở trong lúc align (đo ~7 s; đo lại với bài 15 phút).
