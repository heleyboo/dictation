import { safeReturnTo } from "./safe-return-to";

const ORIGIN = "https://dictation.example";

describe("safeReturnTo", () => {
  it.each([
    ["/admin/lessons/3?x=1#s", "/admin/lessons/3?x=1#s"],
    [null, "/"],
    ["", "/"],
    ["admin", "/"],
    ["https://evil.com/x", "/"],
    ["//evil.com/x", "/"],
    ["/\\evil.com", "/"],
    ["/\t/evil.com", "/"],
  ])("%s → %s", (input, expected) => {
    expect(safeReturnTo(input, ORIGIN)).toBe(expected);
  });
});
