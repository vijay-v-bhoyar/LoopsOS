import { deploymentPosture } from "./deployment";

declare global {
  interface Window {
    __LOOPOS_RUNTIME_CONFIG__?: {
      llmEndpoint?: string;
      transcriptionEndpoint?: string;
      llmTimeoutMs?: number;
      allowedEndpointHosts?: string[];
      crashAuthenticatedView?: string;
    };
  }
}

function browserOverride<K extends "llmEndpoint" | "transcriptionEndpoint">(key: K): string | undefined {
  if (typeof window === "undefined" || deploymentPosture.mode === "enterprise") return undefined;
  const value = window.__LOOPOS_RUNTIME_CONFIG__?.[key];
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

export function llmEndpoint(): string | undefined {
  return browserOverride("llmEndpoint") ?? (import.meta.env.VITE_LOOPOS_LLM_ENDPOINT as string | undefined);
}

export function transcriptionEndpoint(): string | undefined {
  return browserOverride("transcriptionEndpoint") ?? (import.meta.env.VITE_LOOPOS_TRANSCRIPTION_ENDPOINT as string | undefined);
}

export function llmTimeoutMs(): number | undefined {
  if (typeof window === "undefined") return undefined;
  const value = window.__LOOPOS_RUNTIME_CONFIG__?.llmTimeoutMs;
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : undefined;
}

export function allowedEndpointHosts(): string[] | undefined {
  if (typeof window === "undefined" || deploymentPosture.mode === "enterprise") return undefined;
  const value = window.__LOOPOS_RUNTIME_CONFIG__?.allowedEndpointHosts;
  return Array.isArray(value) ? value.filter((host): host is string => typeof host === "string" && host.trim().length > 0) : undefined;
}

export function consumeCrashAuthenticatedView(view: string, authenticated: boolean): boolean {
  if (typeof window === "undefined" || !authenticated) return false;
  const configured = window.__LOOPOS_RUNTIME_CONFIG__?.crashAuthenticatedView;
  if (configured !== view) return false;
  if (window.__LOOPOS_RUNTIME_CONFIG__) delete window.__LOOPOS_RUNTIME_CONFIG__.crashAuthenticatedView;
  return true;
}
