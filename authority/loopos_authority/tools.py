from __future__ import annotations

import ipaddress
import socket
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, HttpUrl, model_validator
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from .config import Settings
from .models import EvidenceRequest, ProbeSpec, ToolAction
from .store import AuthorityStore, Conflict


class ToolFailure(RuntimeError):
    code = "tool_failure"


class RetryableToolFailure(ToolFailure):
    code = "retryable_dependency_failure"


class TerminalToolFailure(ToolFailure):
    code = "terminal_dependency_failure"


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
    def __init__(self, settings: Settings, store: AuthorityStore, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.store = store
        self.http = httpx.AsyncClient(
            transport=transport,
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
            content = await self._get_json(request.source_ref)
        return self.store.save_evidence(tenant_id, run_id, request.evidence_id, request.kind, request.source_ref, content, request.freshness_seconds)

    async def execute_action(self, tenant_id: str, run_id: str, action: ToolAction, max_attempts: int) -> dict[str, Any]:
        request = action.model_dump(mode="json")
        invocation_id, replay = self.store.begin_invocation(tenant_id, run_id, action.tool, action.idempotency_key, request)
        if replay is not None:
            return {**replay, "idempotent_replay": True}

        operation: Callable[[], Awaitable[dict[str, Any]]]
        if action.tool == "record_action":
            arguments = RecordActionArguments.model_validate(action.arguments)
            operation = lambda: self._record_action(tenant_id, run_id, action.idempotency_key, arguments)
        elif action.tool == "http_json_action":
            arguments = HttpActionArguments.model_validate(action.arguments)
            operation = lambda: self._http_action(action.idempotency_key, arguments)
        else:
            raise TerminalToolFailure(f"Tool {action.tool} is not registered.")

        try:
            result: dict[str, Any] | None = None
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(min(max_attempts, self.settings.max_retry_attempts)),
                wait=wait_exponential_jitter(initial=self.settings.retry_wait_seconds, max=2.0),
                retry=retry_if_exception_type(RetryableToolFailure),
                reraise=True,
            ):
                with attempt:
                    attempt_number = attempt.retry_state.attempt_number
                    self.store.record_invocation_attempt(tenant_id, run_id, invocation_id, attempt_number)
                    result = await operation()
            if result is None:
                raise TerminalToolFailure("Tool returned no result.")
            self.store.complete_invocation(tenant_id, run_id, invocation_id, result)
            return result
        except ToolFailure as error:
            self.store.fail_invocation(tenant_id, run_id, invocation_id, error.code, str(error))
            raise
        except Exception as error:
            self.store.fail_invocation(tenant_id, run_id, invocation_id, "invalid_tool_input", str(error))
            raise TerminalToolFailure(str(error)) from error

    async def run_probe(self, probe: ProbeSpec, action_output: dict[str, Any], evidence: list[dict[str, Any]]) -> tuple[bool, dict[str, Any]]:
        if probe.kind == "evidence_present":
            found = any(item.get("evidence_id") == probe.expected for item in evidence)
            return found, {"expected_evidence_id": probe.expected, "found": found}
        if probe.kind == "http_json_equals":
            if probe.endpoint is None:
                return False, {"error": "endpoint is required"}
            endpoint = str(probe.endpoint)
            document = await self._get_json(endpoint)
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

    async def _http_action(self, idempotency_key: str, arguments: HttpActionArguments) -> dict[str, Any]:
        endpoint = str(arguments.endpoint)
        self._validate_endpoint(endpoint)
        try:
            response = await self.http.request(
                arguments.method,
                endpoint,
                json=arguments.body,
                headers={**self._connector_headers(endpoint), "content-type": "application/json", "idempotency-key": idempotency_key},
            )
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise RetryableToolFailure(str(error)) from error
        if response.status_code == 429 or response.status_code >= 500:
            raise RetryableToolFailure(f"Dependency returned {response.status_code}.")
        if response.status_code >= 400:
            raise TerminalToolFailure(f"Dependency returned {response.status_code}.")
        payload = await self._read_json(response)
        return {"status": "applied", "http_status": response.status_code, "response": payload}

    async def _get_json(self, endpoint: str) -> dict[str, Any]:
        self._validate_endpoint(endpoint)
        document: dict[str, Any] | None = None
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.settings.max_retry_attempts),
            wait=wait_exponential_jitter(initial=self.settings.retry_wait_seconds, max=2.0),
            retry=retry_if_exception_type(RetryableToolFailure),
            reraise=True,
        ):
            with attempt:
                try:
                    response = await self.http.get(endpoint, headers=self._connector_headers(endpoint))
                except (httpx.TimeoutException, httpx.NetworkError) as error:
                    raise RetryableToolFailure(str(error)) from error
                if response.status_code == 429 or response.status_code >= 500:
                    raise RetryableToolFailure(f"Dependency returned {response.status_code}.")
                if response.status_code >= 400:
                    raise TerminalToolFailure(f"Dependency returned {response.status_code}.")
                document = await self._read_json(response)
        if document is None:
            raise TerminalToolFailure("Dependency returned no JSON document.")
        return document

    async def _read_json(self, response: httpx.Response) -> dict[str, Any]:
        if response.is_redirect:
            raise TerminalToolFailure("Redirect responses are not allowed.")
        content = await response.aread()
        if len(content) > self.settings.http_max_response_bytes:
            raise TerminalToolFailure("Response exceeds the configured size limit.")
        try:
            value = response.json()
        except ValueError as error:
            raise TerminalToolFailure("Response is not valid JSON.") from error
        if not isinstance(value, dict):
            raise TerminalToolFailure("Response must be a JSON object.")
        return value

    def _validate_endpoint(self, endpoint: str) -> None:
        parsed = urlparse(endpoint)
        hostname = (parsed.hostname or "").lower()
        if parsed.username or parsed.password:
            raise TerminalToolFailure("Connector endpoints cannot contain embedded credentials.")
        if parsed.scheme != "https" and not (self.settings.allow_dev_auth and parsed.scheme == "http" and hostname in {"localhost", "127.0.0.1"}):
            raise TerminalToolFailure("Enterprise connector endpoints must use HTTPS.")
        if hostname not in self.settings.allowed_http_hosts:
            raise TerminalToolFailure(f"Connector host {hostname or '<missing>'} is not allowlisted.")
        if self.settings.allow_dev_auth and hostname in {"localhost", "127.0.0.1"}:
            return
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)}
        except socket.gaierror as error:
            raise RetryableToolFailure(f"Connector host {hostname} cannot be resolved.") from error
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                raise TerminalToolFailure("Connector endpoints cannot resolve to private or reserved addresses.")

    def _connector_headers(self, endpoint: str) -> dict[str, str]:
        hostname = (urlparse(endpoint).hostname or "").lower()
        headers = {"accept": "application/json", "user-agent": "LoopOS-Authority/0.1"}
        token = (self.settings.connector_bearer_tokens or {}).get(hostname)
        if token:
            headers["authorization"] = f"Bearer {token}"
        return headers
