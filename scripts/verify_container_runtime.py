from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RuntimeEvidenceError(RuntimeError):
    pass


SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def _run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as error:
        if check:
            raise RuntimeEvidenceError(f"{command[0]} could not be executed: {error}.") from error
        return subprocess.CompletedProcess(command, 127, "", str(error))
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise RuntimeEvidenceError(f"{' '.join(command[:3])} failed: {detail}")
    return result


def _inspect(container: str) -> dict[str, Any]:
    result = _run(["docker", "inspect", container])
    try:
        values = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeEvidenceError(f"Docker returned invalid inspection JSON for {container}.") from error
    if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], dict):
        raise RuntimeEvidenceError(f"Docker returned an unexpected inspection payload for {container}.")
    return values[0]


def _wait_healthy(container: str, timeout_seconds: float = 90.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        inspection = _inspect(container)
        state = inspection.get("State")
        if not isinstance(state, dict):
            raise RuntimeEvidenceError(f"{container} has no runtime state.")
        health = state.get("Health")
        health_status = health.get("Status") if isinstance(health, dict) else None
        if health_status == "healthy":
            return inspection
        if state.get("Status") in {"dead", "exited"} or health_status == "unhealthy":
            raise RuntimeEvidenceError(
                f"{container} stopped before becoming healthy: "
                f"state={state.get('Status')}, health={health_status}."
            )
        time.sleep(1)
    raise RuntimeEvidenceError(f"{container} did not become healthy within {timeout_seconds:.0f} seconds.")


def _request(base_url: str, path: str) -> tuple[int, dict[str, str], bytes]:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(f"{base_url}{path}", headers={"User-Agent": "loopos-runtime-verifier/1"})
    with opener.open(request, timeout=10) as response:
        return response.status, {key.lower(): value for key, value in response.headers.items()}, response.read()


def _runtime_uid(container: str) -> int:
    result = _run(["docker", "exec", container, "id", "-u"])
    try:
        return int(result.stdout.strip())
    except ValueError as error:
        raise RuntimeEvidenceError(f"{container} returned an invalid runtime UID.") from error


def _mapped_port(container: str) -> int:
    result = _run(["docker", "port", container, "8080/tcp"])
    endpoint = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    try:
        return int(endpoint.rsplit(":", 1)[1])
    except (IndexError, ValueError) as error:
        raise RuntimeEvidenceError(f"{container} has no valid host mapping for port 8080.") from error


def _release_config_digests(manifest_path: Path) -> dict[str, str]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeEvidenceError("The verified OCI evidence manifest could not be read.") from error
    if not isinstance(manifest, dict) or manifest.get("verified") is not True:
        raise RuntimeEvidenceError("The OCI evidence manifest is not verified.")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 2:
        raise RuntimeEvidenceError("The OCI evidence manifest has no artifacts array.")
    digests = {
        artifact.get("archive"): artifact.get("config_digest")
        for artifact in artifacts
        if isinstance(artifact, dict)
    }
    required = {"loopos-ui.oci.tar", "loopos-authority.oci.tar"}
    if set(digests) != required or not all(
        isinstance(digest, str) and SHA256_PATTERN.fullmatch(digest)
        for digest in digests.values()
    ):
        raise RuntimeEvidenceError("The OCI evidence manifest does not identify both release config digests.")
    return digests  # type: ignore[return-value]


def verify_runtime(ui_image: str, authority_image: str, oci_manifest: Path, output: Path) -> int:
    suffix = uuid.uuid4().hex[:10]
    network = f"loopos-smoke-{suffix}"
    authority = f"loopos-authority-{suffix}"
    ui = f"loopos-ui-{suffix}"
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verified": False,
        "checks": [],
        "containers": [],
    }
    try:
        release_digests = _release_config_digests(oci_manifest)
        _run(["docker", "network", "create", "--internal", network])
        _run([
            "docker", "run", "--detach",
            "--name", authority,
            "--network", network,
            "--network-alias", "authority",
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--tmpfs", "/data:rw,noexec,nosuid,size=64m",
            "--security-opt", "no-new-privileges:true",
            "--cap-drop", "ALL",
            "--env", "LOOPOS_ALLOW_DEV_AUTH=true",
            "--env", "LOOPOS_STORAGE_BACKEND=sqlite",
            "--env", "LOOPOS_DATABASE_PATH=/data/loopos-authority.db",
            "--env", "LOOPOS_SESSION_HMAC_SECRET=ci-runtime-smoke-secret-value-32-bytes",
            authority_image,
        ])
        authority_inspection = _wait_healthy(authority)

        _run([
            "docker", "run", "--detach",
            "--name", ui,
            "--network", network,
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--tmpfs", "/var/cache/nginx:rw,noexec,nosuid,size=64m",
            "--tmpfs", "/var/run:rw,noexec,nosuid,size=16m",
            "--security-opt", "no-new-privileges:true",
            "--cap-drop", "ALL",
            "--publish", "127.0.0.1::8080",
            ui_image,
        ])
        ui_inspection = _wait_healthy(ui)

        authority_uid = _runtime_uid(authority)
        ui_uid = _runtime_uid(ui)
        if authority_uid == 0 or ui_uid == 0:
            raise RuntimeEvidenceError("Both release containers must execute as non-root users.")

        port = _mapped_port(ui)
        base_url = f"http://127.0.0.1:{port}"
        health_status, _, health_body = _request(base_url, "/healthz")
        live_status, _, live_body = _request(base_url, "/api/health/live")
        ready_status, _, ready_body = _request(base_url, "/api/health/ready")
        root_status, root_headers, _ = _request(base_url, "/")
        try:
            live_payload = json.loads(live_body)
            ready_payload = json.loads(ready_body)
        except json.JSONDecodeError as error:
            raise RuntimeEvidenceError("The proxied authority health response was not valid JSON.") from error

        checks = {
            "authority_release_identity": (
                authority_inspection.get("Image") == release_digests["loopos-authority.oci.tar"]
            ),
            "ui_release_identity": ui_inspection.get("Image") == release_digests["loopos-ui.oci.tar"],
            "ui_health": health_status == 200 and health_body == b"ok\n",
            "authority_liveness_through_proxy": live_status == 200 and live_payload == {"status": "live"},
            "authority_readiness_through_proxy": (
                ready_status == 200
                and ready_payload.get("status") == "ready"
                and ready_payload.get("development_auth") is True
                and ready_payload.get("storage_backend") == "sqlite"
            ),
            "ui_root_served": root_status == 200,
            "content_security_policy": bool(root_headers.get("content-security-policy")),
            "content_type_nosniff": root_headers.get("x-content-type-options") == "nosniff",
            "authority_non_root": authority_uid != 0,
            "ui_non_root": ui_uid != 0,
        }
        report["checks"] = [{"name": name, "passed": passed} for name, passed in checks.items()]
        failed = [name for name, passed in checks.items() if not passed]
        if failed:
            raise RuntimeEvidenceError(f"Runtime checks failed: {', '.join(failed)}.")

        report["containers"] = [
            {
                "name": "authority",
                "image": authority_image,
                "image_id": authority_inspection.get("Image"),
                "release_config_digest": release_digests["loopos-authority.oci.tar"],
                "configured_user": authority_inspection.get("Config", {}).get("User"),
                "runtime_uid": authority_uid,
                "health": authority_inspection.get("State", {}).get("Health", {}).get("Status"),
            },
            {
                "name": "ui",
                "image": ui_image,
                "image_id": ui_inspection.get("Image"),
                "release_config_digest": release_digests["loopos-ui.oci.tar"],
                "configured_user": ui_inspection.get("Config", {}).get("User"),
                "runtime_uid": ui_uid,
                "health": ui_inspection.get("State", {}).get("Health", {}).get("Status"),
            },
        ]
        report["verified"] = True
    except (OSError, RuntimeEvidenceError, urllib.error.URLError) as error:
        report["error"] = str(error)
        for container in (authority, ui):
            logs = _run(["docker", "logs", container], check=False)
            if logs.stdout:
                print(logs.stdout, file=sys.stderr)
            if logs.stderr:
                print(logs.stderr, file=sys.stderr)
    finally:
        _run(["docker", "rm", "--force", ui, authority], check=False)
        _run(["docker", "network", "rm", network], check=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
        output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
    return 0 if report["verified"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exercise the hardened LoopOS release containers together.")
    parser.add_argument("--ui-image", required=True)
    parser.add_argument("--authority-image", required=True)
    parser.add_argument("--oci-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    return verify_runtime(args.ui_image, args.authority_image, args.oci_manifest, args.output)


if __name__ == "__main__":
    sys.exit(main())
