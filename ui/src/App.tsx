import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AuthGate } from "./components/AuthGate";
import { Shell, type ViewId } from "./components/Shell";
import { looposData } from "./lib/loopos";
import { recommendLoops } from "./lib/recommendation";
import { validateUseCase } from "./lib/validation";
import { buildEnterpriseActionPlan } from "./lib/actionPlan";
import { buildProofPackMarkdown, completeNextRunStep, createInitiativeFromWorkspace, refreshInitiative } from "./lib/sdlcProductivity";
import { consumeCrashAuthenticatedView } from "./lib/runtimeConfig";
import { createExecution, EMPTY_WORKSPACE_USE_CASE, useWorkspaceStore } from "./lib/workspaceStore";
import { downloadMarkdown } from "./lib/workspaceExport";
import { Dashboard } from "./screens/Dashboard";
import { ImplementationPlan } from "./screens/ImplementationPlan";
import { LoopExplorer } from "./screens/LoopExplorer";
import { ReadinessWorkbench } from "./screens/ReadinessWorkbench";
import { UseCaseAdvisor, type AdvisorPane } from "./screens/UseCaseAdvisor";
import { UseCaseLibrary } from "./screens/UseCaseLibrary";
import { ValidationStudio } from "./screens/ValidationStudio";
import { WorkspaceConsole } from "./screens/WorkspaceConsole";
import type { EnterpriseActionPlan, EnterpriseUser, LoopDetail, UseCaseRecord, UseCaseSource } from "./types";

const VIEW_IDS: ViewId[] = ["dashboard", "workspace", "loops", "advisor", "usecases", "validation", "readiness", "plan"];

function viewFromLocation(): ViewId {
  const candidate = window.location.hash.replace(/^#/, "") as ViewId;
  return VIEW_IDS.includes(candidate) ? candidate : "dashboard";
}

export default function App() {
  const [activeView, setActiveView] = useState<ViewId>(viewFromLocation);
  const [advisorPane, setAdvisorPane] = useState<AdvisorPane>("input");
  const activeViewRef = useRef(activeView);
  const navigationDepthRef = useRef(0);
  const [query, setQuery] = useState("");
  const [dark, setDark] = useState(false);
  const [selectedLoop, setSelectedLoop] = useState<LoopDetail | null>(looposData.loops[0] ?? null);
  const [plan, setPlan] = useState<EnterpriseActionPlan | null>(null);
  const workspace = useWorkspaceStore();
  const input = workspace.activeWorkspace?.use_case ?? EMPTY_WORKSPACE_USE_CASE;
  const inputSources = workspace.activeWorkspace?.input_sources ?? [];

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);

  useEffect(() => {
    const initialView = viewFromLocation();
    activeViewRef.current = initialView;
    window.history.replaceState({ ...window.history.state, looposView: initialView, looposDepth: 0 }, "", `#${initialView}`);
    const handlePopState = (event: PopStateEvent) => {
      const stateView = event.state?.looposView as ViewId | undefined;
      const nextView = stateView && VIEW_IDS.includes(stateView) ? stateView : viewFromLocation();
      navigationDepthRef.current = typeof event.state?.looposDepth === "number" ? event.state.looposDepth : 0;
      activeViewRef.current = nextView;
      setActiveView(nextView);
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    if (window.scrollY !== 0) window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [activeView]);

  useEffect(() => {
    if (!consumeCrashAuthenticatedView(activeView, Boolean(workspace.state.current_user))) return;
    window.dispatchEvent(new Event("loopos:test-boundary-failure"));
  }, [activeView, workspace.state.current_user]);

  const navigateTo = useCallback((nextView: ViewId) => {
    if (activeViewRef.current === nextView) return;
    navigationDepthRef.current += 1;
    window.history.pushState({ looposView: nextView, looposDepth: navigationDepthRef.current }, "", `#${nextView}`);
    activeViewRef.current = nextView;
    setActiveView(nextView);
  }, []);

  const goBack = useCallback(() => {
    if (navigationDepthRef.current > 0) {
      window.history.back();
      return;
    }
    window.history.replaceState({ looposView: "dashboard", looposDepth: 0 }, "", "#dashboard");
    activeViewRef.current = "dashboard";
    setActiveView("dashboard");
  }, []);

  const recommendations = useMemo(() => recommendLoops(input, looposData, { sources: inputSources }), [input, inputSources]);
  const validation = useMemo(() => validateUseCase(input, recommendations, looposData, inputSources), [input, inputSources, recommendations]);

  const applyInputSource = (source: UseCaseSource, nextInput: typeof input) => {
    workspace.mutateActiveWorkspace((current) => ({
      ...current,
      use_case: nextInput,
      input_sources: [...(current.input_sources ?? []), source],
    }));
  };

  const removeInputSource = (sourceId: string) => {
    workspace.mutateActiveWorkspace((current) => ({
      ...current,
      input_sources: (current.input_sources ?? []).filter((source) => source.source_id !== sourceId),
    }));
  };

  const openLoop = (loop: LoopDetail) => {
    setSelectedLoop(loop);
    navigateTo("loops");
  };

  const openPlaybook = (playbookTitle: string, description: string) => {
    workspace.updateUseCase({
      ...input,
      title: playbookTitle,
      description,
      aiScope: playbookTitle.toLowerCase().includes("agent") ? "Agentic AI" : playbookTitle.toLowerCase().includes("model") ? "GenAI use case" : "Release/compliance governance",
      businessOutcome: description,
      constraints: "Use the selected LoopOS pilot playbook and keep evidence, owners, controls, and validation explicit.",
    });
    setAdvisorPane("results");
    navigateTo("advisor");
  };

  const openUseCase = (record: UseCaseRecord) => {
    workspace.updateUseCase({
      ...input,
      title: record.title,
      description: record.summary,
      aiScope: record.title.toLowerCase().includes("agent") ? "Agentic AI" : record.title.toLowerCase().includes("rag") ? "RAG improvement" : "Existing use-case enhancement",
      businessOutcome: "Reduce enterprise coordination effort by packaging the right LoopOS loops into a governed action path.",
      constraints: `Source: ${record.source}. Rank ${record.rank}.`,
    });
    setAdvisorPane("results");
    navigateTo("advisor");
  };

  const setPlanAndOpen = (nextPlan: EnterpriseActionPlan) => {
    setPlan(nextPlan);
    workspace.savePlan(nextPlan);
    navigateTo("plan");
  };

  const recordDashboardDryRun = () => {
    const recommendation = recommendations[0];
    const loop = recommendation ? looposData.loops.find((item) => item.loop_id === recommendation.loop_id) : null;
    if (!loop || !workspace.activeWorkspace || !currentUser) return;
    const record = createExecution({
      loop_id: loop.loop_id,
      title: `Dry run: ${loop.name}`,
      correlation_id: `dry-run-${Date.now().toString(36)}`,
      state: validation.readiness === "Blocked" ? "Recorded with readiness gaps" : "Recorded dry run",
      risk_tier: loop.baseline_risk_tier,
      evidence_refs: [
        `workspace:${workspace.activeWorkspace.workspace_id}`,
        `readiness:${validation.readiness}`,
        `controls:${loop.control_profile.applicable_control_ids.length}`,
      ].join(" | "),
      validation_result: validation.readiness === "Blocked" ? "Inconclusive" : "Passed",
      proof_state: validation.readiness === "Blocked" ? "Effectiveness Pending" : "Proof Green",
      owner: currentUser.name,
    });
    workspace.mutateActiveWorkspace((current) => ({
      ...current,
      selected_loop_ids: Array.from(new Set([loop.loop_id, ...current.selected_loop_ids])),
      execution_records: [record, ...current.execution_records],
    }));
  };

  const createSdlcInitiative = () => {
    if (!workspace.activeWorkspace || !currentUser) return;
    const initiative = createInitiativeFromWorkspace(workspace.activeWorkspace, recommendations, validation, looposData, currentUser.name);
    workspace.mutateActiveWorkspace((current) => ({
      ...current,
      selected_loop_ids: Array.from(new Set([...initiative.loop_bundle_ids, ...current.selected_loop_ids])),
      initiatives: [initiative, ...current.initiatives],
    }));
  };

  const completeSdlcRunStep = () => {
    const initiative = workspace.activeWorkspace?.initiatives[0];
    if (!initiative) return;
    workspace.mutateActiveWorkspace((current) => ({
      ...current,
      initiatives: current.initiatives.map((item) => {
        if (item.id !== initiative.id) return item;
        const run = item.execution_records[0];
        if (!run) return item;
        const nextRun = completeNextRunStep(run);
        return refreshInitiative({ ...item, execution_records: [nextRun, ...item.execution_records.slice(1)] }, validation);
      }),
    }));
  };

  const exportSdlcProofPack = () => {
    const active = workspace.activeWorkspace;
    const initiative = active?.initiatives[0];
    if (!active || !initiative) return;
    const markdown = buildProofPackMarkdown(active, initiative, looposData, validation);
    const base = initiative.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "loopos-proof-pack";
    downloadMarkdown(`${base}-proof-pack.md`, markdown);
    workspace.mutateActiveWorkspace((current) => ({ ...current, action_plan_markdown: markdown }));
  };

  const renderView = (currentUser: EnterpriseUser) => {
    if (activeView === "dashboard") {
      return (
        <Dashboard
          data={looposData}
          activeWorkspace={workspace.activeWorkspace}
          recommendations={recommendations}
          validation={validation}
          onOpenAdvisor={() => navigateTo("advisor")}
          onOpenPlaybook={(playbook) => openPlaybook(playbook.title, playbook.effort_saving)}
          onOpenWorkspace={() => {
            workspace.savePlan(buildEnterpriseActionPlan(input, recommendations, validation));
            navigateTo("workspace");
          }}
          onOpenValidation={() => navigateTo("validation")}
          onOpenPlan={() => setPlanAndOpen(buildEnterpriseActionPlan(input, recommendations, validation))}
          onOpenLoop={openLoop}
          onRecordDryRun={recordDashboardDryRun}
          onCreateInitiative={createSdlcInitiative}
          onCompleteRunStep={completeSdlcRunStep}
          onExportProofPack={exportSdlcProofPack}
        />
      );
    }
    if (activeView === "loops") {
      return <LoopExplorer data={looposData} globalQuery={query} selectedLoop={selectedLoop} onSelectLoop={setSelectedLoop} />;
    }
    if (activeView === "advisor") {
      return (
        <UseCaseAdvisor
          data={looposData}
          input={input}
          inputSources={inputSources}
          workspaceId={workspace.activeWorkspace?.workspace_id ?? "local-workspace"}
          onInputChange={workspace.updateUseCase}
          onApplyInputSource={applyInputSource}
          onRemoveInputSource={removeInputSource}
          onPlanChange={setPlanAndOpen}
          onSelectLoop={openLoop}
          activePane={advisorPane}
          onPaneChange={setAdvisorPane}
        />
      );
    }
    if (activeView === "workspace") {
      return (
        <WorkspaceConsole
          data={looposData}
          user={currentUser}
          activeWorkspace={workspace.activeWorkspace}
          workspaces={workspace.state.workspaces}
          onCreateWorkspace={workspace.addWorkspace}
          onSetActiveWorkspace={workspace.setActiveWorkspace}
          onMutateWorkspace={workspace.mutateActiveWorkspace}
          onUseCaseChange={workspace.updateUseCase}
          onDeleteWorkspace={workspace.deleteWorkspace}
          persistence={workspace.persistence}
        />
      );
    }
    if (activeView === "usecases") {
      return <UseCaseLibrary data={looposData} query={query} onUseCaseSelect={openUseCase} />;
    }
    if (activeView === "validation") {
      return <ValidationStudio data={looposData} input={input} validation={validation} />;
    }
    if (activeView === "readiness") {
      return <ReadinessWorkbench data={looposData} />;
    }
    return <ImplementationPlan plan={plan ?? buildEnterpriseActionPlan(input, recommendations, validation)} />;
  };
  const currentUser = workspace.state.current_user;

  return (
    <AuthGate user={currentUser} onSignIn={workspace.signIn}>
      {currentUser ? (
        <Shell
          activeView={activeView}
          onViewChange={navigateTo}
          query={query}
          onQueryChange={setQuery}
          dark={dark}
          onToggleTheme={() => setDark((value) => !value)}
          userLabel={`${currentUser.name} / ${currentUser.role}`}
          workspaceLabel={workspace.activeWorkspace?.name}
          onSignOut={workspace.signOut}
          canGoBack={activeView !== "dashboard"}
          onBack={goBack}
        >
          {renderView(currentUser)}
        </Shell>
      ) : null}
    </AuthGate>
  );
}
