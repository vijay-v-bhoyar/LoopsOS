import { Copy, Download } from "lucide-react";
import { Button } from "../components/Button";
import { Card, SectionHeader } from "../components/Card";
import { HelpPopover, InlineNote } from "../components/Help";
import type { EnterpriseActionPlan } from "../types";

export function ImplementationPlan({ plan }: { plan: EnterpriseActionPlan | null }) {
  if (!plan) {
    return (
      <Card>
        <SectionHeader title="Implementation Plan Export" description="Use the Use Case Advisor to generate a read-only enterprise action plan." />
        <InlineNote>Generated plans appear here after a use case is evaluated.</InlineNote>
      </Card>
    );
  }

  const copy = async () => {
    await navigator.clipboard.writeText(plan.exportMarkdown);
  };

  const download = () => {
    const blob = new Blob([plan.exportMarkdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${plan.title.toLowerCase().replace(/[^a-z0-9]+/g, "-") || "loopos-action-plan"}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
      <Card>
        <SectionHeader title="Enterprise Action Plan" description={plan.summary} action={<HelpPopover helpKey="export" />} />
        <div className="mb-4 flex flex-wrap gap-2">
          <Button onClick={copy}>
            <Copy className="h-4 w-4" aria-hidden="true" />
            Copy Markdown
          </Button>
          <Button variant="primary" onClick={download}>
            <Download className="h-4 w-4" aria-hidden="true" />
            Download
          </Button>
        </div>
        <div className="space-y-2">
          {plan.first30Days.map((item) => (
            <div key={item} className="rounded-panel border border-border2 bg-bg2 p-3 text-sm text-fg2">
              {item}
            </div>
          ))}
        </div>
      </Card>
      <Card>
        <SectionHeader title="Markdown Preview" description="This is deterministic output from the current recommendation and validation state." />
        <pre className="max-h-screen overflow-auto rounded-panel border border-border2 bg-bg2 p-4 text-sm text-fg2 whitespace-pre-wrap">{plan.exportMarkdown}</pre>
      </Card>
    </div>
  );
}
