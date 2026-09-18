import { isPrefixOf, wordsMatch } from "./normalize";
import { splitInput } from "./tokenize";

export type TokenStatus = "correct" | "wrong" | "extra" | "missing" | "pending" | "revealed";

export interface Token {
  status: TokenStatus;
  /** Chữ để hiển thị. `missing` → chuỗi rỗng (view tự vẽ ô trống). */
  text: string;
  /** Vị trí từ trong câu gốc (undefined với `extra`). */
  expectedIndex?: number;
}

export interface DiffOptions {
  /** Bắt lỗi dấu câu & chữ hoa (mặc định tắt). */
  strict?: boolean;
  /** Câu đã bấm "Hiện đáp án" → trả toàn bộ câu ở trạng thái `revealed`. */
  revealed?: boolean;
}

type RawOp = { kind: "ok" | "wrong" | "extra" | "missing"; text: string; expectedIndex?: number };

/** LCS trên token đã chuẩn hoá (≤ 60 từ → O(n·m) đủ nhanh, xem benchmark trong test). */
function lcsOps(expected: string[], typed: string[], strict: boolean): RawOp[] {
  const n = expected.length;
  const m = typed.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = wordsMatch(expected[i], typed[j], strict)
        ? dp[i + 1][j + 1] + 1
        : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const ops: RawOp[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (wordsMatch(expected[i], typed[j], strict)) {
      ops.push({ kind: "ok", text: typed[j], expectedIndex: i });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      ops.push({ kind: "missing", text: expected[i], expectedIndex: i });
      i++;
    } else {
      ops.push({ kind: "extra", text: typed[j] });
      j++;
    }
  }
  while (i < n) ops.push({ kind: "missing", text: expected[i], expectedIndex: i++ });
  while (j < m) ops.push({ kind: "extra", text: typed[j++] });

  // missing + extra cạnh nhau = người học gõ sai một từ → gộp thành `wrong`
  const merged: RawOp[] = [];
  for (let k = 0; k < ops.length; k++) {
    const a = ops[k];
    const b = ops[k + 1];
    const pair =
      b && ((a.kind === "missing" && b.kind === "extra") || (a.kind === "extra" && b.kind === "missing"));
    if (pair) {
      const typedOp = a.kind === "extra" ? a : b;
      const expectedOp = a.kind === "missing" ? a : b;
      merged.push({ kind: "wrong", text: typedOp.text, expectedIndex: expectedOp.expectedIndex });
      k++;
    } else {
      merged.push(a);
    }
  }
  return merged;
}

/**
 * So khớp câu gốc với những gì người học đã gõ.
 *
 * Bất biến quan trọng (AC-M5-02.x): KHÔNG bao giờ để lộ đáp án — kể cả số từ còn lại.
 * Vì vậy các ô `missing` ở cuối (những từ người học chưa gõ tới) bị bỏ, và từ đang gõ
 * được so bằng tiền tố với đúng một từ kỳ vọng ở vị trí tương ứng.
 */
export function diffWords(expected: string[], typedText: string, options: DiffOptions = {}): Token[] {
  const { strict = false, revealed = false } = options;
  if (revealed) {
    return expected.map((text, expectedIndex) => ({ status: "revealed", text, expectedIndex }));
  }

  const { settled, inProgress } = splitInput(typedText);
  const ops = lcsOps(expected, settled, strict);

  // bỏ ô trống ở cuối: đó là những từ chưa gõ tới, không phải lỗi
  let end = ops.length;
  while (end > 0 && ops[end - 1].kind === "missing") end--;
  const tokens: Token[] = ops.slice(0, end).map((op) => ({
    status: op.kind === "ok" ? "correct" : op.kind,
    text: op.kind === "missing" ? "" : op.text,
    expectedIndex: op.expectedIndex,
  }));

  if (inProgress !== null) {
    // số từ câu gốc đã được phần "đã chốt" dùng hết (extra không tiêu từ nào)
    const consumed = tokens.reduce((n, t) => n + (t.status === "extra" ? 0 : 1), 0);
    const want = expected[consumed];
    if (!want) tokens.push({ status: "extra", text: inProgress });
    else if (isPrefixOf(inProgress, want, strict))
      tokens.push({ status: "pending", text: inProgress, expectedIndex: consumed });
    else tokens.push({ status: "wrong", text: inProgress, expectedIndex: consumed });
  }

  return tokens;
}

/**
 * "Gợi ý" — hiện đúng MỘT từ tại vị trí lỗi đầu tiên và giữ nguyên mọi thứ người học đã gõ.
 * Trả về text mới cho ô nhập (đã kèm khoảng trắng nếu cần), hoặc null khi không còn gì để gợi.
 */
export function applyHint(expected: string[], typedText: string, options: DiffOptions = {}): string | null {
  const tokens = diffWords(expected, typedText, options);
  const { settled, inProgress } = splitInput(typedText);
  const words = inProgress === null ? [...settled] : [...settled, inProgress];

  let typedIndex = 0;
  let expectedIndex = 0;
  let firstBad = -1;
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i].status !== "correct") {
      firstBad = i;
      break;
    }
    typedIndex++;
    expectedIndex++;
  }

  const word = expected[expectedIndex];
  if (!word) return null;

  if (firstBad === -1) {
    words.splice(typedIndex, 0, word); // tất cả đang đúng → thêm từ kế tiếp
  } else if (tokens[firstBad].status === "missing") {
    words.splice(typedIndex, 0, word); // điền vào ô trống, không xoá gì
  } else {
    words.splice(typedIndex, 1, word); // sửa đúng một từ
  }

  // giữ nguyên trạng thái "đang gõ" của người học: chỉ thêm space khi input vốn đã có
  const keepSpace = firstBad === -1 || /\s$/.test(typedText);
  return words.join(" ") + (keepSpace ? " " : "");
}
