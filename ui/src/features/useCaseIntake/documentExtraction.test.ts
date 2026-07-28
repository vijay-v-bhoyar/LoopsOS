import { describe, expect, it, vi } from "vitest";
import { extractDocument, IntakeError } from "./documentExtraction";

function file(name: string, contents: string, type: string): File {
  return new File([contents], name, { type });
}

describe("extractDocument", () => {
  it("extracts TXT and Markdown locally without invoking a binary parser", async () => {
    const parser = vi.fn();
    const textSource = await extractDocument(file("brief.txt", "Enterprise agent brief", "text/plain"), { parseBinary: parser });
    const markdownSource = await extractDocument(file("brief.md", "# Agent brief", "text/markdown"), { parseBinary: parser });

    expect(textSource.accepted_text).toBe("Enterprise agent brief");
    expect(markdownSource.accepted_text).toBe("# Agent brief");
    expect(textSource.extraction_method).toBe("browser text reader");
    expect(parser).not.toHaveBeenCalled();
  });

  it("routes PDF and DOCX through the binary parser and keeps parser warnings", async () => {
    const parser = vi.fn().mockResolvedValue({
      text: "Page one\n\nPage two",
      method: "PDF.js worker",
      warnings: [{ code: "parser_warning", message: "One font could not be decoded." }],
    });

    const source = await extractDocument(file("architecture.pdf", "%PDF", "application/pdf"), { parseBinary: parser });

    expect(parser).toHaveBeenCalledWith(expect.objectContaining({ extension: "pdf", fileName: "architecture.pdf" }));
    expect(source.accepted_text).toBe("Page one\n\nPage two");
    expect(source.warnings[0].code).toBe("parser_warning");
  });

  it("rejects conflicting MIME types before reading the file", async () => {
    await expect(extractDocument(file("policy.pdf", "not a pdf", "text/plain"))).rejects.toMatchObject({ code: "mime_mismatch" } satisfies Partial<IntakeError>);
    await expect(extractDocument(file("policy.exe", "not supported", "application/octet-stream"))).rejects.toMatchObject({ code: "unsupported" });
  });

  it("rejects binary files whose contents do not match their declared format", async () => {
    const parser = vi.fn();
    await expect(
      extractDocument(file("spoofed.pdf", "not a PDF", "application/pdf"), { parseBinary: parser }),
    ).rejects.toMatchObject({ code: "mime_mismatch" });
    await expect(
      extractDocument(file("spoofed.docx", "not a ZIP package", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"), { parseBinary: parser }),
    ).rejects.toMatchObject({ code: "mime_mismatch" });
    expect(parser).not.toHaveBeenCalled();
  });

  it("enforces file count, size, source text, workspace text, and timeout limits", async () => {
    await expect(extractDocument(file("sixth.txt", "content", "text/plain"), { currentFileCount: 5 })).rejects.toMatchObject({ code: "file_count" });
    await expect(extractDocument(file("large.txt", "x".repeat(10 * 1024 * 1024 + 1), "text/plain"))).rejects.toMatchObject({ code: "file_size" });

    const long = await extractDocument(file("long.md", "x".repeat(50_010), "text/markdown"));
    expect(long.accepted_text).toHaveLength(50_000);
    expect(long.truncated).toBe(true);
    expect(long.warnings).toEqual(expect.arrayContaining([expect.objectContaining({ code: "truncated" })]));

    const bounded = await extractDocument(file("remaining.txt", "x".repeat(100), "text/plain"), { currentWorkspaceCharacters: 199_950 });
    expect(bounded.accepted_text).toHaveLength(50);
    expect(bounded.truncated).toBe(true);

    const never = new Promise<never>(() => undefined);
    await expect(
      extractDocument(file("slow.pdf", "%PDF", "application/pdf"), { parseBinary: () => never, timeoutMs: 5 }),
    ).rejects.toMatchObject({ code: "timeout" });
  });

  it("maps encrypted and image-only PDF results to actionable errors", async () => {
    await expect(
      extractDocument(file("locked.pdf", "%PDF", "application/pdf"), {
        parseBinary: async () => {
          throw new IntakeError("encrypted", "This PDF requires a password.");
        },
      }),
    ).rejects.toMatchObject({ code: "encrypted" });

    await expect(
      extractDocument(file("scan.pdf", "%PDF", "application/pdf"), {
        parseBinary: async () => ({ text: "", method: "PDF.js worker", warnings: [] }),
      }),
    ).rejects.toMatchObject({ code: "image_only" });
  });
});
