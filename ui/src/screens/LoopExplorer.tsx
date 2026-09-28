import { Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge, riskTone } from "../components/Badge";
import { Card, SectionHeader } from "../components/Card";
import { HelpPopover } from "../components/Help";
import { LoopDetailPanel } from "../components/LoopDetailPanel";
import type { LoopDetail, LoopOSData } from "../types";

export function LoopExplorer({
  data,
  globalQuery,
  selectedLoop,
  onSelectLoop,
}: {
  data: LoopOSData;
  globalQuery: string;
  selectedLoop: LoopDetail | null;
  onSelectLoop: (loop: LoopDetail) => void;
}) {
  const [category, setCategory] = useState("all");
  const [risk, setRisk] = useState("all");
  const [localQuery, setLocalQuery] = useState("");
  const query = `${globalQuery} ${localQuery}`.trim().toLowerCase();

  const filtered = useMemo(() => {
    return data.loops.filter((loop) => {
      if (category !== "all" && loop.category_slug !== category) return false;
      if (risk !== "all" && loop.baseline_risk_tier !== risk) return false;
      if (!query) return true;
      return [loop.name, loop.category_name, loop.trigger, loop.output, loop.run, loop.cadence].join(" ").toLowerCase().includes(query);
    });
  }, [data.loops, category, risk, query]);

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_0.9fr]">
      <Card>
        <SectionHeader title="Loop Explorer" description="Browse all 108 loops by category, risk, trigger, outcome, cadence, and control surface." action={<HelpPopover helpKey="risk" />} />
        <div className="mb-4 grid gap-3 md:grid-cols-[1fr_0.8fr_0.6fr]">
          <label className="control flex min-h-10 items-center gap-2 px-3">
            <Search className="h-4 w-4 text-fg3" aria-hidden="true" />
            <span className="sr-only">Filter loops</span>
            <input value={localQuery} onChange={(event) => setLocalQuery(event.target.value)} placeholder="Filter loops" className="w-full bg-transparent text-sm" />
          </label>
          <select className="control min-h-10 px-3 text-sm" value={category} onChange={(event) => setCategory(event.target.value)} aria-label="Filter by category">
            <option value="all">All categories</option>
            {data.categories.map((item) => (
              <option key={item.slug} value={item.slug}>
                {item.number}. {item.name}
              </option>
            ))}
          </select>
          <select className="control min-h-10 px-3 text-sm" value={risk} onChange={(event) => setRisk(event.target.value)} aria-label="Filter by risk tier">
            <option value="all">All risks</option>
            {["R0", "R1", "R2", "R3", "R4"].map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>
        <div className="overflow-hidden rounded-panel border border-border2">
          <div className="grid grid-cols-[80px_1fr_120px] border-b border-border2 bg-bg2 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-fg3">
            <span>ID</span>
            <span>Loop</span>
            <span>Risk</span>
          </div>
          <div className="max-h-screen overflow-auto">
            {filtered.length ? (
              filtered.map((loop) => (
                <button
                  key={loop.loop_id}
                  onClick={() => onSelectLoop(loop)}
                  className={`grid w-full grid-cols-[80px_1fr_120px] items-center gap-3 border-x-0 border-t-0 px-3 py-3 text-left text-sm hover:bg-bg2 ${
                    selectedLoop?.loop_id === loop.loop_id ? "bg-brandSubtle" : "bg-bg1"
                  } border-b border-border2 text-fg1`}
                >
                  <span className="font-semibold text-fg2">{loop.number}</span>
                  <span>
                    <span className="block font-semibold text-fg1">{loop.name}</span>
                    <span className="block text-xs text-fg3">{loop.category_name}</span>
                  </span>
                  <span>
                    <Badge tone={riskTone(loop.baseline_risk_tier)}>{loop.baseline_risk_tier}</Badge>
                  </span>
                </button>
              ))
            ) : (
              <div role="status" className="p-6 text-sm text-fg2">
                No loops match the current filters. Clear the search, category, or risk filter and try again.
              </div>
            )}
          </div>
        </div>
      </Card>
      <LoopDetailPanel loop={selectedLoop} />
    </div>
  );
}
