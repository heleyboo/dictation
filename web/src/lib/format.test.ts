import { formatBytes, formatDuration } from "./format";

describe("format", () => {
  it("formats durations as mm:ss", () => {
    expect(formatDuration(0)).toBe("00:00");
    expect(formatDuration(83_500)).toBe("01:24");
    expect(formatDuration(15 * 60 * 1000)).toBe("15:00");
  });
  it("formats byte sizes", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(1_572_864)).toBe("1.5 MB");
  });
});
