import { describe, expect, it } from "vitest";
import { applyHint, diffWords } from "./diff-words";
import { scoreTokens } from "./score";
import { splitWords } from "./tokenize";

const SENTENCE = "Scientists say the new study could change how we think about sleep.";
const EXPECTED = splitWords(SENTENCE); // 12 từ

const shape = (typed: string, strict = false) =>
  diffWords(EXPECTED, typed, { strict }).map((t) => `${t.status}:${t.text}`);

describe("diffWords", () => {
  it("câu rỗng → không token nào", () => {
    expect(diffWords(EXPECTED, "")).toEqual([]);
  });

  it("gõ đúng hoàn toàn → tất cả correct", () => {
    const tokens = diffWords(EXPECTED, SENTENCE);
    expect(tokens.every((t) => t.status === "correct")).toBe(true);
    expect(scoreTokens(tokens, EXPECTED.length)).toMatchObject({ percent: 100, isPerfect: true });
  });

  it("từ đang gõ khớp tiền tố → pending, không lộ đáp án", () => {
    expect(shape("Scien")).toEqual(["pending:Scien"]);
  });

  it("từ đang gõ sai tiền tố → wrong", () => {
    expect(shape("Xyz")).toEqual(["wrong:Xyz"]);
  });

  it("does not leak unreached words (không hiện ô trống cho từ chưa gõ tới)", () => {
    const tokens = shape("Scientist say the study could changed how we thin");
    expect(tokens).toEqual([
      "wrong:Scientist",
      "correct:say",
      "correct:the",
      "missing:",
      "correct:study",
      "correct:could",
      "wrong:changed",
      "correct:how",
      "correct:we",
      "pending:thin",
    ]);
    expect(tokens.filter((t) => t.startsWith("missing")).length).toBe(1);
  });

  it("điểm mẫu của input trên là 50%", () => {
    const tokens = diffWords(EXPECTED, "Scientist say the study could changed how we thin");
    expect(scoreTokens(tokens, EXPECTED.length)).toMatchObject({
      percent: 50,
      correct: 6,
      wrong: 2,
      missing: 1,
      untyped: 2,
    });
  });

  it("ô trống giữa câu vẫn hiện khi người học đã gõ vượt qua nó", () => {
    expect(shape("Scientists say the study ")).toEqual([
      "correct:Scientists",
      "correct:say",
      "correct:the",
      "missing:",
      "correct:study",
    ]);
  });

  it("từ thừa → extra", () => {
    expect(shape("Scientists really say ")).toEqual(["correct:Scientists", "extra:really", "correct:say"]);
  });

  it("bỏ dấu câu và chữ hoa khi strict = false", () => {
    expect(shape("scientists, say ")).toEqual(["correct:scientists,", "correct:say"]);
  });

  it("strict = true bắt lỗi dấu câu và chữ hoa", () => {
    const tokens = shape("scientists say ", true);
    expect(tokens[0]).toBe("wrong:scientists");
    expect(tokens[1]).toBe("correct:say");
  });

  it("revealed → toàn bộ câu ở trạng thái revealed, điểm null", () => {
    const tokens = diffWords(EXPECTED, "", { revealed: true });
    expect(tokens).toHaveLength(EXPECTED.length);
    expect(tokens.every((t) => t.status === "revealed")).toBe(true);
    expect(scoreTokens(tokens, EXPECTED.length).percent).toBeNull();
  });

  it("gõ dài hơn câu gốc → extra ở cuối", () => {
    const tokens = diffWords(EXPECTED, SENTENCE + " really ");
    expect(tokens[tokens.length - 1]).toMatchObject({ status: "extra", text: "really" });
  });

  it("60 từ chạy dưới 5 ms", () => {
    const long = splitWords(Array.from({ length: 60 }, (_, i) => `word${i}`).join(" "));
    const typed = long.slice(0, 55).join(" ") + " ";
    const t0 = performance.now();
    diffWords(long, typed);
    expect(performance.now() - t0).toBeLessThan(5);
  });
});

describe("applyHint", () => {
  const typed = "Scientist say the study could changed how we thin";

  it("sửa đúng một từ, giữ nguyên phần còn lại", () => {
    expect(applyHint(EXPECTED, typed)).toBe("Scientists say the study could changed how we thin");
  });

  it("gợi ý lần hai điền vào ô trống, điểm chỉ tăng", () => {
    const once = applyHint(EXPECTED, typed)!;
    const twice = applyHint(EXPECTED, once)!;
    expect(twice).toBe("Scientists say the new study could changed how we thin");
    const s1 = scoreTokens(diffWords(EXPECTED, typed), EXPECTED.length).percent!;
    const s2 = scoreTokens(diffWords(EXPECTED, once), EXPECTED.length).percent!;
    const s3 = scoreTokens(diffWords(EXPECTED, twice), EXPECTED.length).percent!;
    expect(s1).toBeLessThan(s2);
    expect(s2).toBeLessThan(s3);
  });

  it("không giữ khoảng trắng cuối khi người học đang gõ giữa từ", () => {
    expect(applyHint(EXPECTED, typed)!.endsWith(" ")).toBe(false);
  });

  it("đang đúng hết → thêm từ kế tiếp kèm khoảng trắng", () => {
    expect(applyHint(EXPECTED, "Scientists say ")).toBe("Scientists say the ");
  });

  it("câu đã xong → null", () => {
    expect(applyHint(EXPECTED, SENTENCE + " ")).toBeNull();
  });
});
