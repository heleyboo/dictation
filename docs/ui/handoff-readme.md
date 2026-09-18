# Dictation — bàn giao UI → repo `heleyboo/dictation`

Gói này khớp với `plans/260918-1535-dictation-mvp` (phase 1 & 3) và `docs/srs-mvp.md`.
Nguồn thiết kế: `Dictation.dc.html` trong project Omelette (canvas đặc tả 9 mục, tiếng Việt).

## Có gì trong gói

| Đường dẫn trong gói | Copy vào repo | Trạng thái |
|---|---|---|
| `web/src/styles/tokens.css` | `web/src/styles/tokens.css` | code chạy được |
| `web/src/features/dictation/diff/*` | cùng đường dẫn | code + 18 test case (bổ sung lên ≥ 30 ở phase 3) |
| `web/src/features/dictation/{diff-view,segment-input}.tsx` | cùng đường dẫn | code chạy được |
| `web/src/features/dictation/shortcuts.ts` | cùng đường dẫn | code chạy được |
| `web/src/features/player/{use-segment-player.ts,player-bar.tsx}` | cùng đường dẫn | code chạy được |
| `component-map.md` | `docs/ui/component-map.md` | đặc tả cho các màn còn lại |
| `interaction-notes.md` | `docs/ui/interaction-notes.md` | player + diff + a11y |

Tất cả file TS/TSX viết cho React 19 + TS strict + Tailwind + shadcn/ui như `plans/.../phase-01-scaffold.md` §5, không import gì ngoài `react`, `clsx` và `@/components/ui/*`.

## Thứ tự làm

1. `tokens.css` → import trong `web/src/main.tsx` sau `tailwind.css`. Thêm mapping màu vào `tailwind.config.ts` (snippet ở đầu file tokens).
2. `diff/` + test (`vitest run web/src/features/dictation/diff`) — đây là phần dễ sai nhất, phase 3 bước 1.
3. `use-segment-player.ts` → `player-bar.tsx`.
4. `segment-input.tsx` + `diff-view.tsx` → lắp vào `workspace.tsx` (workspace layout: cột chính = danh sách câu, cột phải 312px = điểm/gợi ý/bản dịch/ghi chú, gập xuống thanh đáy ở < 768px).
5. Các màn còn lại theo `component-map.md`.

## Ràng buộc đã chốt trong thiết kế

- Không bao giờ lộ từ đúng trừ khi người học bấm **Gợi ý** / **Hiện đáp án** — kể cả số lượng từ còn lại (không hiện ô `___` cho những từ chưa gõ tới). Xem test `does not leak unreached words`.
- **Gợi ý** chỉ sửa đúng một từ tại vị trí lỗi đầu tiên (hoặc chèn vào ô thiếu), giữ nguyên phần còn lại người học đã gõ.
- Màu không phải tín hiệu duy nhất: mỗi trạng thái có kiểu gạch riêng + `title`/`aria-label` tiếng Việt (NFR-07).
- ~~Điểm câu = `correct / expected.length`; câu đã hiện đáp án → điểm `—`~~ → thay bởi SRS v1.2: `correct / (expected + extra)`, câu đã hiện đáp án giữ điểm trước khi hiện (AC-M5-03.1, AC-M5-04.2). Code trong `web/src` sửa ở phase 3.
