import { AlertTriangle, Ban, CheckCircle2, FileCheck2, PlayCircle, Power, Radio, RefreshCw, RotateCcw, Server, ShieldCheck, Square, SquareTerminal } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Badge, riskTone } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card, SectionHeader } from "../../components/Card";
import { InlineNote } from "../../components/Help";
import { downloadMarkdown } from "../../lib/workspaceExport";
import type { EnterpriseUser, LoopOSData, SavedWorkspace } from "../../types";
import {
  approveGovernedRun,
  AuthorityError,
  activateKillSwitch,
  createAuthoritySession,
  createGovernedRun,
  recordReleaseInitiative as recordReleaseInitiativeAtomically,
  deactivateKillSwitch,
  getKillSwitchStatus,
  getReleaseProofPack,
  getGovernedRun,
  listConnectorEvents,
  listGovernedRuns,
  listReleaseInitiatives,
  recoverGovernedRun,
  rejectGovernedRun,
  rollbackGovernedRun,
  startGovernedRun,
  streamGovernedRun,
  verifyAuthorityAudit,
} from "./authorityClient";
import { requireConnectorUrl } from "./endpointValidation";
import { buildConnectorEventsForRelease, buildReleaseInitiativeRecord, buildWorkspaceExecutionPlan, type AuditVerification, type AuthorityEvent, type ConnectorEventRecord, type GovernedRun, type KillSwitchStatus, type ReleaseInitiativeRecord } from "./types";

type ConnectionState = "connecting" | "available" | "unavailable";

export function GovernedExecutionPanel({
  data,
  user,
  workspace,
  onSessionExpired,
}: {
  data: LoopOSData;
  user: EnterpriseUser;
  workspace: SavedWorkspace;
  onSessionExpired?: () => void;
}) {
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [runs, setRuns] = useState<GovernedRun[]>([]);
  const [releaseInitiatives, setReleaseInitiatives] = useState<ReleaseInitiativeRecord[]>([]);
  const [connectorEvents, setConnectorEvents] = useState<ConnectorEventRecord[]>([]);
  const [killSwitch, setKillSwitch] = useState<KillSwitchStatus | null>(null);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [loopId, setLoopId] = useState(workspace.selected_loop_ids[0] ?? data.loops[0]?.loop_id ?? "");
  const [targetMode, setTargetMode] = useState<"record" | "http">("record");
  const [endpoint, setEndpoint] = useState("");
  const [requestBody, setRequestBody] = useState("{}");
  const [rollbackEndpoint, setRollbackEndpoint] = useState("");
  const [rollbackBody, setRollbackBody] = useState("{}");
  const [verificationEndpoint, setVerificationEndpoint] = useState("");
  const [verificationPath, setVerificationPath] = useState("status");
  const [verificationExpected, setVerificationExpected] = useState('"active"');
  const [observationDelay, setObservationDelay] = useState(0);
  const [events, setEvents] = useState<AuthorityEvent[]>([]);
  const [approvalReason, setApprovalReason] = useState("Executable payload, evidence scope, risk tier, and validation probes reviewed.");
  const [killSwitchReason, setKillSwitchReason] = useState("Emergency stop requested after an unsafe or unexpected execution condition.");
  const [busy, setBusy] = useState(false);
  const [followingRunId, setFollowingRunId] = useState<string | null>(null);
  const [observationNotice, setObservationNotice] = useState("");
  const [error, setError] = useState("");
  const [auditVerification, setAuditVerification] = useState<AuditVerification | null>(null);
  const tokenRef = useRef("");
  const tenantRef = useRef("");
  const streamControllerRef = useRef<AbortController | null>(null);
  const connectionGenerationRef = useRef(0);
  const eventCursorRef = useRef<Record<string, number>>({});
  const selectedRun = runs.find((run) => run.run_id === selectedRunId) ?? runs[0] ?? null;
  const selectedLoop = data.loops.find((loop) => loop.loop_id === loopId) ?? data.loops[0];
  const activeInitiative = workspace.initiatives[0] ?? null;
  const verifiedConnectorEvents = connectorEvents.filter((event) => event.verification_status === "verified_webhook").length;
  const sessionConnectorEvents = connectorEvents.filter((event) => event.verification_status === "session_authenticated").length;

  const handleAuthorityFailure = useCallback((reason: unknown) => {
    if (reason instanceof AuthorityError && reason.status === 401) {
      tokenRef.current = "";
      tenantRef.current = "";
      streamControllerRef.current?.abort();
      onSessionExpired?.();
    }
    setError(messageFor(reason));
  }, [onSessionExpired]);

  const connect = useCallback(async () => {
    const connectionGeneration = connectionGenerationRef.current + 1;
    connectionGenerationRef.current = connectionGeneration;
    setConnection("connecting");
    setError("");
    try {
      const session = await createAuthoritySession(user);
      if (connectionGeneration !== connectionGenerationRef.current) return;
      const accessToken = session.access_token;
      const tenantId = session.actor.tenant_id;
      tokenRef.current = accessToken;
      tenantRef.current = tenantId;
      const [records, initiatives, events] = await Promise.all([
        listGovernedRuns(accessToken, workspace.workspace_id, tenantId),
        listReleaseInitiatives(accessToken, workspace.workspace_id, tenantId),
        listConnectorEvents(accessToken, workspace.workspace_id, tenantId),
      ]);
      const control = await getKillSwitchStatus(accessToken, tenantId);
      if (connectionGeneration !== connectionGenerationRef.current) return;
      setRuns(records);
      setReleaseInitiatives(initiatives);
      setConnectorEvents(events);
      setKillSwitch(control);
      setSelectedRunId((current) => current || records[0]?.run_id || "");
      setConnection("available");
    } catch (reason) {
      if (connectionGeneration !== connectionGenerationRef.current) return;
      tokenRef.current = "";
      tenantRef.current = "";
      setConnection("unavailable");
      handleAuthorityFailure(reason);
    }
  }, [handleAuthorityFailure, user, workspace.workspace_id]);

  useEffect(() => {
    void connect();
    return () => {
      connectionGenerationRef.current += 1;
      streamControllerRef.current?.abort();
    };
  }, [connect]);

  const refresh = useCallback(async (runId?: string): Promise<boolean> => {
    if (!tokenRef.current) return false;
    const connectionGeneration = connectionGenerationRef.current;
    try {
      const [records, initiatives, events] = await Promise.all([
        listGovernedRuns(tokenRef.current, workspace.workspace_id, tenantRef.current),
        listReleaseInitiatives(tokenRef.current, workspace.workspace_id, tenantRef.current),
        listConnectorEvents(tokenRef.current, workspace.workspace_id, tenantRef.current),
      ]);
      const control = await getKillSwitchStatus(tokenRef.current, tenantRef.current);
      if (connectionGeneration !== connectionGenerationRef.current) return false;
      setRuns(records);
      setReleaseInitiatives(initiatives);
      setConnectorEvents(events);
      setKillSwitch(control);
      if (runId) setSelectedRunId(runId);
      return true;
    } catch (reason) {
      handleAuthorityFailure(reason);
      return false;
    }
  }, [handleAuthorityFailure, workspace.workspace_id]);

  const recordReleaseInitiative = async () => {
    if (!activeInitiative?.release_assurance || !tokenRef.current) return;
    setBusy(true);
    setError("");
    try {
      const response = await recordReleaseInitiativeAtomically(
        tokenRef.current,
        buildReleaseInitiativeRecord(workspace, activeInitiative),
        buildConnectorEventsForRelease(workspace, activeInitiative),
        tenantRef.current,
      );
      const eventIds = response.connector_events.map((event) => event.connector_event_id);
      setConnectorEvents((current) => [...response.connector_events, ...current.filter((item) => !eventIds.includes(item.connector_event_id))]);
      setReleaseInitiatives((current) => [response.initiative, ...current.filter((item) => item.initiative_id !== response.initiative.initiative_id)]);
    } catch (reason) {
      handleAuthorityFailure(reason);
    } finally {
      setBusy(false);
    }
  };

  const downloadAuthorityProofPack = async () => {
    const initiative = releaseInitiatives[0];
    if (!initiative || !tokenRef.current) return;
    setBusy(true);
    setError("");
    try {
      const proofPack = await getReleaseProofPack(tokenRef.current, initiative.initiative_id, tenantRef.current);
      const base = proofPack.release_name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "release-proof-pack";
      downloadMarkdown(`${base}-authority-proof-pack.md`, proofPack.markdown);
    } catch (reason) {
      handleAuthorityFailure(reason);
    } finally {
      setBusy(false);
    }
  };

  const follow = async (runId: string, stopAtApproval = false) => {
    const connectionGeneration = connectionGenerationRef.current;
    streamControllerRef.current?.abort();
    const controller = new AbortController();
    streamControllerRef.current = controller;
    setFollowingRunId(runId);
    setObservationNotice("");
    try {
      await streamGovernedRun(tokenRef.current, runId, tenantRef.current, (event) => {
        if (connectionGeneration !== connectionGenerationRef.current) return;
        eventCursorRef.current[runId] = Math.max(eventCursorRef.current[runId] ?? 0, event.sequence);
        setEvents((current) => current.some((item) => item.sequence === event.sequence) ? current : [...current, event].slice(-100));
      }, controller.signal, eventCursorRef.current[runId] ?? 0, stopAtApproval);
      if (connectionGeneration !== connectionGenerationRef.current) return;
      const run = await getGovernedRun(tokenRef.current, runId, tenantRef.current);
      if (connectionGeneration !== connectionGenerationRef.current) return;
      setRuns((current) => [run, ...current.filter((item) => item.run_id !== run.run_id)]);
      setSelectedRunId(run.run_id);
    } catch (reason) {
      if (!controller.signal.aborted && connectionGeneration === connectionGenerationRef.current) handleAuthorityFailure(reason);
    } finally {
      if (streamControllerRef.current === controller) {
        streamControllerRef.current = null;
        setFollowingRunId(null);
      }
    }
  };

  const stopFollowing = () => {
    if (!streamControllerRef.current) return;
    streamControllerRef.current.abort();
    setObservationNotice("Stopping observation does not cancel a remote request or change its remote execution state.");
  };

  const execute = async () => {
    if (!selectedLoop || !tokenRef.current) return;
    setBusy(true);
    setError("");
    try {
      const target = targetMode === "http" ? {
        mode: "http" as const,
        endpoint: requireConnectorUrl(endpoint, "Action endpoint"),
        method: "POST" as const,
        body: parseObject(requestBody, "Request body"),
        rollbackEndpoint: requireConnectorUrl(rollbackEndpoint, "Compensation endpoint"),
        rollbackBody: parseObject(rollbackBody, "Compensation body"),
        verificationEndpoint: requireConnectorUrl(verificationEndpoint, "Verification endpoint"),
        verificationPath: verificationPath.trim(),
        verificationExpected: parseJsonValue(verificationExpected),
        observationDelaySeconds: observationDelay,
      } : { mode: "record" as const };
      const input = buildWorkspaceExecutionPlan(workspace, selectedLoop.loop_id, selectedLoop.name, selectedLoop.baseline_risk_tier, target);
      const run = await createGovernedRun(tokenRef.current, input, tenantRef.current);
      eventCursorRef.current[run.run_id] = 0;
      setEvents([]);
      setRuns((current) => [run, ...current.filter((item) => item.run_id !== run.run_id)]);
      setSelectedRunId(run.run_id);
      await startGovernedRun(tokenRef.current, run.run_id);
      await follow(run.run_id, run.requires_approval);
    } catch (reason) {
      handleAuthorityFailure(reason);
    } finally {
      setBusy(false);
    }
  };

  const changeKillSwitch = async (activate: boolean) => {
    if (!tokenRef.current || user.role !== "Executive" || killSwitchReason.trim().length < 3) return;
    setBusy(true);
    setError("");
    try {
      const control = activate
        ? await activateKillSwitch(tokenRef.current, killSwitchReason, tenantRef.current)
        : await deactivateKillSwitch(tokenRef.current, killSwitchReason, tenantRef.current);
      setKillSwitch(control);
      await refresh();
    } catch (reason) {
      handleAuthorityFailure(reason);
    } finally {
      setBusy(false);
    }
  };

  const approve = async () => {
    if (!selectedRun || !tokenRef.current) return;
    setBusy(true);
    setError("");
    try {
      await approveGovernedRun(tokenRef.current, selectedRun, approvalReason);
      await startGovernedRun(tokenRef.current, selectedRun.run_id);
      await follow(selectedRun.run_id, false);
    } catch (reason) {
      handleAuthorityFailure(reason);
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    if (!selectedRun || !tokenRef.current) return;
    setBusy(true);
    setError("");
    try {
      await rejectGovernedRun(tokenRef.current, selectedRun, approvalReason);
      if (!await refresh(selectedRun.run_id)) return;
      await follow(selectedRun.run_id);
    } catch (reason) {
      handleAuthorityFailure(reason);
    } finally {
      setBusy(false);
    }
  };

  const verifyAudit = async () => {
    if (!tokenRef.current) return;
    setBusy(true);
    setError("");
    try {
      setAuditVerification(await verifyAuthorityAudit(tokenRef.current));
    } catch (reason) {
      handleAuthorityFailure(reason);
    } finally {
      setBusy(false);
    }
  };

  const recover = async () => {
    if (!selectedRun || !tokenRef.current) return;
    setBusy(true);
    setError("");
    try {
      const successor = await recoverGovernedRun(tokenRef.current, selectedRun.run_id);
      eventCursorRef.current[successor.run_id] = 0;
      setEvents([]);
      if (!await refresh(successor.run_id)) return;
      await startGovernedRun(tokenRef.current, successor.run_id);
      await follow(successor.run_id, successor.requires_approval);
    } catch (reason) {
      handleAuthorityFailure(reason);
    } finally {
      setBusy(false);
    }
  };

  const rollback = async () => {
    if (!selectedRun || !tokenRef.current) return;
    setBusy(true);
    setError("");
    try {
      await rollbackGovernedRun(tokenRef.current, selectedRun.run_id);
      await follow(selectedRun.run_id);
    } catch (reason) {
      handleAuthorityFailure(reason);
    } finally {
      setBusy(false);
    }
  };

  const canApprove = user.role === "Approver" || user.role === "Executive";
  const canExecute = user.role !== "Auditor";
  const killSwitchActive = killSwitch?.active === true;
  const canStartExecution = canExecute && !killSwitchActive;
  const canVerifyAudit = user.role === "Auditor" || user.role === "Executive";
  const canRecover = canExecute && selectedRun && (["BLOCKED", "ROLLED_BACK", "EFFECTIVENESS_FAILED"].includes(selectedRun.state) || selectedRun.runner_status === "failed");
  const canRollback = selectedRun?.plan.rollback && ["ACTION_IN_PROGRESS", "ACTION_APPLIED", "VALIDATION_FAILED", "PROOF_FAILED"].includes(selectedRun.state);
  const eventSummary = useMemo(() => events.slice().reverse(), [events]);

  return (
    <Card className="xl:col-span-2">
      <SectionHeader
        title="Governed Execution Authority"
        description="Creates durable runs, enforces the corpus state machine and approvals, invokes registered tools, records evidence and probes, and streams append-only audit events."
        action={<ConnectionBadge state={connection} />}
      />

      {connection === "unavailable" ? (
        <InlineNote tone="warning">
          <div>Authority unavailable. No execution was simulated or recorded locally. Start the authority service and reconnect. {error}</div>
          <Button variant="primary" className="mt-3" onClick={() => void connect()}>
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Reconnect authority
          </Button>
        </InlineNote>
      ) : null}
      {connection === "connecting" ? <InlineNote>Connecting to the governed execution authority...</InlineNote> : null}
      {connection === "available" ? (
        <div className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-fg1">Loop to execute</span>
              <select className="control min-h-10 w-full px-3 text-sm" value={loopId} onChange={(event) => setLoopId(event.target.value)}>
                {data.loops.map((loop) => <option key={loop.loop_id} value={loop.loop_id}>{loop.number}. {loop.name} ({loop.baseline_risk_tier})</option>)}
              </select>
            </label>
            <div className="flex items-end gap-2">
              <Button variant="primary" onClick={execute} disabled={busy || !selectedLoop || !canStartExecution} title={killSwitchActive ? "Tenant execution is stopped by the active kill switch" : canExecute ? "Run the selected loop" : "Auditor sessions are read-only"}>
                <PlayCircle className="h-4 w-4" aria-hidden="true" />
                {busy ? "Running..." : "Run loop"}
              </Button>
              {followingRunId ? (
                <Button variant="danger" onClick={stopFollowing} title="Stop local event observation only; this does not cancel remote execution">
                  <Square className="h-4 w-4" aria-hidden="true" />
                  Stop following events
                </Button>
              ) : null}
              <Button variant="ghost" onClick={() => void refresh()} disabled={busy} aria-label="Refresh governed runs" title="Refresh governed runs">
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
          </div>

          {observationNotice ? <InlineNote tone="warning">{observationNotice}</InlineNote> : null}

          {!canExecute ? <InlineNote>Auditor sessions are read-only. You can inspect runs, follow events, and verify the audit chain.</InlineNote> : null}

          <div className={`rounded-panel border p-3 ${killSwitchActive ? "border-danger bg-dangerBg" : "border-border2 bg-bg2"}`} aria-label="Tenant execution control">
            <div className="flex flex-wrap items-center gap-2">
              <Power className="h-4 w-4 text-fg1" aria-hidden="true" />
              <div className="font-semibold text-fg1">Tenant execution control</div>
              <Badge tone={killSwitchActive ? "danger" : "success"}>{killSwitchActive ? "STOPPED" : "RUNNING"}</Badge>
            </div>
            <div className="mt-1 text-sm text-fg2">
              {killSwitchActive
                ? "New runs and queued dispatch are blocked. Runs already in an external request may finish; this authority does not claim remote cancellation or credential revocation. Deactivation does not resume blocked runs; restart requires a new run and approval."
                : "Executive-authorized emergency stop for this tenant. It prevents new and queued execution and records the decision in the append-only audit chain."}
            </div>
            {killSwitch?.activation_id ? <div className="mt-2 break-all font-mono text-xs text-fg3">activation {killSwitch.activation_id}</div> : null}
            {user.role === "Executive" ? (
              <div className="mt-3 grid gap-2 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
                <label className="block">
                  <span className="mb-1 block text-sm font-semibold text-fg1">Control decision note</span>
                  <textarea className="control min-h-16 w-full px-3 py-2 text-sm" value={killSwitchReason} onChange={(event) => setKillSwitchReason(event.target.value)} />
                </label>
                <Button variant={killSwitchActive ? "primary" : "danger"} onClick={() => void changeKillSwitch(!killSwitchActive)} disabled={busy || killSwitchReason.trim().length < 3}>
                  <Power className="h-4 w-4" aria-hidden="true" />
                  {killSwitchActive ? "Restore tenant execution" : "Stop tenant execution"}
                </Button>
              </div>
            ) : <div className="mt-2 text-sm text-fg3">Only an Executive session can change this control. Other roles can inspect its status.</div>}
          </div>

          {activeInitiative?.release_assurance ? (
            <div className="rounded-panel border border-border2 bg-bg2 p-3">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <Badge tone="brand">{activeInitiative.release_assurance.release_name}</Badge>
                <Badge>{activeInitiative.release_assurance.gates.length} gates</Badge>
                <Badge>{connectorEvents.length} connector evidence events</Badge>
                <Badge tone={verifiedConnectorEvents ? "success" : "neutral"}>{verifiedConnectorEvents} webhook verified</Badge>
                <Badge tone={sessionConnectorEvents ? "warning" : "neutral"}>{sessionConnectorEvents} session snapshots</Badge>
                <Badge>{releaseInitiatives.length} durable release records</Badge>
              </div>
              <div className="grid gap-3 lg:grid-cols-[1fr_auto] lg:items-center">
                <div>
                  <div className="text-sm font-semibold text-fg1">Release assurance authority record</div>
                  <div className="mt-1 text-sm text-fg2">
                    Persists Jira/GitHub/manual evidence events first, then binds their event IDs to release gates, exceptions, and proof-pack scope in the tenant audit chain.
                  </div>
                </div>
                <Button onClick={recordReleaseInitiative} disabled={busy || !canExecute}>
                  <FileCheck2 className="h-4 w-4" aria-hidden="true" />
                  Record release initiative
                </Button>
                <Button variant="ghost" onClick={downloadAuthorityProofPack} disabled={busy || !releaseInitiatives[0]} title="Download the authority-generated proof pack for the latest durable release record">
                  <FileCheck2 className="h-4 w-4" aria-hidden="true" />
                  Authority proof pack
                </Button>
              </div>
              {releaseInitiatives[0] ? (
                <div className="mt-3 rounded-panel border border-border2 bg-bg1 p-2 text-xs text-fg2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span>Latest durable record: <span className="font-mono">{releaseInitiatives[0].initiative_id}</span> / {releaseInitiatives[0].status}</span>
                    <Badge tone={freshnessTone(releaseInitiatives[0].freshness_summary?.status)}>
                      freshness {releaseInitiatives[0].freshness_summary?.status ?? "not evaluated"}
                    </Badge>
                    <Badge tone={verdictTone(releaseInitiatives[0].readiness_verdict?.verdict)}>
                      release {releaseInitiatives[0].readiness_verdict?.verdict ?? "not evaluated"}
                    </Badge>
                  </div>
                  {releaseInitiatives[0].freshness_summary?.policy ? (
                    <div className="mt-1">
                      {releaseInitiatives[0].freshness_summary.policy}; {releaseInitiatives[0].freshness_summary.source_event_count ?? 0} source events evaluated.
                    </div>
                  ) : null}
                  {releaseInitiatives[0].readiness_verdict?.policy ? (
                    <div className="mt-1">
                      {releaseInitiatives[0].readiness_verdict.policy}
                    </div>
                  ) : null}
                  {releaseInitiatives[0].readiness_verdict?.failing_reasons?.length ? (
                    <div className="mt-1 text-danger">{releaseInitiatives[0].readiness_verdict.failing_reasons.join(" | ")}</div>
                  ) : null}
                  {releaseInitiatives[0].readiness_verdict?.review_reasons?.length ? (
                    <div className="mt-1 text-warning">{releaseInitiatives[0].readiness_verdict.review_reasons.join(" | ")}</div>
                  ) : null}
                </div>
              ) : null}
              {connectorEvents.length ? (
                <div className="mt-3 grid gap-2 lg:grid-cols-3">
                  {connectorEvents.slice(0, 6).map((event) => (
                    <div key={event.connector_event_id} className="rounded-panel border border-border2 bg-bg1 p-2 text-xs">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={event.verification_status === "verified_webhook" ? "success" : "warning"}>
                          {event.verification_status === "verified_webhook" ? "verified webhook" : "session snapshot"}
                        </Badge>
                        <span className="font-semibold text-fg1">{event.system}</span>
                      </div>
                      <div className="mt-1 truncate text-fg2" title={event.label}>{event.label}</div>
                      <div className="mt-1 font-mono text-fg3">{event.payload_hash.slice(0, 12)}</div>
                      {event.delivery_id ? <div className="mt-1 truncate text-fg3" title={event.delivery_id}>delivery {event.delivery_id}</div> : null}
                    </div>
                  ))}
                </div>
              ) : (
                <InlineNote>
                  No connector evidence events have been recorded in the authority store yet. Release gates remain profile-level until a session snapshot or verified webhook is attached.
                </InlineNote>
              )}
            </div>
          ) : null}

          <div className="rounded-panel border border-border2 bg-bg2 p-3">
            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-fg1">Execution target</span>
              <select className="control min-h-10 w-full px-3 text-sm" value={targetMode} onChange={(event) => setTargetMode(event.target.value as "record" | "http")}>
                <option value="record">Durable authority artifact</option>
                <option value="http">Allowlisted enterprise HTTP connector</option>
              </select>
            </label>
            {targetMode === "http" ? (
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                <ConnectorField label="Action endpoint" value={endpoint} onChange={setEndpoint} placeholder="https://change.example.com/actions" />
                <JsonField label="Request body" value={requestBody} onChange={setRequestBody} />
                <ConnectorField label="Compensation endpoint" value={rollbackEndpoint} onChange={setRollbackEndpoint} placeholder="https://change.example.com/compensate" />
                <JsonField label="Compensation body" value={rollbackBody} onChange={setRollbackBody} />
                <ConnectorField label="Verification endpoint" value={verificationEndpoint} onChange={setVerificationEndpoint} placeholder="https://change.example.com/status" />
                <label className="block">
                  <span className="mb-1 block text-sm font-semibold text-fg1">Verification JSON path</span>
                  <input className="control min-h-10 w-full px-3 text-sm" value={verificationPath} onChange={(event) => setVerificationPath(event.target.value)} />
                </label>
                <label className="block">
                  <span className="mb-1 block text-sm font-semibold text-fg1">Expected JSON value</span>
                  <input className="control min-h-10 w-full px-3 font-mono text-sm" value={verificationExpected} onChange={(event) => setVerificationExpected(event.target.value)} />
                </label>
                <label className="block">
                  <span className="mb-1 block text-sm font-semibold text-fg1">Effectiveness delay (seconds)</span>
                  <input type="number" min={0} max={604800} className="control min-h-10 w-full px-3 text-sm" value={observationDelay} onChange={(event) => setObservationDelay(Math.max(0, Math.min(604800, Number(event.target.value) || 0)))} />
                </label>
                <div className="lg:col-span-2"><InlineNote>Connector credentials are resolved only by the authority service. External actions always require payload-bound approval and a compensation contract.</InlineNote></div>
              </div>
            ) : null}
          </div>

          {error ? <InlineNote tone="warning"><AlertTriangle className="mr-2 inline h-4 w-4" aria-hidden="true" />{error}</InlineNote> : null}

          {runs.length ? (
            <div className="grid gap-4 xl:grid-cols-[minmax(16rem,0.7fr)_minmax(0,1.3fr)]">
              <div className="space-y-2">
                <div className="text-sm font-semibold text-fg1">Durable runs</div>
                {runs.map((run) => (
                  <button key={run.run_id} type="button" onClick={() => { setSelectedRunId(run.run_id); eventCursorRef.current[run.run_id] = 0; setEvents([]); }} className={`w-full rounded-panel border p-3 text-left ${selectedRun?.run_id === run.run_id ? "border-brand bg-brandSubtle" : "border-border2 bg-bg2"}`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={stateTone(run.state)}>{run.state}</Badge>
                      <Badge tone={riskTone(run.risk_tier)}>{run.risk_tier}</Badge>
                      <span className="text-xs text-fg3">attempt {run.attempt}</span>
                    </div>
                    <div className="mt-2 break-words text-sm font-semibold text-fg1">{run.title}</div>
                    <div className="mt-1 break-all font-mono text-xs text-fg3">{run.run_id}</div>
                  </button>
                ))}
              </div>

              {selectedRun ? (
                <div className="min-w-0 space-y-4">
                  <RunSummary run={selectedRun} data={data} />
                  {selectedRun.state === "PLANNED" && selectedRun.requires_approval ? (
                    <div className="rounded-panel border border-warning bg-warningBg p-3">
                      <div className="flex items-center gap-2 font-semibold text-fg1"><ShieldCheck className="h-4 w-4" aria-hidden="true" />Payload-bound approval required</div>
                      <div className="mt-1 break-all font-mono text-xs text-fg2">{selectedRun.payload_hash}</div>
                      <label className="mt-3 block">
                        <span className="mb-1 block text-sm font-semibold text-fg1">Decision reason</span>
                        <textarea className="control min-h-20 w-full px-3 py-2 text-sm" value={approvalReason} onChange={(event) => setApprovalReason(event.target.value)} />
                      </label>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button variant="primary" onClick={approve} disabled={busy || killSwitchActive || !canApprove || approvalReason.trim().length < 3}>
                          <CheckCircle2 className="h-4 w-4" aria-hidden="true" />Approve exact payload and continue
                        </Button>
                        <Button variant="danger" onClick={reject} disabled={busy || killSwitchActive || !canApprove || approvalReason.trim().length < 3}>
                          <Ban className="h-4 w-4" aria-hidden="true" />Reject and block
                        </Button>
                      </div>
                      {!canApprove ? <div className="mt-2 text-sm text-warning">The current authority session can inspect this request but cannot approve it.</div> : null}
                    </div>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    {canRecover ? <Button onClick={recover} disabled={busy}><RotateCcw className="h-4 w-4" aria-hidden="true" />Create recovery run</Button> : null}
                    {canRollback ? <Button variant="danger" onClick={rollback} disabled={busy || killSwitchActive || !canApprove}><RotateCcw className="h-4 w-4" aria-hidden="true" />Run compensation</Button> : null}
                    <Button onClick={() => void follow(selectedRun.run_id, selectedRun.runner_status === "awaiting_approval")} disabled={busy}><Radio className="h-4 w-4" aria-hidden="true" />Follow events</Button>
                    {canVerifyAudit ? <Button onClick={verifyAudit} disabled={busy}><FileCheck2 className="h-4 w-4" aria-hidden="true" />Verify audit chain</Button> : null}
                  </div>
                  {auditVerification ? (
                    <InlineNote tone={auditVerification.valid ? "info" : "critical"}>
                      Audit chain {auditVerification.valid ? "verified" : "invalid"} across {auditVerification.event_count} tenant events
                      {auditVerification.first_invalid_sequence ? `; first invalid sequence ${auditVerification.first_invalid_sequence}` : ""}.
                    </InlineNote>
                  ) : null}
                  {selectedRun.output ? <RunOutput output={selectedRun.output} verified={selectedRun.state === "EFFECTIVENESS_PROVEN"} /> : null}
                  <EventTimeline events={eventSummary} />
                </div>
              ) : null}
            </div>
          ) : (
            <div className="rounded-panel border border-border2 bg-bg2 p-4 text-sm text-fg2">No governed runs exist for this workspace.</div>
          )}
        </div>
      ) : null}
    </Card>
  );
}

function ConnectionBadge({ state }: { state: ConnectionState }) {
  if (state === "available") return <Badge tone="success"><Server className="h-3.5 w-3.5" aria-hidden="true" />Authority connected</Badge>;
  if (state === "unavailable") return <Badge tone="danger"><AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />Authority unavailable</Badge>;
  return <Badge tone="warning"><Radio className="h-3.5 w-3.5" aria-hidden="true" />Connecting</Badge>;
}

function RunSummary({ run, data }: { run: GovernedRun; data: LoopOSData }) {
  const loop = data.loops.find((item) => item.loop_id === run.loop_id);
  return (
    <div className="rounded-panel border border-border2 bg-bg2 p-3">
      <div className="flex flex-wrap items-center gap-2"><Badge tone={stateTone(run.state)}>{run.state}</Badge><Badge>{run.runner_status}</Badge></div>
      <div className="mt-2 font-semibold text-fg1">{loop?.name ?? run.loop_id}</div>
      <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        <div><dt className="text-fg3">Tool contract</dt><dd className="font-semibold text-fg1">{run.plan.action.tool}</dd></div>
        <div><dt className="text-fg3">Approval</dt><dd className="font-semibold text-fg1">{run.requires_approval ? "Required" : "Policy-authorized"}</dd></div>
        <div><dt className="text-fg3">Validation probes</dt><dd className="font-semibold text-fg1">{run.plan.validation_probes.length}</dd></div>
        <div><dt className="text-fg3">Effectiveness probes</dt><dd className="font-semibold text-fg1">{run.plan.effectiveness_probes.length}</dd></div>
        {run.effectiveness_due_at ? <div><dt className="text-fg3">Effectiveness due</dt><dd className="font-semibold text-fg1">{new Date(run.effectiveness_due_at).toLocaleString()}</dd></div> : null}
      </dl>
      {run.last_error ? <div className="mt-3 text-sm text-danger">{run.last_error}</div> : null}
    </div>
  );
}

function RunOutput({ output, verified }: { output: Record<string, unknown>; verified: boolean }) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-fg1"><SquareTerminal className="h-4 w-4" aria-hidden="true" />{verified ? "Verified output" : "Action output, not effectiveness-proven"}</div>
      <pre className="max-h-80 overflow-auto rounded-panel border border-border2 bg-bg3 p-3 text-xs text-fg1">{JSON.stringify(output, null, 2)}</pre>
    </div>
  );
}

function EventTimeline({ events }: { events: AuthorityEvent[] }) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-fg1"><Radio className="h-4 w-4" aria-hidden="true" />Append-only event stream</div>
      {events.length ? <div className="max-h-96 space-y-2 overflow-auto" aria-live="polite">
        {events.map((event) => <div key={event.sequence} className="rounded-panel border border-border2 bg-bg1 p-2 text-xs"><span className="font-semibold text-fg1">{event.event_type}</span><span className="ml-2 text-fg3">#{event.sequence} {event.state}</span></div>)}
      </div> : <div className="rounded-panel border border-border2 bg-bg2 p-3 text-sm text-fg2">Follow the run to stream its durable events.</div>}
    </div>
  );
}

function stateTone(state: string): "success" | "warning" | "danger" | "brand" {
  if (state === "EFFECTIVENESS_PROVEN") return "success";
  if (["BLOCKED", "ROLLED_BACK", "EFFECTIVENESS_FAILED", "VALIDATION_FAILED", "PROOF_FAILED"].includes(state)) return "danger";
  if (["PLANNED", "EFFECTIVENESS_PENDING"].includes(state)) return "warning";
  return "brand";
}

function freshnessTone(status?: string): "success" | "warning" | "danger" | "neutral" {
  if (status === "fresh") return "success";
  if (status === "stale") return "danger";
  if (status === "missing") return "warning";
  return "neutral";
}

function verdictTone(verdict?: string): "success" | "warning" | "danger" | "neutral" {
  if (verdict === "GO") return "success";
  if (verdict === "REVIEW_REQUIRED") return "warning";
  if (verdict === "NO_GO") return "danger";
  return "neutral";
}

function ConnectorField({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder: string }) {
  return <label className="block"><span className="mb-1 block text-sm font-semibold text-fg1">{label}</span><input type="url" className="control min-h-10 w-full px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} /></label>;
}

function JsonField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="block"><span className="mb-1 block text-sm font-semibold text-fg1">{label}</span><textarea className="control min-h-20 w-full px-3 py-2 font-mono text-sm" value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

function parseObject(value: string, label: string): Record<string, unknown> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new Error(`${label} must be valid JSON.`);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error(`${label} must be a JSON object.`);
  return parsed as Record<string, unknown>;
}

function parseJsonValue(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function messageFor(reason: unknown): string {
  if (reason instanceof AuthorityError || reason instanceof Error) return reason.message;
  return "The governed execution authority could not complete the request.";
}
