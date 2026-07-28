import type { ExtractionWarning, UseCaseSource } from "../../types";
import { nowIso, uid } from "../../lib/workspaceStore";

export const INTAKE_LIMITS = {
  maxFiles: 5,
  maxFileBytes: 10 * 1024 * 1024,
  maxSourceCharacters: 50_000,
  maxWorkspaceCharacters: 200_000,
  extractionTimeoutMs: 15_000,
} as const;

type BinaryExtension = "pdf" | "docx";
type SupportedExtension = BinaryExtension | "txt" | "md";

export interface BinaryParseRequest {
  fileName: string;
  extension: BinaryExtension;
  mimeType: string;
  buffer: ArrayBuffer;
}

export interface BinaryParseResult {
  text: string;
  method: string;
  warnings: ExtractionWarning[];
}

export interface DocumentExtractionOptions {
  currentFileCount?: number;
  currentWorkspaceCharacters?: number;
  timeoutMs?: number;
  parseBinary?: (request: BinaryParseRequest) => Promise<BinaryParseResult>;
}

const MIME_BY_EXTENSION: Record<SupportedExtension, string[]> = {
  pdf: ["application/pdf"],
  docx: ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/octet-stream"],
  txt: ["text/plain"],
  md: ["text/markdown", "text/plain"],
};

export class IntakeError extends Error {
  constructor(public readonly code: string, message: string) {
    super(message);
    this.name = "IntakeError";
  }
}

function extensionOf(fileName: string): SupportedExtension | "" {
  const match = fileName.toLowerCase().match(/\.([a-z0-9]+)$/);
  const extension = match?.[1] ?? "";
  return extension === "pdf" || extension === "docx" || extension === "txt" || extension === "md" ? extension : "";
}

function validateFile(file: File, currentFileCount: number): SupportedExtension {
  if (currentFileCount >= INTAKE_LIMITS.maxFiles) {
    throw new IntakeError("file_count", `A workspace can retain up to ${INTAKE_LIMITS.maxFiles} input sources.`);
  }
  if (file.size > INTAKE_LIMITS.maxFileBytes) {
    throw new IntakeError("file_size", "Files must be 10 MB or smaller.");
  }
  const extension = extensionOf(file.name);
  if (!extension) {
    throw new IntakeError("unsupported", "Use a PDF, DOCX, TXT, or Markdown file.");
  }
  if (file.type && !MIME_BY_EXTENSION[extension].includes(file.type.toLowerCase())) {
    throw new IntakeError("mime_mismatch", `The declared file type does not match .${extension}.`);
  }
  return extension;
}

async function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new IntakeError("timeout", "Document extraction exceeded the time limit.")), timeoutMs);
  });
  try {
    return await Promise.race([promise, timeout]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

function readWithFileReader<T>(file: File, mode: "text" | "arrayBuffer"): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new IntakeError("file_read", "The browser could not read this file."));
    reader.onload = () => resolve(reader.result as T);
    if (mode === "text") reader.readAsText(file);
    else reader.readAsArrayBuffer(file);
  });
}

function readText(file: File): Promise<string> {
  return typeof file.text === "function" ? file.text() : readWithFileReader<string>(file, "text");
}

function readArrayBuffer(file: File): Promise<ArrayBuffer> {
  return typeof file.arrayBuffer === "function" ? file.arrayBuffer() : readWithFileReader<ArrayBuffer>(file, "arrayBuffer");
}

function hasBinarySignature(extension: BinaryExtension, buffer: ArrayBuffer): boolean {
  const bytes = new Uint8Array(buffer.slice(0, 1_024));
  if (extension === "pdf") {
    const signature = [0x25, 0x50, 0x44, 0x46];
    return bytes.some((byte, index) => signature.every((expected, offset) => bytes[index + offset] === expected));
  }
  return bytes[0] === 0x50 && bytes[1] === 0x4b && (
    (bytes[2] === 0x03 && bytes[3] === 0x04)
    || (bytes[2] === 0x05 && bytes[3] === 0x06)
    || (bytes[2] === 0x07 && bytes[3] === 0x08)
  );
}

export async function parseBinaryWithWorker(request: BinaryParseRequest): Promise<BinaryParseResult> {
  if (typeof Worker === "undefined") {
    throw new IntakeError("worker_unavailable", "This browser cannot start the document extraction worker.");
  }
  const worker = new Worker(new URL("./documentExtraction.worker.ts", import.meta.url), { type: "module" });
  return new Promise<BinaryParseResult>((resolve, reject) => {
    const timer = setTimeout(() => {
      worker.terminate();
      reject(new IntakeError("timeout", "Document extraction exceeded the time limit."));
    }, INTAKE_LIMITS.extractionTimeoutMs);
    worker.onmessage = (event: MessageEvent<{ ok: boolean; result?: BinaryParseResult; error?: { code: string; message: string } }>) => {
      clearTimeout(timer);
      worker.terminate();
      if (event.data.ok && event.data.result) resolve(event.data.result);
      else reject(new IntakeError(event.data.error?.code ?? "parser_error", event.data.error?.message ?? "Document extraction failed."));
    };
    worker.onerror = () => {
      clearTimeout(timer);
      worker.terminate();
      reject(new IntakeError("parser_error", "The document worker stopped unexpectedly."));
    };
    worker.postMessage(request, [request.buffer]);
  });
}

export async function extractDocument(file: File, options: DocumentExtractionOptions = {}): Promise<UseCaseSource> {
  const extension = validateFile(file, options.currentFileCount ?? 0);
  const workspaceRemaining = INTAKE_LIMITS.maxWorkspaceCharacters - (options.currentWorkspaceCharacters ?? 0);
  if (workspaceRemaining <= 0) {
    throw new IntakeError("workspace_text", "The workspace input-source text limit has been reached.");
  }

  let result: BinaryParseResult;
  if (extension === "txt" || extension === "md") {
    result = { text: await readText(file), method: "browser text reader", warnings: [] };
  } else {
    const buffer = await readArrayBuffer(file);
    if (!hasBinarySignature(extension, buffer)) {
      throw new IntakeError("mime_mismatch", `The file contents do not match the .${extension} format.`);
    }
    const request: BinaryParseRequest = {
      fileName: file.name,
      extension,
      mimeType: file.type,
      buffer,
    };
    result = await withTimeout((options.parseBinary ?? parseBinaryWithWorker)(request), options.timeoutMs ?? INTAKE_LIMITS.extractionTimeoutMs);
  }

  const normalized = result.text.replace(/\r\n/g, "\n").trim();
  if (!normalized) {
    throw new IntakeError(extension === "pdf" ? "image_only" : "empty_document", extension === "pdf" ? "No selectable text was found. OCR is not included." : "No readable text was found.");
  }
  const retainedCharacters = Math.min(INTAKE_LIMITS.maxSourceCharacters, workspaceRemaining);
  const truncated = normalized.length > retainedCharacters;
  const acceptedText = normalized.slice(0, retainedCharacters);
  const warnings = [...result.warnings];
  if (truncated) {
    warnings.push({ code: "truncated", message: `Text was limited to ${retainedCharacters.toLocaleString()} characters.` });
  }

  return {
    source_id: uid("source"),
    kind: "document",
    label: file.name,
    mime_type: file.type || MIME_BY_EXTENSION[extension][0],
    status: "ready_for_review",
    accepted_text: acceptedText,
    extraction_method: result.method,
    character_count: acceptedText.length,
    created_at: nowIso(),
    warnings,
    truncated,
  };
}
