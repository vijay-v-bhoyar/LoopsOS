import { describe, expect, it, vi } from "vitest";
import { IntakeError } from "./documentExtraction";
import { parseDocxBuffer, parsePdfBuffer } from "./binaryParsers";

describe("binary document parsers", () => {
  it("preserves PDF page order and readable item order", async () => {
    const getPage = vi.fn(async (pageNumber: number) => ({
      getTextContent: async () => ({
        items: pageNumber === 1 ? [{ str: "Page" }, { str: "one" }] : [{ str: "Page" }, { str: "two" }],
      }),
    }));
    const loadPdf = vi.fn(async () => ({
      GlobalWorkerOptions: { workerSrc: "" },
      getDocument: () => ({ promise: Promise.resolve({ numPages: 2, getPage }) }),
    }));

    const result = await parsePdfBuffer(new ArrayBuffer(8), loadPdf);

    expect(result.text).toBe("Page one\n\nPage two");
    expect(getPage.mock.calls.map(([page]) => page)).toEqual([1, 2]);
    expect(result.method).toBe("PDF.js worker");
  });

  it("maps PDF password failures to an encrypted intake error", async () => {
    const loadPdf = vi.fn(async () => ({
      GlobalWorkerOptions: { workerSrc: "" },
      getDocument: () => ({ promise: Promise.reject({ name: "PasswordException" }) }),
    }));

    await expect(parsePdfBuffer(new ArrayBuffer(8), loadPdf)).rejects.toMatchObject({ code: "encrypted" } satisfies Partial<IntakeError>);
  });

  it("maps unreadable binary documents to the corrupt document state", async () => {
    await expect(
      parsePdfBuffer(new ArrayBuffer(0), async () => {
        throw new Error("invalid cross-reference table");
      }),
    ).rejects.toMatchObject({ code: "corrupt" });

    await expect(
      parseDocxBuffer(new ArrayBuffer(0), async () => {
        throw new Error("invalid zip package");
      }),
    ).rejects.toMatchObject({ code: "corrupt" });
  });

  it("extracts DOCX raw text and maps parser messages to warnings", async () => {
    const extractRawText = vi.fn(async () => ({
      value: "Heading\n\nParagraph",
      messages: [{ type: "warning", message: "Unsupported embedded object." }],
    }));
    const result = await parseDocxBuffer(new ArrayBuffer(8), async () => ({ extractRawText }));

    expect(extractRawText).toHaveBeenCalledWith({ arrayBuffer: expect.any(ArrayBuffer) });
    expect(result.text).toBe("Heading\n\nParagraph");
    expect(result.warnings).toEqual([{ code: "parser_warning", message: "Unsupported embedded object." }]);
    expect(result.method).toBe("Mammoth DOCX worker");
  });
});
