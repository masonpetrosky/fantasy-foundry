import { afterEach, describe, expect, it, vi } from "vitest";
import { downloadBlob, triggerBlobDownload } from "./download_helpers";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("triggerBlobDownload", () => {
  it("creates an anchor, clicks it, and revokes the URL", () => {
    const fakeUrl = "blob:http://localhost/fake";
    URL.createObjectURL = vi.fn().mockReturnValue(fakeUrl);
    URL.revokeObjectURL = vi.fn();

    const anchor = { href: "", download: "", click: vi.fn(), remove: vi.fn() };
    vi.spyOn(document, "createElement").mockReturnValue(anchor as unknown as HTMLElement);
    vi.spyOn(document.body, "appendChild").mockImplementation(() => null as unknown as HTMLElement);

    const blob = new Blob(["test"], { type: "text/plain" });
    triggerBlobDownload("test.txt", blob);

    expect(anchor.download).toBe("test.txt");
    expect(anchor.click).toHaveBeenCalled();
    expect(anchor.remove).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith(fakeUrl);
  });
});

describe("downloadBlob", () => {
  it("creates a blob with the given mime type and triggers download", () => {
    URL.createObjectURL = vi.fn().mockReturnValue("blob:fake");
    URL.revokeObjectURL = vi.fn();

    const anchor = { href: "", download: "", click: vi.fn(), remove: vi.fn() };
    vi.spyOn(document, "createElement").mockReturnValue(anchor as unknown as HTMLElement);
    vi.spyOn(document.body, "appendChild").mockImplementation(() => null as unknown as HTMLElement);

    downloadBlob("data.csv", "a,b,c", "text/csv");

    expect(anchor.download).toBe("data.csv");
    expect(URL.createObjectURL).toHaveBeenCalled();
  });
});
