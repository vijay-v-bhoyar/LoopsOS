from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol
from urllib.parse import urlparse

import httpx
import anyio
from pydantic import BaseModel, Field, HttpUrl, model_validator
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from .config import Settings
from .models import EvidenceRequest, ProbeSpec, ToolAction
from .store import AuthorityStore, Conflict
from .effect_budget import EffectBudget, EffectBudgetDenied, Reservation
from .connector_transport import ConnectorTransport, ConnectorAddressDenied, global_address


class ToolFailure(RuntimeError):
    code = "tool_failure"


class RetryableToolFailure(ToolFailure):
    code = "retryable_dependency_failure"


class TerminalToolFailure(ToolFailure):
    code = "terminal_dependency_failure"


class ExternalOutcomeUnknown(TerminalToolFailure):
    code = "external_outcome_unknown"


class ExternalEffectDenied(TerminalToolFailure):
    code = "external_effect_denied"


@dataclass(frozen=True)
class CredentialLease:
    """Server-only connector credential with an explicit, short-lived scope."""

    credential_ref: str
    tenant_id: str
    connector_ref: str
    action_class: str
    issued_at: float
    expires_at: float
    bearer_token: str = field(repr=False, compare=False)

    def validate(self, *, tenant_id: str, connector_ref: str, action_class: str, now: float | None = None) -> None:
        current = time.time() if now is None else now
        if not self.credential_ref or not self.bearer_token:
            raise TerminalToolFailure("Credential broker returned an unusable credential lease.")
        if self.tenant_id != tenant_id or self.connector_ref != connector_ref or self.action_class != action_class:
            raise TerminalToolFailure("Credential broker returned a credential outside the requested scope.")
        if self.issued_at > current or self.expires_at <= current or self.expires_at <= self.issued_at:
            raise TerminalToolFailure("Credential broker returned an expired or invalid credential lease.")


class CredentialBroker(Protocol):
    """Provider-neutral seam for workload-identity-backed credential injection."""

    def issue_lease(
        self,
        *,
        workload_identity_ref: str,
        tenant_id: str,
        connector_ref: str,
        action_class: str,
    ) -> CredentialLease:
        ...


class RecordActionArguments(BaseModel):
    operation: str = Field(default="apply", pattern=r"^(apply|compensate)$")
    summary: str = Field(default="Apply governed LoopOS action", min_length=1, max_length=2_000)
    outputs: list[str] = Field(default_factory=list, max_length=50)
    target_idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)

    @model_validator(mode="after")
    def compensation_has_target(self) -> "RecordActionArguments":
        if self.operation == "compensate" and not self.target_idempotency_key:
            raise ValueError("A compensating record action requires target_idempotency_key.")
        return self


class HttpActionArguments(BaseModel):
    endpoint: HttpUrl
    method: str = Field(pattern=r"^(POST|PUT|PATCH|DELETE)$")
    body: dict[str, Any] = Field(default_factory=dict)


def _json_path(value: Any, path: str) -> Any:
    current = value
    if not path:
        return current
    for segment in path.split("."):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        elif isinstance(current, list) and segment.isdigit() and int(segment) < len(current):
            current = current[int(segment)]
        else:
            raise KeyError(path)
    return current


class ToolRegistry:
    def __init__(
        self,
        settings: Settings,
        store: AuthorityStore,
        transport: httpx.AsyncBaseTransport | None = None,
        credential_broker: CredentialBroker | None = None,
        workload_identity_ref: str | None = None,
    ):
        self.settings = settings
        self.store = store
        self.effect_budget = EffectBudget(store, settings.effect_budget_policy)
        self.credential_broker = credential_broker
        self.workload_identity_ref = workload_identity_ref
        self.http = httpx.AsyncClient(
            transport=transport if transport is not None else ConnectorTransport(settings.allowed_http_hosts, settings.allow_dev_auth),
            trust_env=False,
            timeout=httpx.Timeout(settings.http_timeout_seconds),
            follow_redirects=False,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def close(self) -> None:
        await self.http.aclose()

    async def collect_evidence(self, tenant_id: str, run_id: str, request: EvidenceRequest) -> dict[str, Any]:
        if request.kind == "workspace_snapshot":
            content = request.content or {}
        else:
            content = await self._get_json(request.source_ref, tenant_id=tenant_id, action_class="evidence_read")
        return self.store.save_evidence(tenant_id, run_id, request.evidence_id, request.kind, request.source_ref, content, request.freshness_seconds)

    async def execute_action(self, tenant_id: str, run_id: str, action: ToolAction, max_attempts: int) -> dict[str, Any]:
        request = action.model_dump(mode="json")
        invocation_id, replay = self.store.begin_invocation(tenant_id, run_id, action.tool, action.idempotency_key, request)
        if replay is not None:
            return {**replay, "idempotent_replay": True}

        started_at = time.perf_counter()
        attempts = 0
        operation: Callable[[], Awaitable[dict[str, Any]]]
        reservation: Reservation | None = None
        try:
            if action.tool == "record_action":
                arguments = RecordActionArguments.model_validate(action.arguments)
                operation = lambda: self._record_action(tenant_id, run_id, action.idempotency_key, arguments)
            elif action.tool == "http_json_action":
                arguments = HttpActionArguments.model_validate(action.arguments)
                reservation = self.effect_budget.reserve(tenant_id, run_id, invocation_id, request)
                if reservation.replay is not None:
                    return {**reservation.replay, "idempotent_replay": True}
                operation = lambda: self._http_action(tenant_id, action.idempotency_key, invocation_id, run_id, arguments, reservation)
            else:
                raise TerminalToolFailure(f"Tool {action.tool} is not registered.")

            result: dict[str, Any] | None = None
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(min(max_attempts, self.settings.max_retry_attempts)),
                wait=wait_exponential_jitter(initial=self.settings.retry_wait_seconds, max=2.0),
                retry=retry_if_exception_type(RetryableToolFailure),
                reraise=True,
            ):
                with attempt:
                    attempt_number = attempt.retry_state.attempt_number
                    attempts = attempt_number
                    self.store.record_invocation_attempt(tenant_id, run_id, invocation_id, attempt_number)
                    result = await operation()
            if result is None:
                raise TerminalToolFailure("Tool returned no result.")
            self.store.complete_invocation(
                tenant_id,
                run_id,
                invocation_id,
                result,
                latency_ms=max(0, round((time.perf_counter() - started_at) * 1000)),
                retry_count=max(0, attempts - 1),
            )
            return result
        except ToolFailure as error:
            self._cancel_undispatched_reservation(reservation)
            self.store.fail_invocation(
                tenant_id,
                run_id,
                invocation_id,
                error.code,
                str(error),
                latency_ms=max(0, round((time.perf_counter() - started_at) * 1000)),
                retry_count=max(0, attempts - 1),
            )
            raise
        except Exception as error:
            self._cancel_undispatched_reservation(reservation)
            self.store.fail_invocation(
                tenant_id,
                run_id,
                invocation_id,
                "external_effect_denied" if isinstance(error, EffectBudgetDenied) else "invalid_tool_input",
                str(error),
                latency_ms=max(0, round((time.perf_counter() - started_at) * 1000)),
                retry_count=max(0, attempts - 1),
            )
            failure = ExternalEffectDenied if isinstance(error, EffectBudgetDenied) else TerminalToolFailure
            raise failure(str(error)) from error

    def _cancel_undispatched_reservation(self, reservation: Reservation | None) -> None:
        if reservation is not None:
            try:
                self.effect_budget.cancel_before_dispatch(reservation)
            except EffectBudgetDenied:
                # A dispatched/unknown effect remains charged; cancellation cannot refund it.
                pass

    async def run_probe(
        self,
        probe: ProbeSpec,
        action_output: dict[str, Any],
        evidence: list[dict[str, Any]],
        tenant_id: str | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        if probe.kind == "evidence_present":
            found = any(item.get("evidence_id") == probe.expected for item in evidence)
            return found, {"expected_evidence_id": probe.expected, "found": found}
        if probe.kind == "http_json_equals":
            if probe.endpoint is None:
                return False, {"error": "endpoint is required"}
            endpoint = str(probe.endpoint)
            document = await self._get_json(endpoint, tenant_id=tenant_id, action_class="probe_read")
            try:
                actual = _json_path(document, probe.path)
            except KeyError:
                return False, {"path": probe.path, "expected": probe.expected, "error": "path not found"}
            return actual == probe.expected, {"path": probe.path, "expected": probe.expected, "actual": actual}
        target = action_output if probe.target == "action_output" else {item["evidence_id"]: item.get("content") for item in evidence}
        try:
            actual = _json_path(target, probe.path)
        except KeyError:
            return False, {"path": probe.path, "expected": probe.expected, "error": "path not found"}
        return actual == probe.expected, {"path": probe.path, "expected": probe.expected, "actual": actual}

    async def _record_action(self, tenant_id: str, run_id: str, idempotency_key: str, arguments: RecordActionArguments) -> dict[str, Any]:
        if arguments.operation == "compensate":
            return self.store.compensate_action_artifact(tenant_id, arguments.target_idempotency_key or "")
        return self.store.save_action_artifact(
            tenant_id,
            run_id,
            idempotency_key,
            {"status": "applied", "summary": arguments.summary, "outputs": arguments.outputs},
        )

    async def _http_action(
        self,
        tenant_id: str,
        idempotency_key: str,
        invocation_id: str,
        run_id: str,
        arguments: HttpActionArguments,
        reservation: Reservation,
    ) -> dict[str, Any]:
        endpoint = str(arguments.endpoint)
        await self._validate_endpoint(endpoint)
        try:
            serialized_body = json.dumps(arguments.body, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError, OverflowError) as error:
            raise TerminalToolFailure("HTTP action body is not JSON serializable.") from error
        if not isinstance(self.settings.http_max_request_bytes, int) or self.settings.http_max_request_bytes <= 0:
            raise TerminalToolFailure("HTTP action request size limit is not configured.")
        if len(serialized_body) > self.settings.http_max_request_bytes:
            raise TerminalToolFailure("HTTP action request exceeds the configured size limit.")
        headers = {
            **self._connector_headers(endpoint, tenant_id=tenant_id, action_class="http_action"),
            "content-type": "application/json", "idempotency-key": idempotency_key,
            "x-loopos-run-id": run_id, "x-loopos-invocation-id": invocation_id,
        }
        self.effect_budget.dispatch(reservation)
        try:
            async with self.http.stream(
                arguments.method,
                endpoint,
                content=serialized_body,
                headers=headers,
            ) as response:
                if response.status_code == 429 or response.status_code >= 500:
                    raise TerminalToolFailure(f"External outcome requires reconciliation after HTTP {response.status_code}; no automatic redispatch.")
                if response.status_code >= 400:
                    raise TerminalToolFailure(f"Dependency returned {response.status_code}.")
                payload = await self._read_json(response)
        except BaseException as error:
            self.effect_budget.finish(reservation, None)
            if isinstance(error, Exception):
                raise ExternalOutcomeUnknown("External outcome is unknown; aggregate exposure retained for reconciliation.") from error
            raise
        result = {"status": "applied", "http_status": response.status_code, "response": payload}
        self.effect_budget.finish(reservation, result)
        return result

    async def _get_json(
        self,
        endpoint: str,
        *,
        tenant_id: str | None = None,
        action_class: str = "connector_read",
    ) -> dict[str, Any]:
        await self._validate_endpoint(endpoint)
        document: dict[str, Any] | None = None
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.settings.max_retry_attempts),
            wait=wait_exponential_jitter(initial=self.settings.retry_wait_seconds, max=2.0),
            retry=retry_if_exception_type(RetryableToolFailure),
            reraise=True,
        ):
            with attempt:
                try:
                    async with self.http.stream(
                        "GET",
                        endpoint,
                        headers=self._connector_headers(endpoint, tenant_id=tenant_id, action_class=action_class),
                    ) as response:
                        if response.status_code == 429 or response.status_code >= 500:
                            raise RetryableToolFailure(f"Dependency returned {response.status_code}.")
                        if response.status_code >= 400:
                            raise TerminalToolFailure(f"Dependency returned {response.status_code}.")
                        document = await self._read_json(response)
                except ConnectorAddressDenied as error:
                    raise TerminalToolFailure(str(error)) from error
                except (httpx.TimeoutException, httpx.NetworkError) as error:
                    raise RetryableToolFailure(str(error)) from error
        if document is None:
            raise TerminalToolFailure("Dependency returned no JSON document.")
        return document

    async def _read_json(self, response: httpx.Response) -> dict[str, Any]:
        if response.is_redirect:
            raise TerminalToolFailure("Redirect responses are not allowed.")
        chunks: list[bytes] = []
        content_length = 0
        async for chunk in response.aiter_bytes():
            content_length += len(chunk)
            if content_length > self.settings.http_max_response_bytes:
                raise TerminalToolFailure("Response exceeds the configured size limit.")
            chunks.append(chunk)
        content = b"".join(chunks)
        try:
            value = json.loads(content)
        except (TypeError, ValueError) as error:
            raise TerminalToolFailure("Response is not valid JSON.") from error
        if not isinstance(value, dict):
            raise TerminalToolFailure("Response must be a JSON object.")
        return value

    async def _validate_endpoint(self, endpoint: str) -> None:
        parsed = urlparse(endpoint)
        hostname = (parsed.hostname or "").lower()
        if parsed.username or parsed.password or "\\" in endpoint:
            raise TerminalToolFailure("Connector endpoints cannot contain embedded credentials.")
        if "?" in endpoint or "#" in endpoint:
            raise TerminalToolFailure("Connector endpoints cannot contain query strings or fragments.")
        if parsed.scheme != "https" and not (self.settings.allow_dev_auth and parsed.scheme == "http" and hostname in {"localhost", "127.0.0.1"}):
            raise TerminalToolFailure("Enterprise connector endpoints must use HTTPS.")
        if hostname not in self.settings.allowed_http_hosts:
            raise TerminalToolFailure(f"Connector host {hostname or '<missing>'} is not allowlisted.")
        if self.settings.allow_dev_auth and hostname in {"localhost", "127.0.0.1"}:
            return
        try:
            with anyio.fail_after(self.settings.http_timeout_seconds):
                answers = await anyio.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
                addresses = {item[4][0] for item in answers}
        except TimeoutError as error:
            raise RetryableToolFailure("Connector DNS validation timed out.") from error
        except socket.gaierror as error:
            raise RetryableToolFailure(f"Connector host {hostname} cannot be resolved.") from error
        if not addresses:
            raise TerminalToolFailure("Connector DNS returned no addresses.")
        for address in addresses:
            if not global_address(address):
                raise TerminalToolFailure("Connector endpoints cannot resolve to private, reserved, or non-global addresses.")

    def _connector_headers(
        self,
        endpoint: str,
        *,
        tenant_id: str | None = None,
        action_class: str = "connector_read",
    ) -> dict[str, str]:
        hostname = (urlparse(endpoint).hostname or "").lower()
        headers = {"accept": "application/json", "user-agent": "LoopOS-Authority/0.1"}
        token = (self.settings.connector_bearer_tokens or {}).get(hostname)
        if self.credential_broker is None:
            if token and not self.settings.allow_dev_auth:
                raise TerminalToolFailure(
                    "Production connector credentials require an approved short-lived credential injection broker; static bearer tokens are not supported."
                )
            if not self.settings.allow_dev_auth:
                raise TerminalToolFailure(
                    "Production connector requests require an approved short-lived credential injection broker."
                )
            if token:
                headers["authorization"] = f"Bearer {token}"
            return headers
        if not tenant_id or not self.workload_identity_ref:
            raise TerminalToolFailure("Credential broker requests require tenant and workload identity scope.")
        try:
            lease = self.credential_broker.issue_lease(
                workload_identity_ref=self.workload_identity_ref,
                tenant_id=tenant_id,
                connector_ref=hostname,
                action_class=action_class,
            )
        except TerminalToolFailure:
            raise
        except Exception as error:
            raise TerminalToolFailure("Credential broker could not issue a connector credential lease.") from error
        if not isinstance(lease, CredentialLease):
            raise TerminalToolFailure("Credential broker returned an invalid credential lease.")
        lease.validate(
            tenant_id=tenant_id,
            connector_ref=hostname,
            action_class=action_class,
        )
        headers["authorization"] = f"Bearer {lease.bearer_token}"
        return headers
