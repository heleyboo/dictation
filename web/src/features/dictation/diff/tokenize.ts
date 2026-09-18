/** Tách câu thành token hiển thị (giữ nguyên dấu câu và chữ hoa). */
export function splitWords(text: string): string[] {
  const trimmed = text.trim();
  return trimmed ? trimmed.split(/\s+/) : [];
}

/** Người học vừa gõ xong một từ (đã nhấn space) hay đang gõ giữa từ. */
export function endsWithSeparator(text: string): boolean {
  return /\s$/.test(text);
}

/**
 * Chia input thành phần "đã chốt" và từ "đang gõ".
 * Chỉ từ cuối cùng khi input KHÔNG kết thúc bằng khoảng trắng là đang gõ.
 */
export function splitInput(text: string): { settled: string[]; inProgress: string | null } {
  const words = splitWords(text);
  if (!words.length || endsWithSeparator(text)) return { settled: words, inProgress: null };
  return { settled: words.slice(0, -1), inProgress: words[words.length - 1] };
}
