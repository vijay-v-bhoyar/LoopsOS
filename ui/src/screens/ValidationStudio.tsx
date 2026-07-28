import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import { Badge } from "../components/Badge";
import { Card, SectionHeader } from "../components/Card";
import { HelpPopover, InlineNote } from "../components/Help";
import type { LoopOSData, UseCaseInput, UseCaseValidationResult } from "../types";

export function ValidationStudio({
  data,
  input,
  validation,
}: {
  data: LoopOSData;
  input: UseCaseInput;
  validation: UseCaseValidationResult;
}) {
  return (
    <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <Card>
        <SectionHeader title="Validation Studio" description="Separate corpus validity from this use case's enterprise readiness." action={<HelpPopover helpKey="readiness" />} />
        <div className="space-y-3">
          <ValidationMetric label="Corpus validator" value={validation.corpusStatus} tone={validation.corpusStatus === "PASS" ? "success" : "warning"} />
          <ValidationMetric label="Use-case readiness" value={validation.readiness} tone={validation.readiness === "Blocked" ? "danger" : validation.readiness === "Governance Review" ? "warning" : "brand"} />
          <ValidationMetric label="Audit blockers" value={String(data.validation.audit.blockers)} tone={data.validation.audit.blockers === 0 ? "success" : "danger"} />
          <ValidationMetric label="Activation gaps" value={String(data.stats.known_activation_gaps)} tone="warning" />
        </div>
        <div className="mt-4">
          <InlineNote tone="warning">
            The framework is valid, but enterprise activation still requires named owners, authoritative evidence locations, metric targets, probes, and real fixtures.
          </InlineNote>
        </div>
      </Card>

      <Card>
        <SectionHeader title={input.title || "Current use case"} description={input.businessOutcome || "No business outcome entered."} />
        <div className="space-y-3">
          {validation.findings.map((finding) => (
            <div key={`${finding.label}-${finding.detail}`} className="rounded-panel border border-border2 bg-bg1 p-3">
              <div className="flex items-center gap-2">
                {finding.status === "pass" ? (
                  <CheckCircle2 className="h-4 w-4 text-success" aria-hidden="true" />
                ) : finding.status === "gap" ? (
                  <AlertTriangle className="h-4 w-4 text-danger" aria-hidden="true" />
                ) : (
                  <Info className="h-4 w-4 text-warning" aria-hidden="true" />
                )}
                <span className="font-semibold text-fg1">{finding.label}</span>
                <Badge tone={finding.status === "pass" ? "success" : finding.status === "gap" ? "danger" : "warning"}>{finding.status}</Badge>
              </div>
              <p className="mt-2 text-sm text-fg2">{finding.detail}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function ValidationMetric({ label, value, tone }: { label: string; value: string; tone: "success" | "warning" | "danger" | "brand" }) {
  return (
    <div className="flex items-center justify-between rounded-panel border border-border2 bg-bg2 p-3">
      <span className="text-sm font-semibold text-fg1">{label}</span>
      <Badge tone={tone}>{value}</Badge>
    </div>
  );
}
