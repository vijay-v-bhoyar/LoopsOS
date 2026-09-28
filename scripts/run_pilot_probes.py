from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
VALID_STATUSES = {"PASS", "FAIL", "INPUT_REQUIRED"}
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _safe_repo_path(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    candidate.relative_to(root.resolve())
    return candidate


def _load_adapter(root: Path, probe_id: str, relative_path: str):
    path = _safe_repo_path(root, relative_path)
    if not path.is_file() or path.suffix.lower() != ".py":
        raise ValueError(f"{probe_id}: adapter does not resolve to a Python file")
    module_name = "pilot_probe_" + re.sub(r"[^a-zA-Z0-9_]", "_", probe_id)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"{probe_id}: adapter could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run = getattr(module, "run", None)
    if not callable(run):
        raise ValueError(f"{probe_id}: adapter must expose run(payload)")
    return run


def _validate_result(probe_id: str, value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{probe_id}: adapter result must be an object")
    if value.get("schema_version") != 1:
        raise ValueError(f"{probe_id}: adapter result must use schema_version 1")
    if value.get("probe_id") != probe_id:
        raise ValueError(f"{probe_id}: adapter result probe_id does not match registry")
    if value.get("status") not in VALID_STATUSES:
        raise ValueError(f"{probe_id}: adapter result has an invalid status")
    checks = value.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError(f"{probe_id}: adapter result must contain checks")
    if any(not isinstance(item, dict) or not isinstance(item.get("passed"), bool) for item in checks):
        raise ValueError(f"{probe_id}: adapter checks must contain boolean passed values")
    if value.get("external_calls") != 0:
        raise ValueError(f"{probe_id}: local probe adapters must not make external calls")
    if value.get("proof_scope") != "local_contract":
        raise ValueError(f"{probe_id}: local probe adapters must declare proof_scope local_contract")
    if value.get("live_verification") != "unproven":
        raise ValueError(f"{probe_id}: local probe adapters must declare live_verification unproven")


def run_probes(
    repo_root: Path = REPO_ROOT,
    fixture_path: Path = REPO_ROOT / "evals" / "fixtures" / "pilot-sdlc-governance-os.json",
    probe_id: str | None = None,
) -> dict[str, Any]:
    registry = yaml.safe_load((repo_root / "probes" / "PROBE_REGISTRY.yaml").read_text(encoding="utf-8"))
    try:
        resolved_fixture = _safe_repo_path(repo_root, str(fixture_path))
    except (OSError, ValueError) as error:
        raise ValueError("fixture must resolve to a file inside the repository") from error
    if not resolved_fixture.is_file():
        raise ValueError("fixture must resolve to a file inside the repository")
    fixture = json.loads(resolved_fixture.read_text(encoding="utf-8"))
    probes = registry.get("probes", []) if isinstance(registry, dict) else []
    cases = fixture.get("probe_cases", {}) if isinstance(fixture, dict) else {}
    selected = [probe for probe in probes if probe_id is None or probe.get("probe_id") == probe_id]
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    for probe in selected:
        current_id = probe.get("probe_id")
        if not isinstance(current_id, str):
            failures.append("registry contains a probe without a probe_id")
            continue
        adapter_path = probe.get("adapter")
        if not isinstance(adapter_path, str):
            failures.append(f"{current_id}: registry adapter is missing")
            continue
        probe_cases = cases.get(current_id)
        if isinstance(probe_cases, dict):
            probe_cases = [probe_cases]
        if not isinstance(probe_cases, list) or not probe_cases:
            failures.append(f"{current_id}: fixture has no probe_cases entry")
            continue
        try:
            run = _load_adapter(repo_root, current_id, adapter_path)
            case_results = []
            for index, case in enumerate(probe_cases):
                value = run(case)
                _validate_result(current_id, value)
                case_results.append({"case_index": index, "result": value})
                if value["status"] != "PASS":
                    failures.append(f"{current_id}[{index}]: {value['status']}")
            results.append({"probe_id": current_id, "adapter": adapter_path, "cases": case_results})
        except (OSError, TypeError, ValueError, json.JSONDecodeError, yaml.YAMLError) as error:
            failures.append(str(error))

    return {
        "schema_version": 1,
        "fixture_kind": fixture.get("fixture_kind"),
        "playbook_id": fixture.get("playbook_id"),
        "proof_scope": "local_contract",
        "live_verification": "unproven",
        "external_calls": 0,
        "probe_count": len(results),
        "case_count": sum(len(item["cases"]) for item in results),
        "verdict": "PASS" if selected and not failures else "NO_GO",
        "failures": failures,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run credential-free local pilot probe adapters against bounded fixtures.")
    parser.add_argument("--fixture", type=Path, default=REPO_ROOT / "evals" / "fixtures" / "pilot-sdlc-governance-os.json")
    parser.add_argument("--probe-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = run_probes(REPO_ROOT, args.fixture, args.probe_id)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
