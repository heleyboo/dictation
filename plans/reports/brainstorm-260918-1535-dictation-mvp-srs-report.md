# Brainstorm — Dictation Web App MVP SRS

- Date: 2026-09-18 · Modes: none (no --html/--wiki)
- Output: `docs/srs-mvp.md` (SRS đầy đủ FR/AC/NFR/data model/API/milestones)

## Bối cảnh repo
Greenfield: chỉ có ClaudeKit scaffolding + `.gitignore` mẫu Next.js; chưa có code/docs/plan. Không có ràng buộc kế thừa.

## Problem-first (tóm tắt)
- Vấn đề thật: người Việt học nghe thiếu vòng lặp luyện chủ động có phản hồi tức thì + không giữ được từ mới → bỏ cuộc.
- Giả định rủi ro nhất: nội dung. TED/CNN không dùng hợp pháp được (TED = CC BY-NC-ND) → đổi sang VOA Learning English (public domain) + admin upload nội dung có license.
- "Tính năng ẩn" thứ 5: pipeline ingest (alignment timestamp câu + dịch) — không có nó, auto-pause & bản dịch không tồn tại.
- Retention cần cơ chế quay lại (streak, nhắc ôn, email), 4 tính năng gốc chỉ phục vụ học.
- Evidence status: weak (ý tưởng founder, tham chiếu app tương tự như dailydictation). Validate bằng metric bên dưới.

## Quyết định đã chốt (user)
| Chủ đề | Chọn | Loại bỏ & lý do |
|---|---|---|
| Nội dung | VOA + admin upload, WhisperX alignment | YouTube embed (loop kém, bản quyền mờ); TTS (giọng máy); TED (license) |
| Tài khoản | Bắt buộc login để học (Google + magic link) | localStorage (không đo retention, mất dữ liệu) |
| Stack | React/Vite + FastAPI + Postgres + worker Python | NestJS+Py worker (2 ngôn ngữ backend, 3 service); STT API (chi phí/phút) |
| Tra từ | Claude Haiku 4.5 + cache (word, segment) | Từ điển mở (chất lượng không đều, không ngữ cảnh) |
| Dịch câu | LLM dịch lúc ingest, admin sửa — **cập nhật 2026-09-19: Sonnet 5** (so trên bài VOA thật, Haiku sai thành ngữ/tên loài) | Nhập tay (nghẽn ra bài) |
| Chấm điểm | Theo câu, diff từ, case-insensitive, strict punctuation toggle mặc định TẮT | Bắt buộc dấu câu (nản người mới); cả bài 1 ô (lệch auto-pause) |
| Retention | Streak, lịch sử/tiếp tục, badge due, email nhắc hằng ngày | Gamification/leaderboard (YAGNI) |
| Deploy | Docker Compose 1 VPS, R2 audio, responsive web | Managed multi-cloud |
| Monetize | Miễn phí | Freemium (thêm payment scope) |

Cập nhật sau plan validation: alignment đổi WhisperX → stable-ts (`whisperx.align` cần segment có timing sẵn); sửa bài published tại chỗ (chặn merge/split); email nhắc sau cờ env.

Tinh chỉnh khi viết SRS: FSRS chạy server-side bằng thư viện Python `fsrs` (thay vì `ts-fsrs` client) để server là nguồn sự thật cho due count/email.

## Rủi ro chính & giảm thiểu
| Rủi ro | Giảm thiểu |
|---|---|
| Alignment (stable-ts) CPU chậm / RAM | Job async; VPS ≥ 8 GB RAM; AC: 5 phút audio ≤ 10 phút xử lý |
| Pause lệch do `timeupdate` ~250 ms | Check biên bằng rAF; AC ±100 ms |
| Chi phí/latency LLM | Cache, rate limit, log `llm_usage`, Haiku |
| Lộ đáp án qua DevTools | Chấp nhận (app học); UI không hiện text trước khi xong |
| Email vào spam | Domain riêng SPF/DKIM, List-Unsubscribe |
| Ít nội dung lúc launch | Exit milestone 5: ≥ 30 bài |

## Success metrics (đo sau launch)
- Activation: ≥ 60% user mới hoàn thành ≥ 1 bài trong phiên đầu.
- D7 retention ≥ 20%, D30 ≥ 10%.
- ≥ 40% user active lưu ≥ 5 từ/tuần; ≥ 50% thẻ due được ôn trong 48 h.
- Chi phí LLM ≤ 1 USD/1000 lookup.

## Next steps
1. `/ck:plan docs/srs-mvp.md` theo 6 milestone trong SRS §6.
2. Trước milestone 1: chốt email provider + domain, VPS size.

## Câu hỏi còn mở
Tên sản phẩm/domain · Resend vs SMTP · cấu hình VPS · tương đương số–chữ ở phase sau.
