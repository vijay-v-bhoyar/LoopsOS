import { deploymentPosture, isUnsafeAuthorityHostname } from "./deployment";
import { allowedEndpointHosts as runtimeAllowedEndpointHosts } from "./runtimeConfig";

const DEFAULT_TIMEOUT_MS = 15_000;
const DEFAULT_MAX_RESPONSE_BYTES = 1_000_000;
const RESPONSE_LIMIT_MESSAGE = "Enterprise endpoint response exceeded the response limit.";

function requestAbortError(): DOMException {
  return new DOMException("The request was aborted.", "AbortError");
}

async function awaitWithAbort<T>(operation: Promise<T>, signal: AbortSignal): Promise<T> {
  if (signal.aborted) throw requestAbortError();
  let onAbort: (() => void) | undefined;
  const aborted = new Promise<never>((_resolve, reject) => {
    onAbort = () => reject(requestAbortError());
    signal.addEventListener("abort", onAbort, { once: true });
  });
  try {
    return await Promise.race([operation, aborted]);
  } finally {
    if (onAbort) signal.removeEventListener("abort", onAbort);
  }
}

function defaultBaseOrigin(): string {
  return typeof window === "undefined" ? "https://loopos.local" : window.location.origin;
}

function isLocalHost(hostname: string): boolean {
  const normalized = hostname.replace(/^\[|\]$/g, "").toLowerCase();
  return normalized === "localhost" || normalized === "127.0.0.1" || normalized === "::1";
}

export function assertAllowedEndpoint(endpoint: string, allowedHosts: string[], baseOrigin = defaultBaseOrigin()): URL {
  let url: URL;
  try {
    url = new URL(endpoint, baseOrigin);
  } catch {
    throw new Error("The configured endpoint URL is invalid.");
  }
  if (url.username || url.password) throw new Error("Endpoint URLs cannot contain credentials.");
  if (endpoint.includes("\\") || endpoint.includes("?") || endpoint.includes("#") || url.search || url.hash) {
    throw new Error("Endpoint URLs cannot contain query strings, fragments, or backslashes.");
  }
  if (url.protocol !== "https:" && !(url.protocol === "http:" && isLocalHost(url.hostname))) {
    throw new Error("Remote enterprise endpoints must use HTTPS.");
  }
  const localHttpEndpoint = url.protocol === "http:" && isLocalHost(url.hostname);
  if (!localHttpEndpoint && isUnsafeAuthorityHostname(url.hostname)) {
    throw new Error("Endpoint hosts must be global, non-local addresses.");
  }
  const sameOrigin = url.origin === new URL(baseOrigin).origin;
  const normalizedAllowlist = allowedHosts.map((host) => host.trim().toLowerCase()).filter(Boolean);
  const allowlisted = normalizedAllowlist.includes(url.hostname.toLowerCase()) || normalizedAllowlist.includes(url.host.toLowerCase());
  if (!sameOrigin && !allowlisted) throw new Error(`Endpoint host ${url.host} is not in the outbound allowlist.`);
  return url;
}

export function allowedHostsForConfiguredEndpoint(endpoint: string): string[] {
  if (deploymentPosture.mode === "enterprise") return deploymentPosture.allowedEndpointHosts;
  const runtimeHosts = runtimeAllowedEndpointHosts();
  if (runtimeHosts?.length) return runtimeHosts;
  try {
    const url = new URL(endpoint, defaultBaseOrigin());
    return [url.hostname, url.host];
  } catch {
    return [];
  }
}

export interface SecureJsonRequestOptions<T = unknown> {
  allowedHosts?: string[];
  baseOrigin?: string;
  fetchImpl?: typeof fetch;
  init?: RequestInit;
  maxResponseBytes?: number;
  timeoutMs?: number;
  validate?: (value: unknown) => value is T;
  invalidResponseMessage?: string;
}

async function readResponseText(response: Response, maxResponseBytes: number, signal: AbortSignal): Promise<string> {
  const reader = response.body?.getReader();
  if (!reader) {
    const text = await awaitWithAbort(response.text(), signal);
    if (new TextEncoder().encode(text).byteLength > maxResponseBytes) throw new Error(RESPONSE_LIMIT_MESSAGE);
    return text;
  }

  const decoder = new TextDecoder();
  const chunks: string[] = [];
  let totalBytes = 0;
  try {
    while (true) {
      const { done, value } = await awaitWithAbort(reader.read(), signal);
      if (done) {
        chunks.push(decoder.decode());
        return chunks.join("");
      }
      totalBytes += value.byteLength;
      if (totalBytes > maxResponseBytes) {
        await reader.cancel().catch(() => undefined);
        throw new Error(RESPONSE_LIMIT_MESSAGE);
      }
      chunks.push(decoder.decode(value, { stream: true }));
    }
  } catch (error) {
    if (signal.aborted) void reader.cancel().catch(() => undefined);
    throw error;
  } finally {
    reader.releaseLock();
  }
}

export async function secureJsonRequest<T>(endpoint: string, options: SecureJsonRequestOptions<T> = {}): Promise<T> {
  const allowedHosts = options.allowedHosts ?? allowedHostsForConfiguredEndpoint(endpoint);
  const url = assertAllowedEndpoint(endpoint, allowedHosts, options.baseOrigin);
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  const maxResponseBytes = options.maxResponseBytes ?? DEFAULT_MAX_RESPONSE_BYTES;

  try {
    const response = await awaitWithAbort((options.fetchImpl ?? fetch)(url.toString(), {
      ...options.init,
      cache: "no-store",
      credentials: "omit",
      redirect: "error",
      referrerPolicy: "no-referrer",
      signal: controller.signal,
    }), controller.signal);
    if (!response.ok) throw new Error(`Enterprise endpoint returned ${response.status}.`);
    const declaredLength = Number(response.headers?.get?.("content-length") ?? 0);
    if (declaredLength > maxResponseBytes) throw new Error(RESPONSE_LIMIT_MESSAGE);

    if (typeof response.text === "function") {
      const text = await readResponseText(response, maxResponseBytes, controller.signal);
      const payload: unknown = JSON.parse(text);
      if (options.validate && !options.validate(payload)) {
        throw new Error(options.invalidResponseMessage ?? "Enterprise endpoint returned an invalid JSON response.");
      }
      return payload as T;
    }
    const payload: unknown = await awaitWithAbort(response.json(), controller.signal);
    if (options.validate && !options.validate(payload)) {
      throw new Error(options.invalidResponseMessage ?? "Enterprise endpoint returned an invalid JSON response.");
    }
    return payload as T;
  } catch (error) {
    if (controller.signal.aborted) throw new Error(`Enterprise endpoint timed out after ${timeoutMs} ms.`);
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}
