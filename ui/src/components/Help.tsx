import * as Popover from "@radix-ui/react-popover";
import * as Tooltip from "@radix-ui/react-tooltip";
import { HelpCircle, Info } from "lucide-react";
import type { ReactNode } from "react";

const HELP_COPY = {
  risk: {
    short: "Risk tier",
    rich: "LoopOS risk tiers control proof depth and handoff expectations. R3 and R4 work must not be treated like routine automation.",
  },
  readiness: {
    short: "Readiness",
    rich: "Use-case readiness is separate from corpus validation. The framework can be valid while a specific enterprise use case still lacks owners, evidence, or controls.",
  },
  why: {
    short: "Why this loop?",
    rich: "Recommendations show recorded match factors from loop metadata, playbooks, risk, and controls. The UI does not invent hidden confidence scores.",
  },
  evidence: {
    short: "Evidence",
    rich: "Evidence gaps mean an enterprise must bind the loop to real systems such as source control, CI, observability, GRC, data catalogs, or model evaluation stores.",
  },
  export: {
    short: "Export",
    rich: "Exports are read-only action plans. They do not approve changes, promote loops, or mutate LoopOS governance state.",
  },
  multimodalIntake: {
    short: "Multimodal intake",
    rich: "Typed text, extracted document text, and reviewed transcripts can propose use-case fields. Raw files and audio are not retained; optional enterprise services are called only after an explicit action.",
  },
} as const;

export type HelpKey = keyof typeof HELP_COPY;

export function HelpTooltip({ helpKey }: { helpKey: HelpKey }) {
  const copy = HELP_COPY[helpKey];
  return (
    <Tooltip.Provider delayDuration={250}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <button className="inline-flex min-h-8 min-w-8 items-center justify-center rounded-control text-fg3 hover:bg-bg2" aria-label={copy.short}>
            <HelpCircle className="h-4 w-4" aria-hidden="true" />
          </button>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content className="surface max-w-xs px-3 py-2 text-sm text-fg2" sideOffset={6}>
            {copy.short}
            <Tooltip.Arrow className="fill-bg1" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}

export function HelpPopover({ helpKey }: { helpKey: HelpKey }) {
  const copy = HELP_COPY[helpKey];
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button className="inline-flex min-h-8 min-w-8 items-center justify-center rounded-control text-fg3 hover:bg-bg2" aria-label={`Help: ${copy.short}`}>
          <Info className="h-4 w-4" aria-hidden="true" />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="surface z-50 max-w-sm p-4 text-sm text-fg2" sideOffset={8} align="start">
          <div className="mb-1 font-semibold text-fg1">{copy.short}</div>
          <p>{copy.rich}</p>
          <Popover.Close className="mt-3 rounded-control border border-border1 px-2 py-1 text-xs font-semibold text-fg2 hover:bg-bg2">
            Close
          </Popover.Close>
          <Popover.Arrow className="fill-bg1" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function InlineNote({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warning" | "critical" }) {
  const toneClass = tone === "critical" ? "bg-dangerBg text-danger" : tone === "warning" ? "bg-warningBg text-warning" : "bg-infoBg text-fg2";
  return <div className={`rounded-panel border border-border2 px-3 py-2 text-sm ${toneClass}`}>{children}</div>;
}
