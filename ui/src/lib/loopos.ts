import data from "../data/loopos-data.json";
import type { LoopDetail, LoopOSData } from "../types";

export const looposData = data as unknown as LoopOSData;

export const loopById = new Map(looposData.loops.map((loop) => [loop.loop_id, loop]));
export const loopByName = new Map(looposData.loops.map((loop) => [loop.name, loop]));

export function getLoop(loopId: string): LoopDetail {
  const loop = loopById.get(loopId);
  if (!loop) {
    throw new Error(`Unknown loop id: ${loopId}`);
  }
  return loop;
}

export function categoryRiskSummary(categoryName: string): string {
  const category = looposData.categories.find((item) => item.name === categoryName);
  if (!category) return "No category record";
  return Object.entries(category.risk_tiers)
    .map(([tier, count]) => `${tier}: ${count}`)
    .join(", ");
}

export function compactList(values: string[], limit = 3): string {
  if (!values.length) return "None recorded";
  if (values.length <= limit) return values.join(", ");
  return `${values.slice(0, limit).join(", ")} +${values.length - limit}`;
}

export function riskRank(tier: string): number {
  return Number(tier.replace("R", "")) || 0;
}
