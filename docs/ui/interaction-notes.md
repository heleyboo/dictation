# Ghi chú tương tác — player, diff, a11y

## Auto-pause (tự dừng cuối câu, bật mặc định)
- Vòng `requestAnimationFrame` chỉ chạy khi đang phát; dừng ngay khi `currentTime*1000 >= segment.endMs`,
  đồng thời set `currentTime = endMs/1000` để lần "Phát lại câu" sau không lệch.
- Sau khi dừng, trả focus về ô nhập của câu hiện tại (workspace gọi `inputRef.focus()`).
- Tắt tự dừng → phát liên tục; khi `currentTime` vượt `endMs`, `currentIndex` nhảy sang câu chứa mốc đó và
  ô nhập active đổi theo (không xoá nháp câu cũ).
- `visibilitychange → hidden` thì pause: rAF bị throttle nên mốc dừng sẽ lệch > 100 ms (Safari iOS).
- Đo độ lệch: log `currentTime` lúc pause so với `end_ms` ở 0.75/1/1.25x trên Chrome, Safari macOS, Safari iOS
  (Success Criteria phase 3).

## A-B loop
- `A` và `B` ghim theo `currentTimeMs` lúc bấm; `B < A` thì tự đổi chỗ.
- Chỉ loop khi có cả A và B; tới B thì `currentTime = A`, giữ nguyên tốc độ và trạng thái tự dừng.
- Marker A/B vẽ theo `%` của tổng thời lượng, nằm trên cùng lớp với thanh segment; vùng lặp là overlay
  `pointer-events: none` để vẫn bấm được vào segment bên dưới.
- "Lặp câu này" = đặt A/B bằng `segment.startMs/endMs` của câu hiện tại; bấm lại thì tắt và giữ A/B cũ nếu
  người dùng đã tự đặt.
- Seek thủ công trong vùng lặp không tắt loop; seek ra ngoài thì loop vẫn giữ (lần tới B vẫn nhảy về A).

## Diff khi đang gõ
- Chấm lại ngay mỗi keystroke, không debounce (AC-M5-02.1 ≤ 50 ms); input controlled.
- Chuẩn hoá (SRS §M5): luôn NFC, nháy cong → thẳng, gạch nối tách từ, không phân biệt hoa/thường; `strict = true` chỉ thêm việc so dấu câu.
- Chỉ từ cuối cùng (khi input không kết thúc bằng khoảng trắng) là "đang gõ": khớp tiền tố → `pending`
  (xám trung tính), không khớp → `wrong`.
- **Không lộ đáp án:** bỏ toàn bộ ô `missing` ở cuối chuỗi — nếu không, số ô trống sẽ tiết lộ còn bao nhiêu từ.
  Ô `missing` chỉ xuất hiện khi người học đã gõ vượt qua vị trí đó.
- Điểm = `correct / (số từ câu gốc + số từ thừa)`, làm tròn (AC-M5-03.1); nhãn cột phải: "N đúng · N sai · N chưa gõ" (chưa gõ = từ chưa
  tới, không phải ô trống).
- Gợi ý: sửa đúng một từ ở vị trí lỗi đầu tiên (hoặc chèn vào ô trống đầu tiên), giữ nguyên phần còn lại;
  không thêm khoảng trắng cuối nếu người học đang gõ giữa từ. Tăng `hints_used`.
- Hiện đáp án: toàn bộ câu chuyển `revealed`, giữ điểm ngay trước khi hiện (nhãn "đã hiện đáp án", AC-M5-04.2), câu được đánh dấu `revealed = true` trong attempt và
  đếm vào màn tổng kết.
- `Enter` trong ô nhập chỉ sang câu sau khi đạt 100%; bỏ qua khi `isComposing` (IME Telex/VNI).

## Autosave & ngoại tuyến
- Mutation queue (TanStack Query) debounce 1 s cho `draft`; lỗi mạng → chỉ báo "Chưa lưu", retry khi `online`.
- Chỉ báo có 3 trạng thái: `saved` (xanh "Đã lưu"), `pending` ("Đang lưu…"), `offline` (vàng "Chưa lưu — sẽ
  đồng bộ lại" + số câu đang chờ).

## A11y (NFR-07)
- Mỗi token diff có `title` + `aria-label` tiếng Việt và một ký hiệu nhỏ (✓ ~ × _ ·) — màu không phải tín hiệu
  duy nhất; tương phản chữ/nền ≥ 4.5:1 ở cả hai theme.
- Khối diff là `aria-live="polite" aria-atomic="true"`, kèm `sr-only` đọc điểm hiện tại.
- Thanh segment là các `<button>` có `aria-label="Đến câu N"` và `aria-current` cho câu hiện tại.
- Toàn bộ luồng làm được bằng bàn phím; nút trên mobile ≥ 44px.
