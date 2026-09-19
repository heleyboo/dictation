# SRS — Dictation Web App (MVP)

- Phiên bản: 1.3 · Ngày: 2026-09-19 · Trạng thái: Approved (brainstorm + plan validation + UI handoff)
- UI handoff: `docs/ui/` (component map, interaction notes) + code khởi đầu trong `web/src/`; khi lệch, SRS là nguồn sự thật.
- Nguồn quyết định: `plans/reports/brainstorm-260918-1535-dictation-mvp-srs-report.md`
- Quy ước ID: `FR-<module>-<nn>` (yêu cầu), `AC-<module>-<nn>.<k>` (tiêu chí chấp nhận), `NFR-<nn>`. AC viết dạng Given/When/Then; mọi AC phải kiểm chứng được bằng test tự động hoặc bước manual ghi rõ.
- Từ khoá: **PHẢI** = bắt buộc MVP; **NÊN** = làm nếu không tăng scope; **KHÔNG** = cấm.

---

## 1. Tổng quan

### 1.1 Mục tiêu sản phẩm
Webapp luyện nghe tiếng Anh bằng chép chính tả (dictation) cho người Việt: nghe từng câu → gõ lại → được chấm real-time → lưu từ mới → ôn tập ngắt quãng. Mục tiêu MVP: chứng minh vòng lặp học + quay lại (retention), miễn phí hoàn toàn.

### 1.2 Persona
| Persona | Mô tả | Nhu cầu chính |
|---|---|---|
| Learner | Người Việt, trình độ A2–C1, học trên laptop (chính) và điện thoại (phụ) | Bài theo level/chủ đề, tự dừng từng câu, biết sai ở đâu, tra từ nhanh, ôn từ |
| Admin | Người vận hành nội dung (1–3 người) | Upload audio + transcript, tự động cắt câu + dịch, sửa rồi publish nhanh |

### 1.3 Phạm vi MVP (module)
| ID | Module |
|---|---|
| M1 | Auth & tài khoản |
| M2 | Content ingestion (admin) |
| M3 | Thư viện bài học |
| M4 | Smart Audio Player |
| M5 | Dictation Workspace |
| M6 | Vocabulary Builder (tra từ + sổ tay + ôn FSRS) |
| M7 | Retention (tiến độ, streak, nhắc ôn, email) |

### 1.4 Ngoài phạm vi (KHÔNG làm trong MVP)
Payment/gói trả phí · app mobile native · nhúng TED/YouTube hoặc nội dung không rõ license · leaderboard/huy hiệu/điểm XP · push notification · learner tự upload bài · chấm phát âm/speaking · tự nhận dạng transcript (ASR) khi admin không nhập transcript · yêu thích/♡ bài học · "ôn thêm" thẻ chưa đến hạn · UI đa ngôn ngữ (chỉ tiếng Việt) · scraper tự động VOA · tương đương số–chữ ("5" ≡ "five") và tương đương contraction ("don't" ≡ "do not") · chỉnh waveform trực quan trong admin · social/share.

### 1.5 Ràng buộc kỹ thuật (non-negotiable)
| Hạng mục | Lựa chọn |
|---|---|
| Frontend | React 18+ · Vite · TypeScript strict · TanStack Query · React Router · Tailwind + shadcn/ui |
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 |
| Worker | Cùng Python package với API; job queue bằng bảng Postgres (`SELECT … FOR UPDATE SKIP LOCKED`), không Redis |
| DB | PostgreSQL 16 |
| Alignment | stable-ts `model.align(audio, text)` (forced alignment transcript thuần → word timing), chạy CPU |
| LLM | Anthropic `claude-haiku-4-5` (tra từ + dịch câu), gọi qua 1 module `llm_client` duy nhất |
| SRS algorithm | Thư viện Python `fsrs` (open-spaced-repetition), tính lịch ở server |
| Storage | Cloudflare R2 (S3-compatible) cho audio; phục vụ qua HTTPS có hỗ trợ HTTP Range |
| Email | Resend (hoặc SMTP) qua 1 module `mailer` |
| Deploy | Docker Compose trên 1 VPS: `web` (static qua Caddy) · `api` · `worker` · `postgres` |
| API contract | REST `/api/v1`, OpenAPI; TS client sinh tự động từ OpenAPI (không viết tay type) |
| Repo layout | Monorepo: `web/`, `api/` (gồm worker), `docker-compose.yml`, `docs/` |

---

## 2. Yêu cầu chức năng

### M1 — Auth & tài khoản

**FR-M1-01 Đăng nhập Google OAuth.**
- AC-M1-01.1 Given khách chưa đăng nhập, When bấm "Đăng nhập với Google" và đồng ý, Then được tạo/khớp user theo email, set cookie session `httpOnly; Secure; SameSite=Lax`, chuyển về trang trước đó.
- AC-M1-01.2 Given Google trả lỗi/huỷ, When quay về callback, Then hiển thị thông báo lỗi tiếng Việt, không tạo user.

**FR-M1-02 Đăng nhập magic link email.**
- AC-M1-02.1 Given email hợp lệ, When gửi yêu cầu, Then gửi email chứa link 1 lần, hết hạn sau 15 phút; UI luôn trả cùng thông điệp "Kiểm tra email" (không lộ email có tồn tại hay không).
- AC-M1-02.2 Given link đã dùng hoặc quá hạn, When mở, Then báo "Link hết hạn" và cho gửi lại.
- AC-M1-02.3 Given 1 email, When yêu cầu > 5 lần/giờ, Then trả 429.
- AC-M1-02.4 Bật/tắt bằng env `MAGIC_LINK_ENABLED` (mặc định `false`); khi tắt, UI chỉ hiện Google login và endpoint magic link trả 404. Launch được với cờ tắt.

**FR-M1-03 Session & phân quyền.**
- AC-M1-03.1 Session hết hạn sau 30 ngày không hoạt động; đăng xuất xoá session server-side.
- AC-M1-03.2 Mọi request thay đổi dữ liệu (POST/PUT/PATCH/DELETE) PHẢI kèm CSRF token hợp lệ, nếu không trả 403.
- AC-M1-03.3 Role `learner` gọi endpoint `/api/v1/admin/*` → 403. Role `admin` chỉ gán qua CLI/seed (`python -m app.cli make-admin <email>`), không có UI tự nâng quyền.

**FR-M1-04 Truy cập khách.**
- AC-M1-04.1 Khách xem được thư viện bài (M3) và trang chi tiết bài; khi bấm "Bắt đầu học" → yêu cầu đăng nhập, sau đăng nhập quay lại đúng bài.

**FR-M1-05 Cài đặt & xoá tài khoản.**
- AC-M1-05.1 User chỉnh được: tên hiển thị, múi giờ (mặc định `Asia/Saigon`), bật/tắt email nhắc, giờ nhắc (mặc định 20:00), mặc định Strict punctuation, tốc độ phát mặc định.
- AC-M1-05.2 Given user bấm "Xoá tài khoản" và xác nhận bằng cách gõ email, Then xoá toàn bộ dữ liệu cá nhân (progress, vocab, activity, session) trong ≤ 1 phút; đăng xuất.

---

### M2 — Content ingestion (admin)

Vòng đời bài: `draft → processing → review → published` (+ `failed`, `unpublished`).

**FR-M2-01 Tạo bài.**
- AC-M2-01.1 Admin nhập: title, topic (`talk | news | interview | conversation`), level (`beginner | intermediate | advanced`), `source_name`, `source_url`, `license` (bắt buộc, ví dụ "Public domain — VOA"), audio file, transcript (plain text tiếng Anh).
- AC-M2-01.2 Audio chấp nhận mp3/m4a/wav, ≤ 30 MB, ≤ 15 phút; sai định dạng/quá giới hạn → lỗi rõ ràng, không tạo bài.
- AC-M2-01.3 Transcript rỗng hoặc > 20 000 ký tự → lỗi validation.
- AC-M2-01.4 Thiếu `license` → không cho submit.

**FR-M2-02 Pipeline tự động (worker).**
- AC-M2-02.1 Given bài vừa submit, Then trạng thái `processing` và 1 job được enqueue; UI admin hiển thị trạng thái, tự refresh (poll 5 s).
- AC-M2-02.2 Worker tách transcript thành câu (sentence splitter, giữ nguyên dấu câu gốc), chạy stable-ts forced alignment trên toàn transcript, tạo `segments` với `start_ms`/`end_ms`: `start = max(0, first_word_start − 150ms)`, `end = min(last_word_end + 500ms, next_segment_start, duration)`. Chỉ dùng từ align được làm mốc (token không align được không kéo lệch ranh giới). *(v1.3: +200ms → +500ms — đo trên bài VOA thật, aligner kết thúc từ cuối sớm; +200ms cắt mất "monarchs", +500ms không.)*
- AC-M2-02.3 Sau alignment, worker gọi LLM dịch từng câu sang tiếng Việt (có ngữ cảnh cả bài, batch), lưu `translation_vi`.
- AC-M2-02.4 Thành công → `review`. Lỗi bất kỳ bước nào → `failed` + lưu `error_message`; admin bấm "Chạy lại" được. Job retry tự động tối đa 2 lần với backoff.
- AC-M2-02.5 Segment có > 25 từ, < 1 s, có từ không align được, hoặc ≥ 3 từ (hoặc ≥ 20% số từ) align với độ tin cậy thấp được đánh cờ `needs_attention` kèm lý do để admin xem. *(v1.3: 1 từ kém tin cậy là bình thường — gắn cờ theo từng từ làm 20/39 câu bị cờ, mất tác dụng.)*
- AC-M2-02.6 Bài 5 phút audio xử lý xong (alignment + dịch) ≤ 10 phút trên VPS 4 vCPU.

**FR-M2-03 Review & chỉnh sửa.**
- AC-M2-03.1 Màn review liệt kê segment: số thứ tự, text, bản dịch, start/end, nút ▶ phát đúng đoạn đó; segment có cờ được highlight.
- AC-M2-03.2 Admin sửa được: text, bản dịch, start/end (ms, validate `start < end`, không chồng lấn segment kề), gộp 2 segment kề, tách 1 segment tại vị trí từ (timestamp tách lấy từ word alignment).
- AC-M2-03.3 Sửa text segment KHÔNG tự chạy lại alignment (MVP); admin tự chỉnh thời gian nếu cần.

**FR-M2-04 Publish / unpublish.**
- AC-M2-04.1 Chỉ publish được khi ở `review` hoặc `unpublished` và mọi segment có text, `translation_vi`, thời gian hợp lệ.
- AC-M2-04.2 Unpublish → bài biến mất khỏi thư viện; progress/vocab của learner giữ nguyên; learner đang mở bài thấy thông báo "Bài không còn khả dụng".
- AC-M2-04.3 Bài đã published: admin sửa trực tiếp được text, bản dịch, start/end (giữ `segment_id`, giữ progress; điểm cũ của learner không tính lại). Gộp/tách segment chỉ khi unpublish trước; gộp/tách xoá progress của segment liên quan — UI cảnh báo trước.

---

### M3 — Thư viện bài học

**FR-M3-01 Danh sách & lọc.**
- AC-M3-01.1 Hiển thị bài `published`, mỗi thẻ: title, topic, level, thời lượng (mm:ss), số câu, nguồn; nếu đã đăng nhập: % tiến độ và điểm tốt nhất.
- AC-M3-01.2 Lọc theo topic (multi) và level (multi), tìm theo title (không dấu/không phân biệt hoa thường); bộ lọc phản ánh vào URL query (`?topic=news&level=beginner`) để share/reload.
- AC-M3-01.3 Phân trang 24 bài/trang; sắp xếp mặc định mới nhất.
- AC-M3-01.4 Không có kết quả → empty state kèm nút "Xoá bộ lọc".

**FR-M3-02 Trang chi tiết bài.**
- AC-M3-02.1 Hiển thị metadata, nguồn + license (attribution bắt buộc), nút "Bắt đầu" / "Tiếp tục câu N" / "Làm lại".
- AC-M3-02.2 Transcript đầy đủ và bản dịch chỉ hiển thị sau khi user đã hoàn thành bài (tránh lộ đáp án).

---

### M4 — Smart Audio Player

**FR-M4-01 Phát theo segment + tự dừng.**
- AC-M4-01.1 Given Auto-pause BẬT (mặc định), When phát segment i, Then audio dừng tại `end_ms` của segment i với sai lệch ≤ 100 ms ở cả 3 tốc độ (đo bằng `currentTime` lúc pause; kiểm tra biên bằng `requestAnimationFrame`, không chỉ dựa `timeupdate`).
- AC-M4-01.2 Sau khi dừng, focus vẫn ở ô nhập của segment i; không tự sang câu sau.
- AC-M4-01.3 Given Auto-pause TẮT, Then audio phát liên tục; segment đang phát được highlight và ô nhập tương ứng tự focus khi segment đổi.
- AC-M4-01.4 "Phát lại câu" → seek về `start_ms` của segment hiện tại và phát.

**FR-M4-02 Tốc độ phát.**
- AC-M4-02.1 Chọn 0.75x / 1x / 1.25x; áp dụng ngay không reset vị trí; giữ cao độ (`preservesPitch = true`).
- AC-M4-02.2 Lựa chọn tốc độ lưu vào cài đặt user và áp dụng lại lần sau.

**FR-M4-03 Loop A-B.**
- AC-M4-03.1 User đặt A và B tại vị trí hiện tại (nút hoặc phím tắt); B phải > A + 500 ms, nếu không báo lỗi inline.
- AC-M4-03.2 Khi A-B hoạt động, audio lặp vô hạn trong [A, B] (sai lệch ≤ 100 ms), Auto-pause tạm vô hiệu; hiển thị marker A/B trên thanh tiến trình.
- AC-M4-03.3 Nút "Lặp câu này" = đặt A/B theo `start_ms`/`end_ms` segment hiện tại.
- AC-M4-03.4 "Xoá loop" hoặc chuyển segment → huỷ A-B, Auto-pause trở lại trạng thái trước.

**FR-M4-04 Điều hướng & phím tắt.**
- AC-M4-04.1 Nút câu trước/câu sau; thanh tiến trình click được để seek (seek vào segment nào thì segment đó thành hiện tại).
- AC-M4-04.2 Phím tắt hoạt động cả khi focus trong ô nhập, và `preventDefault` để không gõ ký tự: `Ctrl+Enter` phát lại câu · `Ctrl+'` play/pause · `Ctrl+.` câu sau · `Ctrl+,` câu trước. Có panel "Phím tắt" (`?` icon).
- AC-M4-04.3 Audio dùng `preload="metadata"`; seek hoạt động nhờ HTTP Range từ storage.
- AC-M4-04.4 Lỗi tải audio → thông báo + nút thử lại; không crash workspace.

---

### M5 — Dictation Workspace

**Tokenize & chuẩn hoá (áp dụng cho cả kịch bản và input):**
1. Unicode NFC; thay nháy cong `‘’“”` → `'` `"`; gạch nối `-`/`–`/`—` tách thành khoảng trắng.
2. Tách token theo khoảng trắng; dấu câu dính đầu/cuối từ tách thành token riêng (`.,!?;:"`). Apostrophe trong từ giữ nguyên (`don't`, `people's`).
3. So sánh không phân biệt hoa/thường.
4. Strict punctuation TẮT (mặc định): bỏ toàn bộ token dấu câu trước khi diff. BẬT: token dấu câu tham gia diff như từ.

**FR-M5-01 Ô nhập theo câu.**
- AC-M5-01.1 Mỗi segment có 1 ô nhập một dòng (textarea auto-grow, Enter không xuống dòng); chỉ segment hiện tại được nhập; segment đã hoàn thành hiển thị kết quả read-only (có nút "Sửa lại").
- AC-M5-01.2 Tắt autocorrect/autocomplete/spellcheck của trình duyệt trên ô nhập (`spellcheck=false autocomplete=off autocorrect=off autocapitalize=off`).

**FR-M5-02 Diff real-time.**
- AC-M5-02.1 Diff cấp từ dựa trên LCS/Myers giữa token kịch bản và token input; chạy hoàn toàn client-side, cập nhật sau mỗi keystroke ≤ 50 ms cho segment ≤ 60 từ (đo trên laptop tầm trung).
- AC-M5-02.2 Trạng thái token: `correct` (xanh + không gạch), `wrong` (đỏ + gạch chân lượn sóng), `extra` (đỏ + gạch ngang), `missing` (placeholder `___` màu đỏ chèn đúng vị trí), `pending` (xám, chấm gạch), `revealed` (vàng, gạch đứt). Ô `missing` CHỈ hiện ở vị trí learner đã gõ vượt qua; từ chưa gõ tới ở cuối câu KHÔNG hiện ô trống (tránh lộ số từ còn lại). Màu KHÔNG là tín hiệu duy nhất (có kiểu gạch/biểu tượng).
- AC-M5-02.3 KHÔNG lộ đáp án: `wrong`/`missing` không hiển thị từ đúng, và UI không để lộ số từ còn lại của câu, trừ khi dùng Gợi ý/Hiện đáp án.
- AC-M5-02.4 Token cuối đang gõ dở (chưa có khoảng trắng sau) mà là prefix của từ kỳ vọng tại vị trí đó → trạng thái `pending` (xám), không tô đỏ.
- AC-M5-02.5 Bộ test bảng (≥ 30 case) cho engine diff, gồm: hoa/thường, nháy cong, gạch nối, contraction, từ lặp, thiếu từ đầu/giữa/cuối, thừa từ, đảo từ, strict ON/OFF, input rỗng, chỉ dấu câu, không hiện ô trống cho từ chưa gõ tới, gợi ý (sửa 1 từ / điền ô trống / thêm từ kế), revealed.

**FR-M5-03 Chấm điểm.**
- AC-M5-03.1 Điểm segment = `correct / (expected + extra)` làm tròn %, hiển thị live, tính lại ngay mỗi keystroke (không debounce phần chấm). Cột điểm hiển thị thêm "N đúng · N sai · N chưa gõ" (chưa gõ = từ chưa tới, không tính là lỗi).
- AC-M5-03.2 Segment `completed` khi đạt 100%; khi đó hiện ✓, Enter → sang segment kế và (nếu Auto-pause) tự phát segment kế.
- AC-M5-03.3 Điểm bài = tổng `correct` / tổng `(expected + extra)` của mọi segment, tính theo lần nộp tốt nhất mỗi segment; lưu `best_score` cho bài.
- AC-M5-03.4 Đổi Strict punctuation giữa chừng → tính lại diff/điểm segment hiện tại ngay; điểm lưu kèm cờ `strict` đang dùng.

**FR-M5-04 Trợ giúp.**
- AC-M5-04.1 "Gợi ý" (`Ctrl+/`): sửa đúng MỘT từ tại vị trí lỗi đầu tiên (thay từ sai hoặc điền ô trống; nếu tất cả đang đúng thì thêm từ kế tiếp), giữ nguyên phần còn lại learner đã gõ; mỗi lần dùng tăng `hints_used` của segment.
- AC-M5-04.2 "Hiện đáp án": hiện toàn bộ câu; segment đánh dấu `revealed`, điểm segment ghi nhận = điểm ngay trước khi reveal (UI hiện điểm đó kèm nhãn "đã hiện đáp án", không hiện "—"); user vẫn có thể gõ lại để luyện nhưng điểm không tăng.
- AC-M5-04.3 "Xem bản dịch": bật/tắt hiển thị `translation_vi` của segment hiện tại bất kỳ lúc nào (mặc định ẩn); lựa chọn nhớ trong phiên.

**FR-M5-05 Lưu tiến độ.**
- AC-M5-05.1 Input nháp segment hiện tại autosave lên server (debounce 1 s); reload trang → khôi phục đúng segment và nội dung đang gõ.
- AC-M5-05.2 Mất mạng → tiếp tục gõ/chấm bình thường (chấm là client-side), hiển thị "Chưa lưu"; có mạng lại → tự đồng bộ bản mới nhất.
- AC-M5-05.3 Hoàn thành segment cuối → màn tổng kết: điểm bài, số câu revealed, số gợi ý, thời gian học, danh sách từ đã lưu trong bài, nút "Xem transcript + bản dịch", "Làm lại", "Bài tiếp theo cùng level".

---

### M6 — Vocabulary Builder

**FR-M6-01 Tra từ theo ngữ cảnh.**
- AC-M6-01.1 Từ trong segment `completed`/`revealed` và trong transcript sau khi xong bài click được; segment chưa xong KHÔNG click được (tránh lộ đáp án).
- AC-M6-01.2 Click → popover gồm: từ, lemma, IPA (US), từ loại, nghĩa tiếng Việt theo ngữ cảnh câu, 1 nghĩa phổ biến khác (nếu khác), câu ngữ cảnh gốc; nút ▶ nghe lại câu chứa từ; nút "Lưu".
- AC-M6-01.3 Backend gọi LLM với structured output (JSON schema cố định), validate bằng Pydantic; output sai schema → retry 1 lần rồi trả lỗi thân thiện.
- AC-M6-01.4 Cache theo `(normalized_word, segment_id)`: lần 2 cùng khoá KHÔNG gọi LLM. Latency p95: cache hit ≤ 300 ms, miss ≤ 3 s.
- AC-M6-01.5 Rate limit: 60 lookup/phút/user (mọi lookup) và 500 lookup cache-miss/ngày/user; vượt → 429 + thông báo.
- AC-M6-01.6 Mọi lời gọi LLM ghi log: model, input/output tokens, latency, cache hit/miss (phục vụ theo dõi chi phí).

**FR-M6-02 Sổ tay từ vựng.**
- AC-M6-02.1 "Lưu" tạo `vocab_item` gồm lemma, nghĩa, IPA, từ loại, câu ngữ cảnh, `segment_id`, `lesson_id`. Duy nhất theo `(user, lemma)`: lưu trùng → báo "Đã có trong sổ", không tạo bản mới.
- AC-M6-02.2 Trang Sổ tay: danh sách, tìm kiếm, lọc (Tất cả / Đến hạn / Mới), sắp xếp (mới nhất, đến hạn sớm nhất); mỗi mục: từ, nghĩa, ngày đến hạn, link về bài gốc.
- AC-M6-02.3 User sửa được nghĩa + thêm ghi chú cá nhân (≤ 500 ký tự); xoá mục (có xác nhận).

**FR-M6-03 Ôn tập FSRS.**
- AC-M6-03.1 Phiên ôn lấy các thẻ `due <= now` (tối đa 50/phiên), thứ tự due sớm nhất trước; thẻ mới (chưa ôn) tối đa 20/ngày.
- AC-M6-03.2 Mặt trước: từ + IPA + nút nghe câu ngữ cảnh (phát đúng segment audio). Mặt sau (Space/click để lật): nghĩa, từ loại, câu ngữ cảnh (từ được highlight), ghi chú.
- AC-M6-03.3 4 nút đánh giá Again / Hard / Good / Easy (phím 1–4), mỗi nút hiển thị khoảng cách lần ôn kế (ví dụ "10 phút", "3 ngày") do server tính trước.
- AC-M6-03.4 Đánh giá → server cập nhật trạng thái FSRS (`fsrs` Python) và ghi `review_log`; client không tự tính lịch.
- AC-M6-03.5 Không còn thẻ due → màn "Đã ôn xong hôm nay" + số thẻ đến hạn ngày mai.

---

### M7 — Retention

**FR-M7-01 Tiếp tục học & lịch sử.**
- AC-M7-01.1 Dashboard (trang chủ sau đăng nhập) hiển thị: "Tiếp tục học" (bài dở gần nhất, câu N/M), số từ đến hạn ôn, streak hiện tại, 5 bài học gần nhất kèm điểm tốt nhất.
- AC-M7-01.2 Trang Lịch sử: mọi bài đã bắt đầu, trạng thái (đang học / hoàn thành), % tiến độ, điểm tốt nhất, lần học cuối.

**FR-M7-02 Streak.**
- AC-M7-02.1 Một ngày (theo múi giờ user) được tính "hoạt động" khi user hoàn thành ≥ 1 segment HOẶC chấm ≥ 1 thẻ ôn.
- AC-M7-02.2 Streak = số ngày hoạt động liên tiếp tính đến hôm nay (hoặc hôm qua nếu hôm nay chưa hoạt động); bỏ lỡ 1 ngày → reset về 0 ở ngày kế tiếp. Lưu `longest_streak`.
- AC-M7-02.3 Test đơn vị cho ranh giới ngày: hoạt động 23:59 và 00:01 giờ `Asia/Saigon` là 2 ngày khác nhau; đổi múi giờ user không làm mất lịch sử `daily_activity`.

**FR-M7-03 Badge từ đến hạn.**
- AC-M7-03.1 Header hiển thị badge số thẻ due (ẩn nếu 0); cập nhật sau mỗi lần ôn/lưu từ mà không reload.

**FR-M7-04 Email nhắc hằng ngày.**
- AC-M7-04.1 Scheduler trong worker chạy mỗi 15 phút, gửi cho user có `email_reminder=true` mà giờ nhắc (theo múi giờ user) rơi vào khung hiện tại.
- AC-M7-04.2 CHỈ gửi khi hôm nay user chưa hoạt động VÀ (có thẻ due > 0 HOẶC streak hiện tại ≥ 1). Tối đa 1 email/user/ngày (idempotent qua bảng `email_log` unique `(user_id, date, type)`).
- AC-M7-04.3 Nội dung: streak hiện tại, số từ đến hạn, link "Tiếp tục học" (bài dở) — tiếng Việt, HTML + text.
- AC-M7-04.4 Mọi email có link hủy 1-click (token ký, không cần đăng nhập) + header `List-Unsubscribe`; bấm → `email_reminder=false` ngay.
- AC-M7-04.5 Gửi lỗi → retry tối đa 2 lần, sau đó log lỗi; không gửi trùng.
- AC-M7-04.6 Tính năng bật/tắt bằng env `EMAIL_REMINDERS_ENABLED` (mặc định `false`); khi tắt, scheduler không gửi email nhắc và UI cài đặt ẩn tuỳ chọn nhắc. Magic link có cờ riêng (AC-M1-02.4). Launch KHÔNG bị chặn bởi email nhắc.

---

## 3. Yêu cầu phi chức năng

| ID | Hạng mục | Yêu cầu đo được |
|---|---|---|
| NFR-01 | Hiệu năng web | LCP ≤ 2.5 s (Lighthouse mobile, 4G giả lập) cho thư viện & workspace; JS bundle route workspace ≤ 250 KB gzip |
| NFR-02 | Hiệu năng API | p95 ≤ 300 ms cho endpoint không gọi LLM ở 50 req/s |
| NFR-03 | Độ chính xác player | Xem AC-M4-01.1, AC-M4-03.2 (±100 ms) |
| NFR-04 | Bảo mật | OWASP Top 10: cookie httpOnly/Secure/SameSite, CSRF token, validate mọi input bằng Pydantic, parameterized query (ORM), CORS chỉ origin web, security headers (CSP, HSTS) qua Caddy; secrets chỉ qua env, không commit |
| NFR-05 | Upload an toàn | Kiểm tra MIME thật (magic bytes) + giới hạn kích thước; tên file lưu là UUID |
| NFR-06 | Quyền riêng tư | Chỉ lưu email, tên, cài đặt, dữ liệu học; không gửi email/tên user sang LLM; xoá tài khoản theo AC-M1-05.2 |
| NFR-07 | Accessibility | Toàn bộ flow dictation + ôn tập làm được chỉ bằng bàn phím; tương phản WCAG AA; trạng thái diff không chỉ dựa vào màu; có `aria-live` cho điểm segment |
| NFR-08 | Responsive | Dùng được từ 360 px; desktop-first cho workspace |
| NFR-09 | Trình duyệt | 2 phiên bản mới nhất Chrome, Edge, Safari (macOS + iOS), Firefox |
| NFR-10 | Độ tin cậy | Job ingest/email idempotent, retry có giới hạn; backup Postgres hằng ngày giữ 7 bản |
| NFR-11 | Quan sát | Log JSON có request id; log chi phí LLM (AC-M6-01.6); endpoint `/healthz` cho api & worker heartbeat |
| NFR-12 | Chi phí LLM | Mục tiêu ≤ 1 USD/1000 lookup trung bình nhờ cache; cảnh báo log khi vượt ngưỡng ngày cấu hình qua env |
| NFR-13 | Ngôn ngữ UI | Tiếng Việt; nội dung học tiếng Anh |
| NFR-14 | Chất lượng code | TS strict, ESLint + Prettier; Python ruff + mypy; test coverage ≥ 80% cho engine diff, streak, FSRS service, auth |

---

## 4. Data model (logic)

| Bảng | Trường chính | Ghi chú |
|---|---|---|
| `users` | id, email (unique), name, role, timezone, email_reminder, reminder_time, strict_punct_default, playback_rate_default, created_at | |
| `sessions` | id, user_id, expires_at, csrf_token | |
| `magic_links` | token_hash, email, expires_at, used_at | |
| `lessons` | id, slug, title, topic, level, source_name, source_url, license, audio_key, duration_ms, status, error_message, published_at | enum topic/level/status |
| `segments` | id, lesson_id, idx, text, translation_vi, start_ms, end_ms, words_json, needs_attention | unique (lesson_id, idx); `words_json` = word timings dùng cho tách segment |
| `jobs` | id, type, payload, status, attempts, run_after, locked_at, last_error | queue Postgres |
| `lesson_progress` | user_id, lesson_id, current_segment_idx, status, best_score, started_at, completed_at, last_active_at | PK (user_id, lesson_id) |
| `segment_attempts` | user_id, segment_id, draft_text, best_score, completed, revealed, hints_used, strict, updated_at | PK (user_id, segment_id) |
| `word_lookups` | id, normalized_word, segment_id, response_json, model, created_at | unique (normalized_word, segment_id) |
| `vocab_items` | id, user_id, lemma, meaning_vi, ipa, pos, context_text, segment_id, lesson_id, note, fsrs_state_json, due_at, created_at | unique (user_id, lemma); index (user_id, due_at) |
| `review_logs` | id, vocab_item_id, rating, reviewed_at, prev/next due | |
| `daily_activity` | user_id, date, segments_completed, reviews_done | PK (user_id, date) |
| `email_log` | user_id, date, type, status, sent_at | unique (user_id, date, type) |
| `llm_usage` | id, purpose, model, input_tokens, output_tokens, latency_ms, cache_hit, created_at | |

## 5. API (REST `/api/v1`, tóm tắt)

| Nhóm | Endpoint |
|---|---|
| Auth | `GET /auth/google/start`, `GET /auth/google/callback`, `POST /auth/magic-link`, `GET /auth/magic-link/verify`, `POST /auth/logout`, `GET /me`, `PATCH /me`, `DELETE /me` |
| Lessons | `GET /lessons?topic&level&q&page`, `GET /lessons/{slug}`, `GET /lessons/{slug}/segments` (text chỉ trả khi user đã completed/revealed segment đó hoặc đã xong bài; luôn trả timing) |
| Progress | `GET /progress`, `PUT /lessons/{id}/progress`, `PUT /segments/{id}/attempt` |
| Vocab | `GET /lookup?word&segment_id`, `GET /vocab?filter&q&sort&page`, `POST /vocab`, `PATCH /vocab/{id}`, `DELETE /vocab/{id}`, `GET /reviews/due`, `POST /reviews/{vocab_id}` {rating} |
| Dashboard | `GET /dashboard` (continue, due_count, streak, recent) |
| Email | `GET /email/unsubscribe?token` |
| Admin | `POST /admin/lessons` (multipart), `GET /admin/lessons`, `GET/PATCH /admin/lessons/{id}`, `POST /admin/lessons/{id}/retry`, `PATCH /admin/segments/{id}`, `POST /admin/segments/{id}/split`, `POST /admin/segments/merge`, `POST /admin/lessons/{id}/publish`, `POST /admin/lessons/{id}/unpublish` |

> **Lưu ý chống lộ đáp án:** vì chấm điểm ở client cần text kịch bản, endpoint segments trả text của segment hiện tại để chấm. Chấp nhận rủi ro user đọc DevTools (app học, không phải thi) — KHÔNG hiển thị text trong UI trước khi hoàn thành/reveal.

## 6. Milestones build (thứ tự cho Claude Code)

| # | Milestone | Bao gồm | Exit criteria |
|---|---|---|---|
| 0 | Scaffold | Monorepo, Docker Compose, Postgres + Alembic, CI (lint, typecheck, test), sinh TS client từ OpenAPI | `docker compose up` chạy đủ 4 service; CI xanh |
| 1 | Auth + Content | M1, M2 | Admin ingest 1 bài VOA thật → published với segments đúng timing |
| 2 | Core learning loop | M3, M4, M5 | Learner làm hết 1 bài chỉ bằng bàn phím; mọi AC M3–M5 pass |
| 3 | Vocabulary | M6 | Tra, lưu, ôn 1 phiên hoàn chỉnh; cache hit xác nhận qua `llm_usage` |
| 4 | Retention | M7 | Streak/dashboard đúng; email nhắc gửi thật qua provider, unsubscribe hoạt động |
| 5 | Hardening | NFR, e2e Playwright, deploy VPS, backup | Mọi NFR đo & đạt; seed ≥ 30 bài (≥ 10 mỗi level) |

## 7. Definition of Done (mỗi FR)
1. Mọi AC của FR có test tự động (unit/API/e2e) hoặc checklist manual ghi trong PR nếu không tự động được (ví dụ độ trễ pause trên Safari iOS).
2. Lint, typecheck, test pass trên CI.
3. Migration Alembic có downgrade.
4. Không secret trong repo; biến môi trường mới được thêm vào `.env.example`.
5. `docs/` cập nhật nếu thay đổi API/kiến trúc.

## 8. Câu hỏi còn mở
- Tên sản phẩm / domain.
- Nhà cung cấp email cụ thể (Resend vs SMTP) và domain gửi (cần SPF/DKIM).
- Quy mô VPS (RAM ≥ 8 GB khuyến nghị cho stable-ts/Whisper CPU).
- Có cần tương đương số–chữ ("5" ≡ "five") ở phase sau không.
