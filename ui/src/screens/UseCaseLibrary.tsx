import { ExternalLink } from "lucide-react";
import { Badge } from "../components/Badge";
import { Card, SectionHeader } from "../components/Card";
import type { LoopOSData, UseCaseRecord } from "../types";

export function UseCaseLibrary({
  data,
  query,
  onUseCaseSelect,
}: {
  data: LoopOSData;
  query: string;
  onUseCaseSelect: (record: UseCaseRecord) => void;
}) {
  const normalized = query.toLowerCase();
  const useCases = data.use_cases
    .filter((item) => !normalized || `${item.title} ${item.summary}`.toLowerCase().includes(normalized))
    .sort((a, b) => a.rank - b.rank);

  return (
    <Card>
      <SectionHeader
        title="Enterprise Use Case Library"
        description="Broad and compound use cases ranked by effort saving and moat value, linked back to LoopOS source docs."
      />
      {useCases.length ? (
        <div className="grid gap-3 lg:grid-cols-2">
          {useCases.map((item) => (
            <button key={item.use_case_id} onClick={() => onUseCaseSelect(item)} className="interactive-surface p-4 text-left hover:border-brand">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <Badge tone={item.family === "moat" ? "brand" : "neutral"}>{item.family}</Badge>
                <Badge>Rank {item.rank}</Badge>
                {item.loop_names.length ? <Badge>{item.loop_names.length} named loops</Badge> : null}
              </div>
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-base font-semibold text-fg1">{item.title}</h3>
                <ExternalLink className="h-4 w-4 text-fg3" aria-hidden="true" />
              </div>
              <p className="mt-2 text-sm text-fg2">{item.summary}</p>
              <div className="mt-3 text-xs text-fg3">Source: {item.source}</div>
            </button>
          ))}
        </div>
      ) : (
        <div role="status" className="rounded-panel border border-dashed border-border2 bg-bg2 p-6 text-sm text-fg2">
          No use cases match the current search. Clear the search and try again.
        </div>
      )}
    </Card>
  );
}
