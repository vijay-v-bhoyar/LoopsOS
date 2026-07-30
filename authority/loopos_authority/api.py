from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import IdentityVerifier, InvalidSession, SessionSigner
from .audit_anchor import AuditAnchorDispatcher
from .config import Settings, operational_binding_fingerprint, operational_binding_status
from .corpus import Corpus
from .engine import ExecutionEngine
from .identity import OIDCIdentityVerifier
from .models import Actor, ApprovalRequest, AuditVerification, ConnectorEventRecord, ConnectorEventRequest, CreateReleaseInitiativeRequest, CreateRunRequest, DevSessionRequest, ReleaseInitiativeRecord, ReleaseProofPack, RunCommandResponse, RunRecord, SessionResponse, WorkspaceDocumentRequest, WorkspaceRecord
from .persistence import create_authority_store
from .store import Conflict, Forbidden, NotFound
from .tools import ToolRegistry
from .worker import ExecutionJobWorker


def create_app(
    settings: Settings | None = None,
    transport=None,
    identity_verifier: IdentityVerifier | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    if identity_verifier is None and settings.oidc_issuer and settings.oidc_audience and settings.oidc_jwks_url and settings.oidc_role_mapping:
        identity_verifier = OIDCIdentityVerifier(
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            jwks_url=settings.oidc_jwks_url,
            tenant_claim=settings.oidc_tenant_claim,
            role_claim=settings.oidc_role_claim,
            role_mapping=settings.oidc_role_mapping,
        )
    corpus = Corpus.load(settings.repo_root)
    store = create_authority_store(settings, corpus)
    tools = ToolRegistry(settings, store, transport=transport)
    engine = ExecutionEngine(corpus, store, tools)
    execution_worker = ExecutionJobWorker(
        store,
        engine,
        worker_id=f"worker-{uuid.uuid4()}",
        lease_seconds=settings.execution_job_lease_seconds,
        max_attempts=settings.execution_job_max_attempts,
    )
    audit_anchor = AuditAnchorDispatcher(
        store,
        settings.audit_anchor_url,
        settings.audit_anchor_hmac_secret,
        transport=transport,
        timeout_seconds=settings.http_timeout_seconds,
    ) if settings.audit_anchor_url and settings.audit_anchor_hmac_secret else None
    signer = SessionSigner(settings.session_secret)
    bearer = HTTPBearer(auto_error=False)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        store.requeue_incomplete_runs()
        async def schedule_execution_jobs() -> None:
            while True:
                store.queue_due_effectiveness()
                await execution_worker.run_once(dispatch_source="internal")
                await asyncio.sleep(settings.execution_worker_poll_seconds)
        execution_worker_task = (
            asyncio.create_task(schedule_execution_jobs())
            if settings.execution_worker_mode == "internal"
            else None
        )
        if execution_worker_task:
            await asyncio.sleep(0)
        async def schedule_audit_anchors() -> None:
            if audit_anchor is None:
                return
            while True:
                await audit_anchor.drain()
                await asyncio.sleep(settings.audit_anchor_poll_seconds)
        audit_anchor_task = asyncio.create_task(schedule_audit_anchors()) if audit_anchor else None
        yield
        if execution_worker_task:
            execution_worker_task.cancel()
        if audit_anchor_task:
            audit_anchor_task.cancel()
        if execution_worker_task:
            await asyncio.gather(execution_worker_task, return_exceptions=True)
        if audit_anchor_task:
            await asyncio.gather(audit_anchor_task, return_exceptions=True)
        if audit_anchor:
            await audit_anchor.close()
        await tools.close()
        store.close()

    app = FastAPI(
        title="LoopOS Governed Execution Authority",
        version="0.1.0",
        docs_url="/docs" if settings.allow_dev_auth else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.corpus = corpus
    app.state.store = store
    app.state.engine = engine
    app.state.execution_worker = execution_worker
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["DELETE", "GET", "POST", "PUT"],
        allow_headers=["authorization", "content-type", "idempotency-key", "if-match", "if-none-match", "last-event-id"],
        expose_headers=["etag"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or f"request-{uuid.uuid4()}"
        response = await call_next(request)
        response.headers["cache-control"] = "no-store"
        response.headers["content-security-policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["permissions-policy"] = "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
        response.headers["referrer-policy"] = "no-referrer"
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["x-frame-options"] = "DENY"
        response.headers["x-request-id"] = request_id
        return response

    async def current_actor(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Actor:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="A bearer session is required.")
        try:
            return signer.verify(credentials.credentials)
        except InvalidSession as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error

    def map_store_error(error: Exception) -> HTTPException:
        if isinstance(error, NotFound):
            return HTTPException(status_code=404, detail=str(error))
        if isinstance(error, Forbidden):
            return HTTPException(status_code=403, detail=str(error))
        if isinstance(error, Conflict):
            return HTTPException(status_code=409, detail=str(error))
        return HTTPException(status_code=500, detail="The authority service could not persist the operation.")

    def parse_revision(value: str | None) -> int:
        if value is None:
            raise HTTPException(status_code=428, detail="A current If-Match revision is required.")
        normalized = value.strip()
        if len(normalized) >= 2 and normalized[0] == normalized[-1] == '"':
            normalized = normalized[1:-1]
        try:
            revision = int(normalized)
        except ValueError as error:
            raise HTTPException(status_code=400, detail="If-Match must contain a quoted non-negative revision.") from error
        if revision < 0:
            raise HTTPException(status_code=400, detail="If-Match must contain a quoted non-negative revision.")
        return revision

    def webhook_secret(tenant_id: str, system: str) -> str:
        secrets = settings.webhook_secrets or {}
        secret = secrets.get(f"{tenant_id}:{system}") or secrets.get(system)
        if not secret:
            raise HTTPException(status_code=403, detail="Webhook secret is not configured.")
        return secret

    def verify_hmac_signature(system: str, body: bytes, secret: str, headers) -> str:
        expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        if system == "github":
            supplied = headers.get("x-hub-signature-256", "")
            prefix = "sha256="
        else:
            supplied = headers.get("x-loopos-signature-256", "") or headers.get("x-hub-signature-256", "")
            prefix = "sha256="
        if not supplied.startswith(prefix) or not hmac.compare_digest(supplied[len(prefix):], expected):
            raise HTTPException(status_code=403, detail="Webhook signature verification failed.")
        return hashlib.sha256(body).hexdigest()

    def normalize_webhook_event(system: str, workspace_id: str, payload: dict[str, object], headers, payload_hash: str) -> ConnectorEventRequest:
        if system == "github":
            event_name = headers.get("x-github-event", "manual_note")
            delivery_id = headers.get("x-github-delivery")
            repository = payload.get("repository") if isinstance(payload.get("repository"), dict) else {}
            pull_request = payload.get("pull_request") if isinstance(payload.get("pull_request"), dict) else {}
            workflow_run = payload.get("workflow_run") if isinstance(payload.get("workflow_run"), dict) else {}
            check_run = payload.get("check_run") if isinstance(payload.get("check_run"), dict) else {}
            release = payload.get("release") if isinstance(payload.get("release"), dict) else {}
            external_id = str(pull_request.get("html_url") or workflow_run.get("html_url") or check_run.get("html_url") or release.get("html_url") or delivery_id or payload_hash)
            label = str(pull_request.get("title") or workflow_run.get("name") or check_run.get("name") or release.get("name") or repository.get("full_name") or event_name)
            event_kind = {
                "pull_request": "pull_request",
                "check_run": "check",
                "workflow_run": "workflow",
                "release": "release",
                "deployment": "deployment",
                "push": "commit",
            }.get(event_name, "manual_note")
            url = str(pull_request.get("html_url") or workflow_run.get("html_url") or check_run.get("html_url") or release.get("html_url") or repository.get("html_url") or "")
        else:
            event_name = headers.get("x-atlassian-webhook-identifier", "jira-webhook")
            issue = payload.get("issue") if isinstance(payload.get("issue"), dict) else {}
            fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
            external_id = str(issue.get("key") or event_name or payload_hash)
            label = str(fields.get("summary") or payload.get("webhookEvent") or external_id)
            event_kind = "issue" if issue else "release"
            url = ""
            delivery_id = event_name
        return ConnectorEventRequest(
            workspace_id=workspace_id,
            system=system,  # type: ignore[arg-type]
            event_kind=event_kind,  # type: ignore[arg-type]
            external_id=external_id,
            label=label,
            url=url or None,
            observed_at=datetime.now(timezone.utc).isoformat(),
            payload=payload,
            verification_status="verified_webhook",
            delivery_id=delivery_id,
        )

    @app.get("/health/live")
    async def liveness() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/health/ready")
    async def readiness() -> dict[str, object]:
        if not settings.allow_dev_auth and identity_verifier is None:
            raise HTTPException(status_code=503, detail="Production identity is not configured.")
        if not settings.allow_dev_auth and settings.storage_backend != "postgres":
            raise HTTPException(status_code=503, detail="Production persistence must use Postgres.")
        if not settings.allow_dev_auth and audit_anchor is None:
            raise HTTPException(status_code=503, detail="Production audit anchoring is not configured.")
        try:
            store.connection.execute("SELECT 1").fetchone()
            worker_dispatch = store.operational_signal_status(
                "execution_worker_dispatch",
                settings.execution_worker_heartbeat_max_age_seconds,
                required_source=settings.execution_worker_mode,
            )
            operational_bindings = operational_binding_status(settings)
            operational_bindings["worker_dispatch_verified"] = bool(
                operational_bindings["worker_dispatch_verified"] and worker_dispatch["verified"]
            )
            operational_binding_names = {
                "retention_verified": "retention_policy",
                "support_verified": "support_contact",
                "outbound_policy_verified": "outbound_policy",
                "backup_restore_verified": "backup_restore",
                "worker_dispatch_verified": "worker_dispatch",
            }
            missing_operational_bindings = [
                operational_binding_names[name]
                for name, verified in operational_bindings.items()
                if not verified
            ]
            if not settings.allow_dev_auth and missing_operational_bindings:
                raise HTTPException(
                    status_code=503,
                    detail=f"Production operational bindings are incomplete: {', '.join(missing_operational_bindings)}.",
                )
            anchor_backlog = store.audit_anchor_backlog()
            if not settings.allow_dev_auth and anchor_backlog:
                raise HTTPException(status_code=503, detail=f"Production audit anchor backlog contains {anchor_backlog} event(s).")
            anchor_delivery = store.audit_anchor_delivery_status()
            if not settings.allow_dev_auth and not anchor_delivery["verified"]:
                raise HTTPException(status_code=503, detail="Production audit anchoring has not completed a verified delivery.")
            return {
                "status": "ready",
                "loops": len(corpus.loop_descriptors),
                "state_machine_invariant": corpus.state_machine["invariant"],
                "standard_hash": corpus.standard_hash,
                "development_auth": settings.allow_dev_auth,
                "production_identity": identity_verifier is not None,
                "storage_backend": settings.storage_backend,
                "audit_anchor_configured": audit_anchor is not None,
                "audit_anchor_backlog": anchor_backlog,
                "audit_anchor_delivery_verified": anchor_delivery["verified"],
                "audit_anchor_last_delivered_at": anchor_delivery["last_delivered_at"],
                "execution_job_backlog": store.execution_job_backlog(),
                "execution_worker_dispatch": worker_dispatch,
                "operational_bindings": operational_bindings,
                "backup_restore_evidence": {
                    "url": settings.backup_restore_evidence_url,
                    "sha256": settings.backup_restore_evidence_sha256,
                    "verified_at": settings.backup_restore_verified_at,
                },
                "operational_evidence": {
                    "url": settings.operational_evidence_url,
                    "sha256": settings.operational_evidence_sha256,
                    "verified_at": settings.operational_evidence_verified_at,
                    "binding_fingerprint": operational_binding_fingerprint(settings),
                },
            }
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(status_code=503, detail="Authority persistence is unavailable.") from error

    if settings.allow_dev_auth:
        @app.post("/v1/dev/sessions", response_model=SessionResponse)
        async def create_dev_session(request: DevSessionRequest) -> SessionResponse:
            actor = Actor.model_validate(request.model_dump(exclude={"ttl_seconds"}))
            return SessionResponse(access_token=signer.issue(actor, request.ttl_seconds), expires_in=request.ttl_seconds, actor=actor)

    @app.post("/v1/sessions", response_model=SessionResponse)
    async def create_enterprise_session(request: Request) -> SessionResponse:
        if identity_verifier is None:
            raise HTTPException(status_code=503, detail="Production identity is not configured.")
        assertion = request.headers.get("x-loopos-identity-token") or request.cookies.get("loopos_identity")
        if not assertion:
            raise HTTPException(status_code=401, detail="A verified identity assertion is required.")
        try:
            actor = identity_verifier.verify(assertion)
        except Exception as error:
            raise HTTPException(status_code=401, detail="Identity assertion verification failed.") from error
        store.append_event(
            actor.tenant_id,
            None,
            "ENTERPRISE_SESSION_ISSUED",
            None,
            actor.user_id,
            {"role": actor.role},
        )
        if audit_anchor:
            await audit_anchor.drain()
        ttl_seconds = 900
        return SessionResponse(
            access_token=signer.issue(actor, ttl_seconds),
            expires_in=ttl_seconds,
            actor=actor,
        )

    @app.get("/v1/session", response_model=Actor)
    async def session(actor: Actor = Depends(current_actor)) -> Actor:
        return actor

    @app.get("/v1/workspaces", response_model=list[WorkspaceRecord])
    async def list_workspaces(
        limit: int = Query(default=100, ge=1, le=200),
        actor: Actor = Depends(current_actor),
    ) -> list[WorkspaceRecord]:
        return store.list_workspaces(actor.tenant_id, limit)

    @app.get("/v1/workspaces/{workspace_id}", response_model=WorkspaceRecord)
    async def get_workspace(workspace_id: str, actor: Actor = Depends(current_actor)) -> WorkspaceRecord:
        try:
            return store.get_workspace(actor.tenant_id, workspace_id)
        except Exception as error:
            raise map_store_error(error) from error

    @app.put("/v1/workspaces/{workspace_id}", response_model=WorkspaceRecord)
    async def put_workspace(
        workspace_id: str,
        request: WorkspaceDocumentRequest,
        response: Response,
        actor: Actor = Depends(current_actor),
        if_match: str | None = Header(default=None, alias="If-Match"),
        if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    ) -> WorkspaceRecord:
        if actor.role == "Auditor":
            raise HTTPException(status_code=403, detail="Auditors cannot modify workspaces.")
        if request.document.get("workspace_id") != workspace_id:
            raise HTTPException(status_code=400, detail="Workspace document ID must match the request path.")
        create_only = if_none_match == "*"
        if create_only == (if_match is not None):
            raise HTTPException(status_code=428, detail="Use If-None-Match: * to create or If-Match with the current revision to update.")
        expected_revision = None if create_only else parse_revision(if_match)
        try:
            record, created = store.put_workspace(
                actor,
                workspace_id,
                request.document,
                expected_revision=expected_revision,
                create_only=create_only,
            )
        except Exception as error:
            raise map_store_error(error) from error
        response.status_code = 201 if created else 200
        response.headers["etag"] = f'"{record.revision}"'
        return record

    @app.delete("/v1/workspaces/{workspace_id}", status_code=204)
    async def delete_workspace(
        workspace_id: str,
        actor: Actor = Depends(current_actor),
        if_match: str | None = Header(default=None, alias="If-Match"),
    ) -> Response:
        if actor.role == "Auditor":
            raise HTTPException(status_code=403, detail="Auditors cannot delete workspaces.")
        try:
            store.delete_workspace(actor, workspace_id, parse_revision(if_match))
        except HTTPException:
            raise
        except Exception as error:
            raise map_store_error(error) from error
        return Response(status_code=204)

    @app.post("/v1/runs", response_model=RunRecord, status_code=201)
    async def create_run(
        request: CreateRunRequest,
        actor: Actor = Depends(current_actor),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> RunRecord:
        if actor.role not in {"Operator", "Approver", "Executive"}:
            raise HTTPException(status_code=403, detail="Auditors cannot create execution runs.")
        if not idempotency_key or len(idempotency_key) < 8 or len(idempotency_key) > 200:
            raise HTTPException(status_code=400, detail="Idempotency-Key must contain 8 to 200 characters.")
        try:
            return store.create_run(actor, request, idempotency_key)
        except Exception as error:
            raise map_store_error(error) from error

    @app.get("/v1/runs", response_model=list[RunRecord])
    async def list_runs(
        workspace_id: str | None = Query(default=None, max_length=160),
        limit: int = Query(default=100, ge=1, le=200),
        actor: Actor = Depends(current_actor),
    ) -> list[RunRecord]:
        return store.list_runs(actor.tenant_id, workspace_id, limit)

    @app.post("/v1/release-initiatives", response_model=ReleaseInitiativeRecord, status_code=201)
    async def create_release_initiative(
        request: CreateReleaseInitiativeRequest,
        actor: Actor = Depends(current_actor),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> ReleaseInitiativeRecord:
        if actor.role not in {"Operator", "Approver", "Executive"}:
            raise HTTPException(status_code=403, detail="Auditors cannot create release initiatives.")
        if not idempotency_key or len(idempotency_key) < 8 or len(idempotency_key) > 200:
            raise HTTPException(status_code=400, detail="Idempotency-Key must contain 8 to 200 characters.")
        try:
            return store.create_release_initiative(actor, request, idempotency_key)
        except Exception as error:
            raise map_store_error(error) from error

    @app.get("/v1/release-initiatives", response_model=list[ReleaseInitiativeRecord])
    async def list_release_initiatives(
        workspace_id: str | None = Query(default=None, max_length=160),
        limit: int = Query(default=100, ge=1, le=200),
        actor: Actor = Depends(current_actor),
    ) -> list[ReleaseInitiativeRecord]:
        return store.list_release_initiatives(actor.tenant_id, workspace_id, limit)

    @app.get("/v1/release-initiatives/{initiative_id}/proof-pack", response_model=ReleaseProofPack)
    async def release_proof_pack(initiative_id: str, actor: Actor = Depends(current_actor)) -> ReleaseProofPack:
        try:
            return store.build_release_proof_pack(actor.tenant_id, initiative_id, actor.user_id)
        except Exception as error:
            raise map_store_error(error) from error

    @app.get("/v1/runs/{run_id}", response_model=RunRecord)
    async def get_run(run_id: str, actor: Actor = Depends(current_actor)) -> RunRecord:
        try:
            return store.get_run(actor.tenant_id, run_id)
        except Exception as error:
            raise map_store_error(error) from error

    @app.post("/v1/connector-events", response_model=ConnectorEventRecord, status_code=201)
    async def record_connector_event(request: ConnectorEventRequest, actor: Actor = Depends(current_actor)) -> ConnectorEventRecord:
        if actor.role not in {"Operator", "Approver", "Executive"}:
            raise HTTPException(status_code=403, detail="Auditors cannot record connector events.")
        try:
            return store.record_connector_event(actor, request)
        except Exception as error:
            raise map_store_error(error) from error

    @app.get("/v1/connector-events", response_model=list[ConnectorEventRecord])
    async def list_connector_events(
        workspace_id: str | None = Query(default=None, max_length=160),
        limit: int = Query(default=100, ge=1, le=200),
        actor: Actor = Depends(current_actor),
    ) -> list[ConnectorEventRecord]:
        return store.list_connector_events(actor.tenant_id, workspace_id, limit)

    @app.post("/v1/webhooks/{tenant_id}/{system}", response_model=ConnectorEventRecord, status_code=201)
    async def ingest_connector_webhook(
        tenant_id: str,
        system: str,
        request: Request,
        workspace_id: str = Query(min_length=1, max_length=160),
    ) -> ConnectorEventRecord:
        normalized_system = system.lower()
        if normalized_system not in {"github", "jira"}:
            raise HTTPException(status_code=404, detail="Unsupported webhook system.")
        body = await request.body()
        if len(body) > settings.http_max_response_bytes:
            raise HTTPException(status_code=413, detail="Webhook payload exceeds the configured size limit.")
        secret = webhook_secret(tenant_id, normalized_system)
        payload_hash = verify_hmac_signature(normalized_system, body, secret, request.headers)
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise HTTPException(status_code=400, detail="Webhook payload must be JSON.") from error
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Webhook payload must be a JSON object.")
        actor = Actor(tenant_id=tenant_id, user_id=f"{normalized_system}-webhook", name=f"{normalized_system.title()} Webhook", role="Operator")
        try:
            event_request = normalize_webhook_event(normalized_system, workspace_id, payload, request.headers, payload_hash)
            return store.record_connector_event(actor, event_request)
        except Exception as error:
            raise map_store_error(error) from error

    @app.post("/v1/runs/{run_id}/start", response_model=RunCommandResponse, status_code=202)
    async def start_run(run_id: str, actor: Actor = Depends(current_actor)) -> RunCommandResponse:
        if actor.role not in {"Operator", "Approver", "Executive"}:
            raise HTTPException(status_code=403, detail="Auditors cannot start execution.")
        try:
            run = store.queue_run(actor.tenant_id, run_id, actor.user_id)
            return RunCommandResponse(run_id=run_id, state=run.state, runner_status="queued")
        except Exception as error:
            raise map_store_error(error) from error

    @app.post("/v1/runs/{run_id}/approve")
    async def approve_run(run_id: str, request: ApprovalRequest, actor: Actor = Depends(current_actor)) -> dict[str, str]:
        try:
            approval_id = store.approve(actor, run_id, request)
            return {"approval_id": approval_id, "status": "approved"}
        except Exception as error:
            raise map_store_error(error) from error

    @app.post("/v1/runs/{run_id}/reject")
    async def reject_run(run_id: str, request: ApprovalRequest, actor: Actor = Depends(current_actor)) -> dict[str, str]:
        try:
            decision_id = store.reject(actor, run_id, request)
            return {"decision_id": decision_id, "status": "rejected"}
        except Exception as error:
            raise map_store_error(error) from error

    @app.post("/v1/runs/{run_id}/rollback", response_model=RunCommandResponse, status_code=202)
    async def rollback_run(run_id: str, actor: Actor = Depends(current_actor)) -> RunCommandResponse:
        if actor.role not in {"Approver", "Executive"}:
            raise HTTPException(status_code=403, detail="Rollback requires Approver or Executive authority.")
        try:
            run = store.get_run(actor.tenant_id, run_id)
            if run.plan.rollback is None:
                raise Conflict("This run has no compensating action contract.")
            if not corpus.allows_transition(run.state, "ROLLED_BACK"):
                raise Conflict(f"Run cannot roll back from {run.state}.")
            store.queue_run(
                actor.tenant_id,
                run_id,
                actor.user_id,
                "rollback",
                {"reason": f"Manual rollback requested by {actor.user_id}."},
            )
            return RunCommandResponse(run_id=run_id, state=run.state, runner_status="queued")
        except Exception as error:
            raise map_store_error(error) from error

    @app.post("/v1/runs/{run_id}/recover", response_model=RunRecord, status_code=201)
    async def recover_run(
        run_id: str,
        actor: Actor = Depends(current_actor),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> RunRecord:
        if actor.role not in {"Operator", "Approver", "Executive"}:
            raise HTTPException(status_code=403, detail="Auditors cannot recover execution.")
        if not idempotency_key or len(idempotency_key) < 8:
            raise HTTPException(status_code=400, detail="Recovery requires an Idempotency-Key.")
        try:
            previous = store.get_run(actor.tenant_id, run_id)
            if not corpus.is_terminal(previous.state) and previous.runner_status not in {"failed", "rolled_back"}:
                raise Conflict("Only terminal or failed runs can be recovered.")
            recovery_operation_id = str(uuid.uuid4())
            recovery_action = previous.plan.action.model_copy(update={"idempotency_key": f"recovery-action-{recovery_operation_id}"})
            recovery_rollback = previous.plan.rollback.model_copy(update={"idempotency_key": f"recovery-rollback-{recovery_operation_id}"}) if previous.plan.rollback else None
            recovery_plan = previous.plan.model_copy(update={"action": recovery_action, "rollback": recovery_rollback})
            request = CreateRunRequest(
                workspace_id=previous.workspace_id,
                loop_id=previous.loop_id,
                title=f"Recovery: {previous.title}",
                trigger=f"Recovery of {previous.run_id}: {previous.last_error or previous.state}",
                requested_risk_tier=previous.risk_tier,
                plan=recovery_plan,
            )
            return store.create_run(actor, request, idempotency_key, recovery_of=previous.run_id)
        except Exception as error:
            raise map_store_error(error) from error

    @app.get("/v1/runs/{run_id}/evidence")
    async def run_evidence(run_id: str, actor: Actor = Depends(current_actor)) -> list[dict[str, object]]:
        try:
            store.get_run(actor.tenant_id, run_id)
            return store.list_evidence(actor.tenant_id, run_id)
        except Exception as error:
            raise map_store_error(error) from error

    @app.get("/v1/runs/{run_id}/events")
    async def run_events(
        run_id: str,
        request: Request,
        after: int = Query(default=0, ge=0),
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
        actor: Actor = Depends(current_actor),
    ) -> StreamingResponse:
        try:
            store.get_run(actor.tenant_id, run_id)
        except Exception as error:
            raise map_store_error(error) from error
        try:
            cursor = max(after, int(last_event_id or 0))
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Last-Event-ID must be a non-negative integer.") from error
        if cursor < 0:
            raise HTTPException(status_code=400, detail="Last-Event-ID must be a non-negative integer.")

        async def stream() -> AsyncIterator[str]:
            nonlocal cursor
            idle_polls = 0
            while not await request.is_disconnected():
                events = store.events_after(actor.tenant_id, run_id, cursor)
                if events:
                    idle_polls = 0
                    for event in events:
                        cursor = int(event["sequence"])
                        data = {key: value for key, value in event.items() if key != "payload_json"}
                        yield f"id: {cursor}\nevent: {event['event_type']}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"
                else:
                    idle_polls += 1
                    current = store.get_run(actor.tenant_id, run_id)
                    if corpus.is_terminal(current.state) and idle_polls >= 2:
                        break
                    if idle_polls % 20 == 0:
                        yield ": keepalive\n\n"
                await asyncio.sleep(settings.event_poll_seconds)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    @app.get("/v1/audit/verify", response_model=AuditVerification)
    async def verify_audit(actor: Actor = Depends(current_actor)) -> AuditVerification:
        if actor.role not in {"Auditor", "Executive"}:
            raise HTTPException(status_code=403, detail="Audit verification requires Auditor or Executive authority.")
        valid, count, invalid = store.verify_audit_chain(actor.tenant_id)
        return AuditVerification(tenant_id=actor.tenant_id, valid=valid, event_count=count, first_invalid_sequence=invalid)

    @app.get("/v1/events")
    async def tenant_events(
        after: int = Query(default=0, ge=0),
        limit: int = Query(default=200, ge=1, le=500),
        actor: Actor = Depends(current_actor),
    ) -> list[dict[str, object]]:
        if actor.role not in {"Auditor", "Executive"}:
            raise HTTPException(status_code=403, detail="Audit event access requires Auditor or Executive authority.")
        return store.events_after(actor.tenant_id, None, after, limit)

    @app.get("/v1/audit/anchors/status")
    async def audit_anchor_status(actor: Actor = Depends(current_actor)) -> dict[str, object]:
        if actor.role not in {"Auditor", "Executive"}:
            raise HTTPException(status_code=403, detail="Audit anchor status requires Auditor or Executive role.")
        return {
            "configured": audit_anchor is not None,
            "backlog": store.audit_anchor_backlog(),
        }

    @app.post("/v1/audit/anchors/drain")
    async def drain_audit_anchors(actor: Actor = Depends(current_actor)) -> dict[str, int]:
        if actor.role != "Executive":
            raise HTTPException(status_code=403, detail="Audit anchor delivery requires Executive role.")
        if audit_anchor is None:
            raise HTTPException(status_code=503, detail="External audit anchoring is not configured.")
        delivered = await audit_anchor.drain()
        return {"delivered": delivered, "backlog": store.audit_anchor_backlog()}

    @app.get("/v1/operations/jobs/status")
    async def execution_job_status(actor: Actor = Depends(current_actor)) -> dict[str, object]:
        if actor.role not in {"Auditor", "Executive"}:
            raise HTTPException(status_code=403, detail="Execution job status requires Auditor or Executive role.")
        return {
            "backlog": store.execution_job_backlog(),
            "dispatch": store.operational_signal_status(
                "execution_worker_dispatch",
                settings.execution_worker_heartbeat_max_age_seconds,
                required_source=settings.execution_worker_mode,
            ),
        }

    @app.post("/v1/operations/jobs/drain")
    async def drain_execution_jobs(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> dict[str, object]:
        supplied_worker_token = request.headers.get("x-loopos-worker-token")
        if not supplied_worker_token and credentials and credentials.scheme.lower() == "bearer":
            supplied_worker_token = credentials.credentials
        worker_authorized = bool(
            settings.worker_token
            and supplied_worker_token
            and hmac.compare_digest(supplied_worker_token, settings.worker_token)
        )
        if not worker_authorized:
            if credentials is None or credentials.scheme.lower() != "bearer":
                raise HTTPException(status_code=401, detail="Worker token or Executive session is required.")
            try:
                actor = signer.verify(credentials.credentials)
            except InvalidSession as error:
                raise HTTPException(status_code=401, detail=str(error)) from error
            if actor.role != "Executive":
                raise HTTPException(status_code=403, detail="Execution job drain requires Executive role.")
        store.queue_due_effectiveness()
        processed = await execution_worker.run_once(dispatch_source="external")
        audit_delivered = await audit_anchor.drain() if audit_anchor else 0
        return {
            "processed": processed,
            "backlog": store.execution_job_backlog(),
            "dispatch": store.operational_signal_status(
                "execution_worker_dispatch",
                settings.execution_worker_heartbeat_max_age_seconds,
                required_source=settings.execution_worker_mode,
            ),
            "audit_delivered": audit_delivered,
            "audit_backlog": store.audit_anchor_backlog(),
        }

    return app


app = create_app()
