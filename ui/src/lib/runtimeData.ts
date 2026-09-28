import catalogUrl from "../data/loopos-data.json?url";
import type { LoopOSData } from "../types";

type CatalogFetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

function isLoopOSData(value: unknown): value is LoopOSData {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<LoopOSData>;
  return Array.isArray(candidate.loops)
    && Array.isArray(candidate.categories)
    && Array.isArray(candidate.controls)
    && typeof candidate.stats === "object"
    && candidate.stats !== null;
}

export async function loadLooposData(fetcher: CatalogFetcher = fetch): Promise<LoopOSData> {
  const response = await fetcher(catalogUrl, { headers: { accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`The LoopOS catalog could not be loaded (HTTP ${response.status}).`);
  }
  const payload: unknown = await response.json();
  if (!isLoopOSData(payload)) {
    throw new Error("The LoopOS catalog response is invalid.");
  }
  return payload;
}
