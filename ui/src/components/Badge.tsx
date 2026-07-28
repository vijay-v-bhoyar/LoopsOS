import type { ReactNode } from "react";

type Tone = "neutral" | "brand" | "success" | "warning" | "danger";

const toneClass: Record<Tone, string> = {
  neutral: "bg-bg2 text-fg2 border-border2",
  brand: "bg-brandSubtle text-brandStrong border-border2",
  success: "bg-successBg text-success border-border2",
  warning: "bg-warningBg text-warning border-border2",
  danger: "bg-dangerBg text-danger border-border2",
};

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: Tone }) {
  return (
    <span className={`inline-flex items-center rounded-control border px-2 py-0.5 text-xs font-semibold ${toneClass[tone]}`}>
      {children}
    </span>
  );
}

export function riskTone(tier: string): Tone {
  if (tier === "R4") return "danger";
  if (tier === "R3") return "warning";
  if (tier === "R2") return "brand";
  return "neutral";
}
