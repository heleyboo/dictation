# Component map — các màn còn lại

Mỗi mục: đường dẫn đích trong repo → component, props chính, state phải phủ. Bản vẽ tham chiếu ở
`Dictation.dc.html` (số mục trong ngoặc). Dùng shadcn: Button, Card, Popover, Dialog, Tabs, Toggle(-Group),
Slider, Badge, Input, Select, Switch, Table, Tooltip.

## Workspace (02, 03) — `web/src/features/dictation/workspace.tsx`
Layout desktop: player dính trên, cột chính = danh sách câu, cột phải `w-[312px]` (điểm câu, tiến độ bài,
ghi chú, chỉ báo lưu). < 768px: cột phải gập thành thanh đáy 3 nút (Gợi ý / Đáp án / Bản dịch), điểm chuyển
vào thẻ câu hiện tại, chip player cuộn ngang, hit target ≥ 44px.

- `SentenceList` — `segments`, `currentIndex`, `attempts`: câu xong hiện read-only + `✓ %` + "Sửa lại" và mỗi
  từ là `<button>` mở popover tra từ; câu chưa tới chỉ hiện "Chưa mở — N từ" (không hiện chữ).
- `SegmentInput` (đã có code) cho câu hiện tại.
- States phải phủ: đang gõ diff hỗn hợp · 100% · đã hiện đáp án · bản dịch mở · A-B đang lặp · lỗi audio +
  "Thử lại" · "Chưa lưu" ngoại tuyến · mobile 360.

## Popover tra từ (04) — `web/src/features/vocabulary/word-popover.tsx`
`word`, `segmentId`, `lessonId`; query `GET /lookup?word=&segment_id=`.
- loading: skeleton 3 dòng, giữ tiêu đề từ + IPA nếu có cache (≤ 3s).
- loaded: từ · lemma · IPA US · từ loại · nghĩa theo ngữ cảnh · 1 nghĩa khác · câu gốc có highlight + ▶ phát
  lại câu · "Lưu từ".
- saved: banner `ok` "Đã có trong sổ — đến hạn dd/MM" + "Mở trong sổ tay" (nút Lưu biến mất).
- error / rate-limited: banner `bad` + "Thử lại" + "Lưu từ (chưa có nghĩa)".

## Thư viện (05) — `web/src/features/library/`
`library-page.tsx` (URL query sync: `topic[]`, `level[]`, `q`, `page`), `lesson-card.tsx`, `filter-chips.tsx`,
`empty-state.tsx`. Card: chủ đề + trình độ (Badge), tiêu đề (serif 19), nguồn, `mm:ss` + số câu (mono),
thanh tiến độ + "Tiến độ N% · Điểm tốt nhất N%", CTA đổi theo tiến độ. Empty: nêu bộ lọc đang áp + "Xoá bộ lọc".

## Chi tiết bài (05) — `web/src/features/library/lesson-detail.tsx`
2 cột: nội dung + cột phải 340px (tiến độ, CTA chính, Làm lại, chip từ đã lưu — ♡ ngoài phạm vi MVP). Bắt buộc khối
"Nguồn & giấy phép" (`Source: … — Public domain`). Transcript ẩn tới khi xong: card gạch đứt + "Mở khoá ở câu N/N".

## Tổng kết (06) — `web/src/features/dictation/summary.tsx`
Điểm lớn (56px serif) + 4 ô: câu đã hiện, lần gợi ý, thời gian, từ mới đã lưu. Biểu đồ cột điểm từng câu
(ok ≥ 90 · accent 50–89 · warn = đã hiện) + chú giải. 4 CTA: bản ghi kèm bản dịch · làm lại · bài tiếp cùng
trình độ · ôn từ vừa lưu.

## Dashboard (07) — `web/src/features/dashboard/dashboard-page.tsx`
Card "Tiếp tục học" nổi (viền accent + ring), card "Từ đến hạn" (số lớn + "Ôn tập ngay"), card chuỗi ngày
(hiện tại + dài nhất, 7 ô ngày), bảng 5 bài gần đây (tiêu đề · chủ đề/level · N/N · điểm tốt nhất · lần cuối).

## Sổ tay (07) — `web/src/features/vocabulary/notebook-page.tsx`
Tabs `Tất cả / Đến hạn / Mới` + tìm + sort Select. Hàng: từ + IPA/từ loại · nghĩa · trạng thái hạn (dot +
"Đến hạn"/"Mới"/ngày) · link bài nguồn "· câu N" · Sửa / Xoá. Sửa = inline (nghĩa + ghi chú riêng, Lưu/Huỷ).
Xoá = Dialog xác nhận nêu rõ mất tiến độ ôn.

## Ôn tập (07) — `web/src/features/review/review-session.tsx`
Mặt trước: từ (40px serif) + IPA + ▶ câu ví dụ + "Hiện nghĩa (Space)". Mặt sau: nghĩa · từ loại · câu ví dụ
highlight · ghi chú · 4 nút `Lại/Khó/Tốt/Dễ` (phím 1–4) mỗi nút in khoảng cách kế tiếp từ FSRS ("10 phút",
"3 ngày"). Xong: "Hết từ đến hạn" + số từ đến hạn mai ("Ôn thêm" thẻ chưa đến hạn: ngoài phạm vi MVP).

## Lịch sử (08) — `web/src/features/history/history-page.tsx`
Table: bài · trạng thái (Badge: Đang học / Đã xong / Mới mở) · tiến độ (bar + %) · điểm tốt nhất · lần cuối.

## Đăng nhập (08) — `web/src/features/auth/`
`sign-in-card.tsx`: "Đăng nhập với Google" (nút chính) + phân cách "hoặc" + Input email + "Gửi liên kết"
(chỉ render khi `MAGIC_LINK_ENABLED`). `check-email.tsx`: icon ✉, "Kiểm tra email của bạn", email in đậm,
"Gửi lại sau 0:42" (countdown) + "Đổi email".

## Cài đặt (08) — `web/src/features/settings/settings-page.tsx`
Nhóm: Tài khoản (tên, múi giờ Select) · Mặc định khi học (tốc độ ToggleGroup, bắt lỗi dấu câu, tự dừng) ·
Nhắc học qua email (Switch + giờ) · Vùng nguy hiểm (viền `bad`, gõ đúng email mới bật nút xoá).

## Admin (09) — `web/src/features/admin/` (desktop-only, dày đặc)
- `lesson-table.tsx`: chip trạng thái `draft · processing · review · published · failed · unpublished`; hàng
  processing hiện % và tự làm mới 5s (`refetchInterval`); hàng failed nền `bad-soft` + log lỗi mono + "Chạy lại".
- `lesson-create-form.tsx`: tiêu đề, chủ đề, trình độ, tên nguồn, URL nguồn, **giấy phép bắt buộc** (viền `bad`
  + thông báo khi trống), upload audio (mp3/m4a/wav ≤ 30 MB ≤ 15 phút, hiện tên/size/thời lượng/bitrate),
  transcript textarea (bắt buộc; trống → lỗi validation, AC-M2-01.3 — ASR tự tách ngoài phạm vi MVP).
- `segment-review-table.tsx`: cột `# · ▶ · English · Bản dịch · start · end · action`; hàng "cần xem" nền
  `warn-soft` + lý do; inline edit text/dịch/timing (kiểm tra chồng lấn dòng kề); Gộp/Tách **disabled +
  Tooltip "Phải bỏ đăng bài trước"** khi `published`; Publish / Unpublish.
