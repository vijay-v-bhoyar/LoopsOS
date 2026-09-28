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

export function isLocalLlmFixtureEndpoint(endpoint: string): boolean {
  return import.meta.env.DEV && deploymentPosture.mode === "evaluation"
    && typeof window !== "undefined" && ["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname)
    && ["/api/mock-llm-questions", "/api/mock-field-enhancement"].includes(endpoint);
}

// Trust configuration is compiled deployment input; never accept keys from Window or a model response.
export function llmAttestationContracts(): unknown {
  try {
    const contracts: unknown = JSON.parse(import.meta.env.VITE_LOOPOS_LLM_ATTESTATION_CONTRACTS ?? "[]");
    if (Array.isArray(contracts) && contracts.some((pin) => pin?.fixture_only === true)) {
      if (contracts.some((pin) => pin?.fixture_only === true && !isLocalLlmFixtureEndpoint(pin.endpoint))) return [];
    }
    return contracts;
  } catch {
    return [];
  }
}

export function transcriptionEndpoint(): string | undefined {
  return browserOverride("transcriptionEndpoint") ?? (import.meta.env.VITE_LOOPOS_TRANSCRIPTION_ENDPOINT as string | undefined);
}

export function llmTimeoutMs(): number | undefined {
  const configured = Number(import.meta.env.VITE_LOOPOS_LLM_TIMEOUT_MS);
  const override = deploymentPosture.mode !== "enterprise" && typeof window !== "undefined"
    ? window.__LOOPOS_RUNTIME_CONFIG__?.llmTimeoutMs : undefined;
  const value = override ?? configured;
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? Math.min(value, 30_000) : 15_000;
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
