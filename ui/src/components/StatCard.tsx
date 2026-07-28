import type { ReactNode } from "react";

export function StatCard({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: string | number;
  detail: string;
  icon: ReactNode;
}) {
  return (
    <div className="surface flex items-start gap-3 p-4">
      <div className="rounded-panel bg-brandSubtle p-2 text-brand">{icon}</div>
      <div>
        <div className="text-2xl font-semibold text-fg1">{value}</div>
        <div className="text-sm font-semibold text-fg1">{label}</div>
        <div className="mt-1 text-xs text-fg3">{detail}</div>
      </div>
    </div>
  );
}
