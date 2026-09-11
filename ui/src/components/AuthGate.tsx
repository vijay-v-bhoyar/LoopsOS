import { LoaderCircle, LogIn, ShieldCheck } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Button } from "./Button";
import { Card } from "./Card";
import { InlineNote } from "./Help";
import { deploymentPosture, DEPLOYMENT_STATUS_LABELS, type DeploymentPosture } from "../lib/deployment";
import type { EnterpriseSessionState } from "../lib/workspaceStore";
import type { EnterpriseUser, UserRole } from "../types";

const ROLES: UserRole[] = ["Executive", "Approver", "Operator", "Auditor"];

export function AuthGate({
  user,
  onSignIn,
  enterpriseSession = { status: "idle" },
  onEnterpriseSignIn = () => undefined,
  posture = deploymentPosture,
  children,
}: {
  user: EnterpriseUser | null;
  onSignIn: (name: string, email: string, role: UserRole) => void;
  enterpriseSession?: EnterpriseSessionState;
  onEnterpriseSignIn?: () => void;
  posture?: DeploymentPosture;
  children: ReactNode;
}) {
  const [name, setName] = useState("LoopOS Operator");
  const [email, setEmail] = useState("operator@example.local");
  const [role, setRole] = useState<UserRole>("Operator");

  const retryableEnterpriseFailure = posture.mode === "enterprise"
    && enterpriseSession.status === "error"
    && enterpriseSession.retryable === true;

  if (posture.mode === "enterprise" && !posture.enterpriseReady && !retryableEnterpriseFailure) {
    const pendingBindings = posture.bindings.filter((binding) => binding.status !== "bound");
    return (
      <main className="flex min-h-screen items-center justify-center bg-bg2 p-4">
        <Card className="w-full max-w-xl">
          <div className="mb-5 flex items-center gap-3">
            <div className="rounded-panel bg-dangerBg p-3 text-danger">
              <ShieldCheck className="h-6 w-6" aria-hidden="true" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-fg1">
                {posture.status === "activation_blocked" ? "Enterprise Activation Blocked" : "Enterprise Verification Required"}
              </h1>
              <p className="text-sm text-fg2">{DEPLOYMENT_STATUS_LABELS[posture.status]}</p>
            </div>
          </div>
          <InlineNote tone="warning">
            LoopOS will not start an enterprise session until every required production binding, including identity, persistence, audit, rate limiting, worker dispatch, restore evidence, and endpoint policy, is configured and verified.
          </InlineNote>
          <ul className="mt-5 space-y-2 text-sm text-fg2">
            {pendingBindings.map((binding) => (
              <li key={binding.id} className="rounded-panel border border-border2 bg-bg2 p-3">
                <span className="font-semibold text-fg1">{binding.label}:</span> {binding.detail}
              </li>
            ))}
          </ul>
        </Card>
      </main>
    );
  }

  if (posture.mode === "enterprise") {
    if (user && enterpriseSession.status === "ready") return <>{children}</>;
    const loading = enterpriseSession.status === "loading";
    const failed = enterpriseSession.status === "error";
    return (
      <main className="flex min-h-screen items-center justify-center bg-bg2 p-4">
        <Card className="w-full max-w-xl">
          <div className="mb-5 flex items-center gap-3">
            <div className="rounded-panel bg-brandSubtle p-3 text-brand">
              {loading
                ? <LoaderCircle className="h-6 w-6 animate-spin" aria-hidden="true" />
                : <ShieldCheck className="h-6 w-6" aria-hidden="true" />}
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-fg1">
                {loading ? "Verifying Enterprise Identity" : failed ? "Enterprise Sign-In Failed" : "Enterprise Sign-In Required"}
              </h1>
              <p className="text-sm text-fg2">Identity and role claims come only from the configured authority plane.</p>
            </div>
          </div>
          <InlineNote tone={failed ? "critical" : "info"}>
            {failed
              ? enterpriseSession.error ?? "The authority plane could not verify this identity."
              : loading
                ? "Loading the tenant-scoped identity and authoritative workspace register."
                : "Continue with the organization-managed identity session. Browser-selected roles are disabled."}
          </InlineNote>
          {!loading ? (
            <Button variant="primary" onClick={onEnterpriseSignIn} className="mt-5 w-full">
              <LogIn className="h-4 w-4" aria-hidden="true" />
              {failed ? "Retry Enterprise Sign-In" : "Verify Enterprise Identity"}
            </Button>
          ) : null}
        </Card>
      </main>
    );
  }

  if (user) return <>{children}</>;

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg2 p-4">
      <Card className="w-full max-w-xl">
        <div className="mb-5 flex items-center gap-3">
          <div className="rounded-panel bg-brandSubtle p-3 text-brand">
            <ShieldCheck className="h-6 w-6" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-fg1">LoopOS Evaluation Workspace</h1>
            <p className="text-sm text-fg2">Browser-local simulation for use-case analysis and workflow evaluation.</p>
          </div>
        </div>
        <InlineNote tone="warning">
          This is not enterprise sign-in. The selected role is a local simulation role and cannot authorize production actions.
        </InlineNote>
        <div className="mt-5 space-y-4">
          <label className="block">
            <span className="mb-1 block text-sm font-semibold text-fg1">Name</span>
            <input className="control min-h-10 w-full px-3 text-sm" value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-semibold text-fg1">Email</span>
            <input className="control min-h-10 w-full px-3 text-sm" value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-semibold text-fg1">Simulation role</span>
            <select className="control min-h-10 w-full px-3 text-sm" value={role} onChange={(event) => setRole(event.target.value as UserRole)}>
              {ROLES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <Button variant="primary" onClick={() => onSignIn(name, email, role)} className="w-full">
            <LogIn className="h-4 w-4" aria-hidden="true" />
            Enter Evaluation Workspace
          </Button>
        </div>
      </Card>
    </main>
  );
}
