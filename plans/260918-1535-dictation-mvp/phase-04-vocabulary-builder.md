---
phase: 4
title: "Vocabulary builder"
status: pending
priority: P2
effort: "4-5d"
dependencies: [3]
---

# Phase 4: Vocabulary builder

## Overview
Click từ → tra nghĩa tiếng Việt theo ngữ cảnh (Haiku + cache) → lưu sổ tay → ôn FSRS server-side. Exit: tra, lưu, ôn 1 phiên hoàn chỉnh; cache hit xác nhận qua `llm_usage`.

## Requirements
- Functional: FR-M6-01..03.
- Non-functional: NFR-06 (không gửi PII sang LLM), NFR-11/12 (log chi phí), p95 lookup theo AC-M6-01.4.

## Architecture
- **Lookup**: `GET /lookup?word=&segment_id=` → chuẩn hoá từ (lowercase, bỏ dấu câu, giữ apostrophe) → tra `word_lookups` theo `(normalized_word, segment_id)` → miss thì gọi `llm_client` với prompt gồm từ + câu ngữ cảnh, output schema `{lemma, ipa, pos, meaning_vi, alt_meaning_vi?}`; lưu cache. Chỉ cho phép lookup khi user đã completed/revealed segment hoặc xong bài (AC-M6-01.1, kiểm tra server-side).
- **Rate limit**: bảng/ bộ đếm trong Postgres theo (user, phút) và (user, ngày, cache-miss) — không thêm Redis.
- **FSRS**: `services/srs.py` bọc thư viện `fsrs` (Scheduler, Card, Rating); `fsrs_state_json` lưu Card serialize; `due_at` cột riêng để index. `GET /reviews/due` trả kèm `intervals` cho 4 rating (tính bằng scheduler mô phỏng, không ghi). `POST /reviews/{id}` cập nhật card + `review_logs` + `daily_activity.reviews_done`.
- **Giới hạn**: ≤ 50 thẻ/phiên, thẻ mới ≤ 20/ngày theo múi giờ user.
- **Web**: popover từ (`features/vocabulary/word-popover.tsx`, states theo `docs/ui/component-map.md`), trang Sổ tay, trang Ôn tập (phím Space lật, 1–4 đánh giá), phát câu ngữ cảnh bằng lại `useSegmentPlayer` với 1 segment.

## Related Code Files
- Create (api): `app/models/{word_lookup,vocab_item,review_log}.py`, migration, `app/routers/{lookup,vocab,reviews}.py`, `app/services/{lookup,srs,rate_limit}.py`
- Create (web): `src/features/vocabulary/{word-popover.tsx,notebook-page.tsx,clickable-transcript.tsx}`, `src/features/review/review-session.tsx`
- Modify (web): `features/dictation/diff-view.tsx` (từ click được khi segment xong), `features/dictation/summary.tsx` (danh sách từ đã lưu trong bài)
- Tests: `api/tests/{test_lookup_cache,test_lookup_gate,test_rate_limit,test_srs_service,test_vocab_crud,test_reviews}.py`, web test cho review keyboard

## Implementation Steps
1. Models + migration (unique `(user_id, lemma)`, index `(user_id, due_at)`).
2. Lookup service + gate + cache + rate limit; test cache hit không gọi LLM (đếm qua fake `llm_client`).
3. Vocab CRUD (trùng lemma → trả item cũ + cờ `already_exists`), sửa nghĩa/ghi chú ≤ 500 ký tự.
4. SRS service + endpoints due/review; test chuỗi rating chuyển trạng thái và `due_at` tăng dần.
5. Web popover, sổ tay (lọc/tìm/sắp xếp), trang ôn tập, badge "đã có trong sổ".
6. Đo p95 lookup (hit/miss) bằng log `llm_usage` + request timing trên 50 lookup thật.

## Success Criteria
- [ ] Mọi AC M6 có test.
- [ ] Segment chưa xong → UI không click được và API trả 403.
- [ ] Lần tra thứ 2 cùng (từ, câu) có `cache_hit=true` trong `llm_usage`.
- [ ] Phiên ôn hoàn chỉnh chỉ bằng bàn phím; khoảng cách hiển thị khớp lịch thực tế sau khi đánh giá.

## Risk Assessment
- LLM trả lemma sai (ví dụ "went" → "went") → vẫn lưu, user sửa được; unique theo lemma có thể gộp nhầm từ đồng hình khác nghĩa — chấp nhận ở MVP.
- API version thư viện `fsrs` thay đổi → pin version, bọc toàn bộ trong `srs.py`.
