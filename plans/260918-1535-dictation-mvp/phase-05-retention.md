---
phase: 5
title: "Retention"
status: pending
priority: P2
effort: "3-4d"
dependencies: [3, 4]
---

# Phase 5: Retention

## Overview
Dashboard "tiếp tục học", lịch sử, streak theo múi giờ user, badge từ đến hạn, email nhắc hằng ngày có unsubscribe 1-click. Exit: email thật gửi qua provider, unsubscribe hoạt động; tính năng nhắc sau cờ `EMAIL_REMINDERS_ENABLED` (mặc định tắt, không chặn launch).

## Requirements
- Functional: FR-M7-01..04.
- Non-functional: NFR-10 (idempotent, retry có giới hạn), NFR-06.

## Architecture
- **Streak**: hàm thuần `compute_streak(active_dates: set[date], today: date) -> (current, longest)`; `today` tính từ `users.timezone`. `daily_activity` đã được ghi từ phase 3/4 (date theo múi giờ user tại thời điểm ghi).
- **Dashboard**: `GET /dashboard` gộp continue (lesson_progress `in_progress` mới nhất), `due_count`, streak, 5 bài gần nhất — 1 request cho trang chủ.
- **Badge**: header dùng query `dashboard` (hoặc `GET /reviews/due?count_only`) và invalidate sau mutation review/vocab.
- **Email scheduler**: worker tự enqueue job `schedule_reminders` mỗi 15 phút (job định kỳ trong queue, `run_after` = mốc 15 phút kế tiếp) → chọn user có `email_reminder` và `reminder_time` rơi vào khung hiện tại theo timezone → kiểm tra điều kiện AC-M7-04.2 → insert `email_log` (unique) trước khi gửi → gửi qua `mailer` → cập nhật status; lỗi retry ≤ 2.
- **Unsubscribe**: token ký HMAC (`itsdangerous`) chứa user_id + purpose; `GET /email/unsubscribe?token` + `POST` cho `List-Unsubscribe-Post: List-Unsubscribe=One-Click`.
- **Template email**: Jinja2 HTML + text, tiếng Việt.

## Related Code Files
- Create (api): `app/models/email_log.py`, migration, `app/routers/{dashboard,email}.py`, `app/services/{streak,dashboard,reminders,unsubscribe_token}.py`, `app/worker/handlers/schedule_reminders.py`, `app/templates/email/daily-reminder.{html,txt}.j2`
- Create (web): `src/features/dashboard/{dashboard-page.tsx,due-badge.tsx}`, `src/features/history/history-page.tsx`, `src/routes/unsubscribed.tsx` (layout theo `docs/ui/component-map.md`)
- Tests: `api/tests/{test_streak,test_dashboard,test_reminders,test_unsubscribe}.py`

## Implementation Steps
1. `compute_streak` + test bảng (bao gồm AC-M7-02.3: 23:59 vs 00:01 Asia/Saigon, đổi timezone, streak tính tới hôm qua khi hôm nay chưa học).
2. `GET /dashboard`, trang dashboard + lịch sử; badge header.
3. Reminder selector (hàm thuần nhận `now_utc` + danh sách user → user cần gửi) + test biên khung 15 phút và múi giờ.
4. Cờ `EMAIL_REMINDERS_ENABLED` (config + `.env.example`; tắt → job không gửi, UI ẩn tuỳ chọn). Job định kỳ, `email_log` idempotent, mailer thật (Resend), template.
5. Unsubscribe token + 2 endpoint + header `List-Unsubscribe`.
6. Gửi thử tới hộp thư thật (Gmail) kiểm tra không vào spam, link hoạt động.

## Success Criteria
- [ ] Mọi AC M7 có test; chạy job 2 lần cùng khung không gửi trùng.
- [ ] User đã học hôm nay không nhận email.
- [ ] Bấm unsubscribe (không đăng nhập) → `email_reminder=false` ngay.
- [ ] Email thật hiển thị đúng trên Gmail web + mobile.

## Risk Assessment
- Email vào spam → cần SPF/DKIM/DMARC trên domain gửi trước khi bật cờ (domain còn là open question; launch được với cờ tắt).
- Worker chết → job định kỳ không tự enqueue lại: khi worker khởi động, đảm bảo luôn có đúng 1 job `schedule_reminders` pending.
