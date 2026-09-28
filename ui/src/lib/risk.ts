export function riskRank(tier: string): number {
  return Number(tier.replace("R", "")) || 0;
}
