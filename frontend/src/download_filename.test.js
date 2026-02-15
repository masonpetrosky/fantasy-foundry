import { describe, expect, it } from "vitest";
import { parseDownloadFilename } from "./download_filename.js";

describe("parseDownloadFilename", () => {
  it("uses fallback when header is missing", () => {
    expect(parseDownloadFilename(null, "dynasty-rankings.csv")).toBe("dynasty-rankings.csv");
  });

  it("parses quoted filename values", () => {
    const disposition = 'attachment; filename="dynasty-rankings.csv"';
    expect(parseDownloadFilename(disposition, "fallback.csv")).toBe("dynasty-rankings.csv");
  });

  it("parses unquoted filename values", () => {
    const disposition = "attachment; filename=dynasty-rankings.csv";
    expect(parseDownloadFilename(disposition, "fallback.csv")).toBe("dynasty-rankings.csv");
  });

  it("prefers RFC 5987 filename* over filename", () => {
    const disposition = "attachment; filename=fallback.csv; filename*=UTF-8''dynasty%20rankings.csv";
    expect(parseDownloadFilename(disposition, "backup.csv")).toBe("dynasty rankings.csv");
  });

  it("sanitizes forbidden path characters", () => {
    const disposition = 'attachment; filename="..\\\\reports/2026:dynasty?.csv"';
    expect(parseDownloadFilename(disposition, "safe.csv")).toBe(".._reports_2026_dynasty_.csv");
  });

  it("falls back when extracted filename is empty after sanitization", () => {
    const disposition = `attachment; filename="${String.fromCharCode(0, 1)}"`;
    expect(parseDownloadFilename(disposition, "safe.csv")).toBe("safe.csv");
  });
});
