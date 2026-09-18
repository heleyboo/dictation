/** Chuẩn hoá token để so khớp. Không dùng cho hiển thị. */

// Dấu câu bỏ qua khi `strict = false` (mặc định, SRS FR-M5-03).
const PUNCTUATION = /[.,!?;:"'\u2019\u201c\u201d\-\u2014\u2026]/g;

export function normalizeWord(word: string, strict = false): string {
  const trimmed = word.trim();
  if (strict) return trimmed;
  return trimmed.replace(PUNCTUATION, "").toLowerCase();
}

/** Hai token có coi là khớp nhau không. */
export function wordsMatch(a: string, b: string, strict = false): boolean {
  return normalizeWord(a, strict) === normalizeWord(b, strict);
}

/** `typed` có phải tiền tố hợp lệ của `expected` (dùng cho trạng thái `pending`). */
export function isPrefixOf(typed: string, expected: string, strict = false): boolean {
  const t = normalizeWord(typed, strict);
  if (!t) return false;
  return normalizeWord(expected, strict).startsWith(t);
}
