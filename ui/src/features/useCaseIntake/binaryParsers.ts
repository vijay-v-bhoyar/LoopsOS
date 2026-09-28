import type { BinaryParseResult } from "./documentExtraction";
import { IntakeError } from "./documentExtraction";
import pdfWorkerUrl from "pdfjs-dist/legacy/build/pdf.worker.mjs?url";

interface PdfTextItem {
  str?: string;
}

interface PdfDocumentLike {
  numPages: number;
  getPage(pageNumber: number): Promise<{ getTextContent(): Promise<{ items: PdfTextItem[] }> }>;
}

interface PdfModuleLike {
  getDocument(options: { data: ArrayBuffer; worker?: unknown }): { promise: Promise<PdfDocumentLike> };
  GlobalWorkerOptions: { workerSrc: string };
}

interface MammothModuleLike {
  extractRawText(options: { arrayBuffer: ArrayBuffer }): Promise<{
    value: string;
    messages: Array<{ type?: string; message: string }>;
  }>;
}

type PdfLoader = () => Promise<PdfModuleLike>;
type MammothLoader = () => Promise<MammothModuleLike>;

async function loadPdfJs(): Promise<PdfModuleLike> {
  return (await import("pdfjs-dist/legacy/build/pdf.mjs")) as unknown as PdfModuleLike;
}

async function loadMammoth(): Promise<MammothModuleLike> {
  const imported = (await import("mammoth/mammoth.browser")) as unknown as { default?: MammothModuleLike } & MammothModuleLike;
  return imported.default ?? imported;
}

export async function parsePdfBuffer(buffer: ArrayBuffer, loader: PdfLoader = loadPdfJs): Promise<BinaryParseResult> {
  try {
    const pdfjs = await loader();
    // PDF.js 6 requires an explicit worker source in browser and nested-worker contexts.
    pdfjs.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;
    const document = await pdfjs.getDocument({ data: buffer }).promise;
    const pages: string[] = [];
    for (let pageNumber = 1; pageNumber <= document.numPages; pageNumber += 1) {
      const page = await document.getPage(pageNumber);
      const content = await page.getTextContent();
      pages.push(content.items.map((item) => item.str?.trim()).filter(Boolean).join(" "));
    }
    return { text: pages.join("\n\n"), method: "PDF.js worker", warnings: [] };
  } catch (error) {
    if (error instanceof IntakeError) throw error;
    const name = typeof error === "object" && error && "name" in error ? String(error.name) : "";
    if (name === "PasswordException") throw new IntakeError("encrypted", "This PDF requires a password and cannot be extracted locally.");
    throw new IntakeError("corrupt", "The PDF appears corrupt or uses an unsupported structure.");
  }
}

export async function parseDocxBuffer(buffer: ArrayBuffer, loader: MammothLoader = loadMammoth): Promise<BinaryParseResult> {
  try {
    const mammoth = await loader();
    const result = await mammoth.extractRawText({ arrayBuffer: buffer });
    return {
      text: result.value,
      method: "Mammoth DOCX worker",
      warnings: result.messages.map((message) => ({ code: "parser_warning", message: message.message })),
    };
  } catch (error) {
    if (error instanceof IntakeError) throw error;
    throw new IntakeError("corrupt", "The DOCX file appears corrupt or uses an unsupported structure.");
  }
}
