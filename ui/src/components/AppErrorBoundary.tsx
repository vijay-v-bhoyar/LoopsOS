import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "./Button";
import { Card } from "./Card";
import { deploymentPosture } from "../lib/deployment";

interface State {
  failed: boolean;
  incidentId: string;
}

function createIncidentId(): string {
  return `ui-${Date.now().toString(36)}`;
}

export class AppErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false, incidentId: "" };

  static getDerivedStateFromError(): State {
    return { failed: true, incidentId: createIncidentId() };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("LoopOS UI boundary", { error, componentStack: info.componentStack, incidentId: this.state.incidentId });
  }

  componentDidMount() {
    window.addEventListener("loopos:test-boundary-failure", this.failClosed as EventListener);
  }

  componentWillUnmount() {
    window.removeEventListener("loopos:test-boundary-failure", this.failClosed as EventListener);
  }

  private failClosed = () => {
    this.setState({ failed: true, incidentId: createIncidentId() });
  };

  private recover = () => {
    window.history.replaceState({ looposView: "dashboard", looposDepth: 0 }, "", "#dashboard");
    this.setState({ failed: false, incidentId: "" });
  };

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="flex min-h-screen items-center justify-center bg-bg2 p-4">
        <Card className="w-full max-w-xl">
          <div className="flex items-start gap-3">
            <div className="rounded-panel bg-dangerBg p-3 text-danger"><AlertTriangle className="h-6 w-6" aria-hidden="true" /></div>
            <div>
              <h1 className="text-xl font-semibold text-fg1">LoopOS could not complete this screen</h1>
              <p className="mt-2 text-sm text-fg2">No readiness or approval result was recorded. Return to the dashboard and retry the operation.</p>
            </div>
          </div>
          <div className="mt-4 rounded-panel border border-border2 bg-bg2 p-3 text-sm text-fg2">
            Incident reference: <span className="font-semibold text-fg1">{this.state.incidentId}</span>
            {deploymentPosture.mode === "enterprise" && import.meta.env.VITE_LOOPOS_SUPPORT_CONTACT ? ` / ${import.meta.env.VITE_LOOPOS_SUPPORT_CONTACT}` : ""}
          </div>
          <Button variant="primary" className="mt-5" onClick={this.recover}>
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Return to dashboard
          </Button>
        </Card>
      </main>
    );
  }
}
