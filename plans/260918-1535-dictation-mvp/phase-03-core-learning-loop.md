---
phase: 3
title: "Core learning loop"
status: pending
priority: P1
effort: "6-8d"
dependencies: [2]
---

# Phase 3: Core learning loop

## Overview
Thư viện bài, Smart Audio Player và Dictation Workspace với diff real-time + lưu tiến độ. Exit: learner làm hết 1 bài chỉ bằng bàn phím.

## Requirements
- Functional: FR-M3-01..02, FR-M4-01..04, FR-M5-01..05.
- Non-functional: NFR-01 (bundle ≤ 250 KB gzip route workspace), NFR-03 (±100 ms), NFR-07 (keyboard, aria-live, không chỉ màu).

## Architecture
- **Code khởi đầu từ UI handoff** (đã có trong repo): `diff/*` + 18 test, `diff-view.tsx`, `segment-input.tsx`, `shortcuts.ts`, `player/{use-segment-player.ts,player-bar.tsx}`. Phase này sửa cho khớp SRS v1.2 thay vì viết mới — xem bước 1–4. <!-- Updated: UI handoff -->
- **Diff engine** thuần TS, không phụ thuộc React: `web/src/features/dictation/diff/{normalize,tokenize,diff-words,score}.ts`. `diffWords(expected, typed, {strict}) → Token[]` với `status: correct|wrong|extra|missing|pending|revealed`; bỏ ô `missing` cuối câu (từ chưa gõ tới). Thuật toán: LCS trên token đã chuẩn hoá (≤ 60 từ → O(n·m) đủ nhanh), rồi ghép cặp các đoạn không khớp thành `wrong` (thay thế) / `extra` / `missing`.
- **Player**: hook `useSegmentPlayer(audioUrl, segments)` bọc 1 `<audio>`; vòng `requestAnimationFrame` khi đang phát để kiểm tra `currentTime >= end` (auto-pause) hoặc `>= B` (loop A-B); state machine: `idle | playing-segment | playing-free | looping`.
- **Keyboard**: 1 handler cấp workspace (capture phase) cho `Ctrl+Enter`, `Ctrl+'`, `Ctrl+.`, `Ctrl+,`, `Ctrl+/`; Enter trong ô nhập = sang câu khi 100%.
- **API**: `GET /lessons` (lọc, tìm không dấu bằng `unaccent` + `ILIKE`), `GET /lessons/{slug}`, `GET /lessons/{slug}/segments` (theo quy tắc §5 SRS), `PUT /segments/{id}/attempt` (draft, best_score, completed, revealed, hints_used, strict), `PUT /lessons/{id}/progress`. Server ghi `daily_activity.segments_completed` khi attempt chuyển sang completed lần đầu (dùng ở phase 5).
- **Offline**: TanStack Query mutation queue với debounce 1 s; trạng thái "Chưa lưu" khi mutation lỗi mạng, retry khi `online`.

## Related Code Files
- Create (api): `app/models/{lesson_progress,segment_attempt,daily_activity}.py`, migration, `app/routers/{lessons,progress}.py`, `app/services/{progress,activity}.py`
- Modify (web, từ handoff): `src/features/dictation/diff/{normalize,tokenize,diff-words,score}.ts`, `diff-words.test.ts`, `src/features/dictation/{segment-input,diff-view}.tsx`, `src/features/player/{use-segment-player.ts,player-bar.tsx}`, `docs/ui/interaction-notes.md` (nếu hành vi đổi)
- Create (web): `src/features/library/{library-page,lesson-card,filter-chips,empty-state,lesson-detail}.tsx`, `src/features/dictation/{workspace,summary}.tsx`, `src/features/settings/*` (tốc độ, strict mặc định) — layout theo `docs/ui/component-map.md`
- Tests: `web/src/features/dictation/diff/*.test.ts` (≥ 30 case bảng, AC-M5-02.5), `use-segment-player.test.ts` (fake timers + mock HTMLMediaElement), `api/tests/{test_lessons,test_progress}.py`

## Implementation Steps
1. Chạy 18 test handoff, rồi sửa diff engine cho khớp SRS (test trước):
   - `score.ts`: điểm = `correct / (expected + extra)` (AC-M5-03.1); câu revealed giữ điểm trước khi reveal (AC-M5-04.2) — bỏ `percent: null`, thêm cờ `revealed`.
   - `normalize.ts`: luôn NFC, luôn đổi nháy cong → thẳng, luôn case-insensitive; strict chỉ thêm việc so dấu câu (SRS §M5 quy tắc 1–4).
   - `tokenize.ts`: tách gạch nối `-`/`–`/`—` thành khoảng trắng; tách dấu câu dính đầu/cuối thành token riêng khi strict.
   - Bổ sung test lên ≥ 30 case (AC-M5-02.5): nháy cong, gạch nối, contraction, từ lặp, đảo từ, chỉ dấu câu, thiếu từ đầu/cuối, strict + hoa/thường; giữ benchmark 60 từ < 5 ms.
2. API library + filter + phân trang + URL query sync phía web.
3. Trang chi tiết bài (attribution, Bắt đầu/Tiếp tục/Làm lại; ẩn transcript tới khi xong).
4. Player hook (sửa code handoff): thêm listener `error`/`loadedmetadata` của `<audio>` (hiện lỗi tải thật, set `durationMs`); A-B validate B > A + 500 ms và báo lỗi inline thay vì tự đổi chỗ (AC-M4-03.1); chuyển segment huỷ A-B (AC-M4-03.4). Giữ: segment play, auto-pause rAF, tốc độ (`preservesPitch`), A-B loop + "Lặp câu này", seek → đổi segment hiện tại, lỗi tải audio + retry.
5. Workspace: ô nhập per segment (tắt spellcheck/autocorrect), diff view với trạng thái có kiểu gạch + icon, điểm live `aria-live`, gợi ý, hiện đáp án, xem bản dịch.
6. Lưu tiến độ: draft debounce, best score, reveal; khôi phục khi reload; hàng đợi offline.
7. Màn tổng kết bài (AC-M5-05.3; phần "từ đã lưu" để trống tới phase 4).
8. Checklist manual đo độ lệch pause (log `currentTime` lúc pause vs `end_ms`) trên Chrome, Safari macOS, Safari iOS ở 0.75/1/1.25x.

## Success Criteria
- [ ] ≥ 30 test diff pass; token đang gõ dở hiện `pending`, không lộ đáp án (kể cả số từ còn lại).
- [ ] Điểm & chuẩn hoá khớp SRS v1.2 (AC-M5-03.1, AC-M5-04.2, quy tắc chuẩn hoá); `docs/ui/interaction-notes.md` không còn mâu thuẫn với code.
- [ ] Độ lệch pause/loop ≤ 100 ms trên 3 trình duyệt × 3 tốc độ (ghi kết quả vào PR).
- [ ] Reload giữa bài → quay về đúng câu + nội dung nháp.
- [ ] Tắt mạng khi đang gõ → vẫn chấm, hiện "Chưa lưu", bật mạng tự đồng bộ.
- [ ] Hoàn thành 1 bài chỉ bằng bàn phím.

## Risk Assessment
- Safari iOS: `play()` cần user gesture, rAF bị throttle khi tab ẩn → chỉ auto-pause khi tab hiển thị; khi `visibilitychange` hidden thì pause.
- Seek chính xác phụ thuộc HTTP Range + mp3 VBR → khuyến nghị ingest chuyển audio sang AAC/m4a CBR (thêm bước `ffmpeg` trong phase 2 nếu đo thấy lệch).
- Phím tắt xung đột IME tiếng Việt (Unikey/Telex) → kiểm tra với `isComposing` và bỏ qua khi đang composition.
