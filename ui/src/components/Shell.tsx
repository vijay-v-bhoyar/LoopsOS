import * as Dialog from "@radix-ui/react-dialog";
import {
  BrainCircuit,
  ArrowLeft,
  ClipboardCheck,
  FileText,
  Gauge,
  GitBranch,
  LogOut,
  Library,
  ListChecks,
  Moon,
  Menu,
  WifiOff,
  Search,
  ShieldCheck,
  Sun,
  X,
  FolderKanban,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Button } from "./Button";
import { deploymentPosture, DEPLOYMENT_STATUS_LABELS } from "../lib/deployment";

export type ViewId = "dashboard" | "workspace" | "loops" | "advisor" | "usecases" | "validation" | "readiness" | "plan";

const navItems: Array<{ id: ViewId; label: string; icon: ReactNode }> = [
  { id: "dashboard", label: "Dashboard", icon: <Gauge className="h-4 w-4" aria-hidden="true" /> },
  { id: "workspace", label: "Workspaces", icon: <FolderKanban className="h-4 w-4" aria-hidden="true" /> },
  { id: "loops", label: "Loop Explorer", icon: <GitBranch className="h-4 w-4" aria-hidden="true" /> },
  { id: "advisor", label: "Use Case Advisor", icon: <BrainCircuit className="h-4 w-4" aria-hidden="true" /> },
  { id: "usecases", label: "Use Case Library", icon: <Library className="h-4 w-4" aria-hidden="true" /> },
  { id: "validation", label: "Validation Studio", icon: <ClipboardCheck className="h-4 w-4" aria-hidden="true" /> },
  { id: "readiness", label: "Readiness", icon: <ShieldCheck className="h-4 w-4" aria-hidden="true" /> },
  { id: "plan", label: "Action Plan", icon: <FileText className="h-4 w-4" aria-hidden="true" /> },
];

export function Shell({
  activeView,
  onViewChange,
  query,
  onQueryChange,
  dark,
  onToggleTheme,
  userLabel,
  workspaceLabel,
  onSignOut,
  canGoBack,
  onBack,
  children,
}: {
  activeView: ViewId;
  onViewChange: (view: ViewId) => void;
  query: string;
  onQueryChange: (query: string) => void;
  dark: boolean;
  onToggleTheme: () => void;
  userLabel?: string;
  workspaceLabel?: string;
  onSignOut?: () => void;
  canGoBack?: boolean;
  onBack?: () => void;
  children: ReactNode;
}) {
  const [online, setOnline] = useState(() => (typeof navigator === "undefined" ? true : navigator.onLine));

  useEffect(() => {
    const markOnline = () => setOnline(true);
    const markOffline = () => setOnline(false);
    window.addEventListener("online", markOnline);
    window.addEventListener("offline", markOffline);
    return () => {
      window.removeEventListener("online", markOnline);
      window.removeEventListener("offline", markOffline);
    };
  }, []);

  return (
    <div className="min-h-screen bg-bg2 text-fg1">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-border2 bg-bg1 p-4 lg:block">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-panel bg-brand text-bg1">
            <ListChecks className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <div className="text-base font-semibold">LoopOS</div>
            <div className="text-xs text-fg3">Enterprise Console</div>
          </div>
        </div>
        <nav aria-label="Primary navigation" className="space-y-1">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={`flex min-h-10 w-full items-center gap-3 rounded-control px-3 text-left text-sm font-semibold reduced-motion-safe ${
                activeView === item.id ? "bg-brandSubtle text-brandStrong" : "text-fg2 hover:bg-bg2"
              }`}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </nav>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 border-b border-border2 bg-bg1 px-4 py-3 shadow-card">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-2 lg:hidden">
                <div className="flex h-9 w-9 items-center justify-center rounded-panel bg-brand text-bg1">
                  <ListChecks className="h-4 w-4" aria-hidden="true" />
                </div>
                <span className="font-semibold">LoopOS</span>
              </div>
              {canGoBack && onBack ? (
                <Button variant="ghost" onClick={onBack} aria-label="Back to previous screen" title="Back to previous screen">
                  <ArrowLeft className="h-4 w-4" aria-hidden="true" />
                </Button>
              ) : null}
            </div>
            <label className="control flex min-h-10 flex-1 items-center gap-2 px-3 md:max-w-2xl">
              <Search className="h-4 w-4 text-fg3" aria-hidden="true" />
              <span className="sr-only">Search loops and use cases</span>
              <input
                value={query}
                onChange={(event) => onQueryChange(event.target.value)}
                placeholder="Search loops, use cases, controls, risks"
                className="w-full bg-transparent text-sm text-fg1 placeholder:text-fg3"
              />
            </label>
            <div className="flex items-center gap-2 overflow-x-auto">
              {workspaceLabel ? (
                <div className="hidden max-w-xs rounded-panel border border-border2 bg-bg2 px-3 py-2 text-xs font-semibold text-fg2 md:block">
                  {workspaceLabel}
                </div>
              ) : null}
              {userLabel ? (
                <div className="hidden rounded-panel border border-border2 bg-bg2 px-3 py-2 text-xs font-semibold text-fg2 xl:block">
                  {userLabel}
                </div>
              ) : null}
              <button
                type="button"
                onClick={() => onViewChange("readiness")}
                className={`hidden min-h-9 items-center rounded-control border px-3 text-xs font-semibold md:inline-flex ${deploymentPosture.enterpriseReady ? "border-success bg-successBg text-success" : "border-border2 bg-warningBg text-warning"}`}
              >
                {DEPLOYMENT_STATUS_LABELS[deploymentPosture.status]}
              </button>
              <Dialog.Root>
                <Dialog.Trigger asChild>
                  <Button className="lg:hidden" variant="ghost" aria-label="Open navigation">
                    <Menu className="h-4 w-4" aria-hidden="true" />
                  </Button>
                </Dialog.Trigger>
                <Dialog.Portal>
                  <Dialog.Overlay className="fixed inset-0 z-40 bg-fg1/50" />
                  <Dialog.Content className="surface fixed inset-y-0 right-0 z-50 w-full max-w-sm overflow-y-auto rounded-none p-4" aria-describedby={undefined}>
                    <div className="mb-5 flex items-center justify-between gap-3 border-b border-border2 pb-4">
                      <div>
                        <Dialog.Title className="text-lg font-semibold text-fg1">Navigation</Dialog.Title>
                        <div className="mt-1 text-xs text-fg3">{DEPLOYMENT_STATUS_LABELS[deploymentPosture.status]}</div>
                      </div>
                      <Dialog.Close asChild>
                        <Button variant="ghost" aria-label="Close navigation">
                          <X className="h-4 w-4" aria-hidden="true" />
                        </Button>
                      </Dialog.Close>
                    </div>
                    <nav aria-label="Mobile navigation" className="space-y-1">
                      {navItems.map((item) => (
                        <Dialog.Close asChild key={item.id}>
                          <button
                            type="button"
                            onClick={() => onViewChange(item.id)}
                            className={`flex min-h-11 w-full items-center gap-3 rounded-control px-3 text-left text-sm font-semibold ${activeView === item.id ? "bg-brandSubtle text-brandStrong" : "text-fg2 hover:bg-bg2"}`}
                          >
                            {item.icon}
                            {item.label}
                          </button>
                        </Dialog.Close>
                      ))}
                    </nav>
                  </Dialog.Content>
                </Dialog.Portal>
              </Dialog.Root>
              <Button
                variant="ghost"
                onClick={onToggleTheme}
                aria-label={dark ? "Switch to Daylight Blue theme" : "Switch to Night Ember theme"}
                title={dark ? "Switch to Daylight Blue" : "Switch to Night Ember"}
              >
                {dark ? <Sun className="h-4 w-4" aria-hidden="true" /> : <Moon className="h-4 w-4" aria-hidden="true" />}
              </Button>
              {onSignOut ? (
                <Button variant="ghost" onClick={onSignOut} aria-label="Sign out">
                  <LogOut className="h-4 w-4" aria-hidden="true" />
                </Button>
              ) : null}
            </div>
          </div>
        </header>
        {!online ? (
          <div role="status" aria-live="polite" className="flex items-center justify-center gap-2 border-b border-warning bg-warningBg px-4 py-2 text-sm font-semibold text-warning">
            <WifiOff className="h-4 w-4" aria-hidden="true" />
            Offline. Local analysis remains available; enterprise endpoints cannot be reached.
          </div>
        ) : null}
        <main className="p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
