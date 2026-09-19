"""Sentence-by-sentence English → Vietnamese translation at ingest (AC-M2-02.3)."""

from pydantic import BaseModel

from app.services.llm_client import LlmError, StructuredLlm

BATCH_SIZE = 40

SYSTEM = (
    "Bạn là biên dịch viên Anh–Việt cho ứng dụng luyện nghe chép chính tả. Người học đọc bản dịch để hiểu "
    "câu tiếng Anh họ vừa nghe, nên bản dịch phải đúng nghĩa và tự nhiên như báo chí tiếng Việt.\n"
    "Quy tắc:\n"
    "- Mỗi câu tiếng Anh dịch thành đúng một câu tiếng Việt; không gộp, không bỏ câu, không thêm chú thích.\n"
    "- Dịch theo nghĩa trong ngữ cảnh cả bài, không dịch từng chữ. Cụm động từ và thành ngữ dịch theo "
    "nghĩa thực (ví dụ 'the plane took off' là 'máy bay cất cánh', không phải 'máy bay cởi ra').\n"
    "- Giữ nguyên tiếng Anh cho tên riêng: người, tổ chức, thương hiệu, địa danh, dãy núi, sông, thành phố. "
    "Không phiên âm hay dịch từng phần của tên riêng. Chỉ dùng tên tiếng Việt khi đó là tên quen thuộc "
    "(Hoa Kỳ, Mexico, California, Bắc Mỹ).\n"
    "- Tên loài động thực vật hay thuật ngữ chuyên môn: dùng tên tiếng Việt thông dụng nếu chắc chắn; "
    "nếu không chắc, giữ tên tiếng Anh.\n"
    "- Giữ nguyên số liệu và đơn vị; dùng dấu phẩy thập phân kiểu Việt (37,7 độ C)."
)


class Translation(BaseModel):
    idx: int
    vi: str


class TranslationBatch(BaseModel):
    translations: list[Translation]


def _prompt(title: str, sentences: list[str], batch: range) -> str:
    context = "\n".join(sentences)
    wanted = "\n".join(f"{i}: {sentences[i]}" for i in batch)
    return (
        f"Tiêu đề bài: {title}\n\nToàn văn (để hiểu ngữ cảnh):\n{context}\n\n"
        f"Hãy dịch các câu sau, trả về đúng từng `idx`:\n{wanted}"
    )


async def translate_sentences(llm: StructuredLlm, title: str, sentences: list[str]) -> list[str]:
    """Returns one translation per sentence, in order. Each batch is retried once on a bad answer."""
    result: list[str | None] = [None] * len(sentences)
    for start in range(0, len(sentences), BATCH_SIZE):
        batch = range(start, min(start + BATCH_SIZE, len(sentences)))
        for attempt in (1, 2):
            try:
                answer = await llm.parse(
                    purpose="translate",
                    system=SYSTEM,
                    prompt=_prompt(title, sentences, batch),
                    schema=TranslationBatch,
                )
            except LlmError:
                if attempt == 2:
                    raise
                continue
            got = {t.idx: t.vi.strip() for t in answer.translations if t.idx in batch and t.vi.strip()}
            if set(got) == set(batch):
                for i, vi in got.items():
                    result[i] = vi
                break
            if attempt == 2:
                missing = sorted(set(batch) - set(got))
                raise LlmError(f"translation missing sentences {missing[:10]}")
    return [vi for vi in result if vi is not None]
