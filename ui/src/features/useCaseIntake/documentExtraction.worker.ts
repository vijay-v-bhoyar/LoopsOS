/// <reference lib="webworker" />

import { parseDocxBuffer, parsePdfBuffer } from "./binaryParsers";
import type { BinaryParseRequest } from "./documentExtraction";
import { IntakeError } from "./documentExtraction";

const workerScope: DedicatedWorkerGlobalScope = self as unknown as DedicatedWorkerGlobalScope;

workerScope.onmessage = async (event: MessageEvent<BinaryParseRequest>) => {
  try {
    const result = event.data.extension === "pdf" ? await parsePdfBuffer(event.data.buffer) : await parseDocxBuffer(event.data.buffer);
    workerScope.postMessage({ ok: true, result });
  } catch (error) {
    const intakeError = error instanceof IntakeError ? error : new IntakeError("parser_error", "Document extraction failed.");
    workerScope.postMessage({ ok: false, error: { code: intakeError.code, message: intakeError.message } });
  }
};

export {};
