import { deploymentPosture } from "./deployment";
import { allowedEndpointHosts as runtimeAllowedEndpointHosts } from "./runtimeConfig";

const DEFAULT_TIMEOUT_MS = 15_000;
const DEFAULT_MAX_RESPONSE_BYTES = 1_000_000;

function defaultBaseOrigin(): string {
  return typeof window === "undefined" ? "https://loopos.local" : window.location.origin;
}

function isLocalHost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]";
}

export function assertAllowedEndpoint(endpoint: string, allowedHosts: string[], baseOrigin = defaultBaseOrigin()): URL {
  let url: URL;
  try {
    url = new URL(endpoint, baseOrigin);
  } catch {
    throw new Error("The configured endpoint URL is invalid.");
  }
  if (url.username || url.password) throw new Error("Endpoint URLs cannot contain credentials.");
  if (url.protocol !== "https:" && !(url.protocol === "http:" && isLocalHost(url.hostname))) {
    throw new Error("Remote enterprise endpoints must use HTTPS.");
  }
  const sameOrigin = url.origin === new URL(baseOrigin).origin;
  const normalizedAllowlist = allowedHosts.map((host) => host.trim().toLowerCase()).filter(Boolean);
  const allowlisted = normalizedAllowlist.includes(url.hostname.toLowerCase()) || normalizedAllowlist.includes(url.host.toLowerCase());
  if (!sameOrigin && !allowlisted) throw new Error(`Endpoint host ${url.host} is not in the outbound allowlist.`);
  return url;
}

export function allowedHostsForConfiguredEndpoint(endpoint: string): string[] {
  const runtimeHosts = runtimeAllowedEndpointHosts();
  if (runtimeHosts?.length) return runtimeHosts;
  if (deploymentPosture.mode === "enterprise") return deploymentPosture.allowedEndpointHosts;
  try {
    const url = new URL(endpoint, defaultBaseOrigin());
    return [url.hostname, url.host];
  } catch {
    return [];
  }
}

export interface SecureJsonRequestOptions {
  allowedHosts?: string[];
  baseOrigin?: string;
  fetchImpl?: typeof fetch;
  init?: RequestInit;
  maxResponseBytes?: number;
  timeoutMs?: number;
}

export async function secureJsonRequest<T>(endpoint: string, options: SecureJsonRequestOptions = {}): Promise<T> {
  const allowedHosts = options.allowedHosts ?? allowedHostsForConfiguredEndpoint(endpoint);
  const url = assertAllowedEndpoint(endpoint, allowedHosts, options.baseOrigin);
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  const maxResponseBytes = options.maxResponseBytes ?? DEFAULT_MAX_RESPONSE_BYTES;

  try {
    const response = await (options.fetchImpl ?? fetch)(url.toString(), {
      ...options.init,
      cache: "no-store",
      credentials: "omit",
      redirect: "error",
      referrerPolicy: "no-referrer",
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`Enterprise endpoint returned ${response.status}.`);
    const declaredLength = Number(response.headers?.get?.("content-length") ?? 0);
    if (declaredLength > maxResponseBytes) throw new Error("Enterprise endpoint response exceeded the response limit.");

    if (typeof response.text === "function") {
      const text = await response.text();
      if (new TextEncoder().encode(text).byteLength > maxResponseBytes) throw new Error("Enterprise endpoint response exceeded the response limit.");
      return JSON.parse(text) as T;
    }
    return await response.json() as T;
  } catch (error) {
    if (controller.signal.aborted) throw new Error(`Enterprise endpoint timed out after ${timeoutMs} ms.`);
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}
