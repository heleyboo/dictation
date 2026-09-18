import type { Token } from "./diff-words";

export interface SentenceScore {
  /** 0–100, làm tròn. Câu đã hiện đáp án → null (hiển thị "—"). */
  percent: number | null;
  correct: number;
  wrong: number;
  /** ô trống thật sự bên trong phần đã gõ */
  missing: number;
  /** từ người học chưa gõ tới — nhãn UI là "chưa gõ", không phải "thiếu" */
  untyped: number;
  extra: number;
  isPerfect: boolean;
}

export function scoreTokens(tokens: Token[], expectedCount: number): SentenceScore {
  if (tokens.some((t) => t.status === "revealed")) {
    return { percent: null, correct: 0, wrong: 0, missing: 0, untyped: expectedCount, extra: 0, isPerfect: false };
  }
  const count = (s: Token["status"]) => tokens.filter((t) => t.status === s).length;
  const correct = count("correct");
  const wrong = count("wrong");
  const missing = count("missing");
  const extra = count("extra");
  const pending = count("pending");
  const untyped = Math.max(0, expectedCount - correct - wrong - missing - pending);
  return {
    percent: expectedCount ? Math.round((correct / expectedCount) * 100) : 0,
    correct,
    wrong,
    missing,
    untyped,
    extra,
    isPerfect: correct === expectedCount && wrong === 0 && extra === 0 && missing === 0,
  };
}
