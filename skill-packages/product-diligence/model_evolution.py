#!/usr/bin/env python3
"""Validate supplied evidence of model-upgrade capability. Never execute an upgrade.

Only Python's standard library is required. Receipts bind bytes and identities;
they do not authenticate an operator or prove the truth of a test report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

SCHEMA = "product-diligence/model-evolution@1"
SUBJECT_KEYS = ("product", "revision", "environment", "configuration")
CONTROL_CHECKS = {
    "task_routing": ("pins_enforced", "capability_checks_exercised", "provider_contract_tests_passed"),
    "refresh_watch": ("discovery_exercised", "deprecation_watch_exercised", "owner_routing_exercised"),
    "evaluation_pipeline": ("holdout_separation_exercised", "trace_capture_exercised", "grader_calibration_passed", "contamination_checks_passed"),
    "policy_enforcement": ("permissions_outside_model", "privacy_outside_model", "budget_outside_model", "limits_exercised"),
    "fallback_recovery": ("fallback_exercised", "replay_idempotency_exercised", "cancellation_exercised"),
    "rollout_rollback": ("shadow_exercised", "canary_exercised", "rollback_exercised", "stop_trigger_exercised"),
    "product_outcomes": ("outcomes_measured", "baseline_bound", "regression_monitor_exercised"),
    "release_authority": ("executor_identity_bound", "preauthorization_scope_checked", "approval_replay_prevented", "review_separate_from_execution"),
}
CANDIDATE_CHECKS = (
    "safety_passed", "compatibility_passed", "capabilities_passed", "holdout_passed",
    "grader_calibration_passed", "shadow_passed", "canary_passed", "rollback_passed",
    "cancellation_passed",
)


class EvidenceError(ValueError):
    def __init__(self, message: str, missing: bool = False):
        super().__init__(message)
        self.missing = missing


def _require(condition: bool, message: str, missing: bool = False) -> None:
    if not condition:
        raise EvidenceError(message, missing)


def _object(value: Any, label: str) -> dict:
    _require(isinstance(value, dict), f"{label}: object required", value is None)
    return value


def _text(value: Any, label: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{label}: nonempty string required", value is None)
    return value


def _number(value: Any, label: str, minimum: float | None = None, strict: bool = False) -> float:
    _require(type(value) in (int, float) and math.isfinite(value), f"{label}: finite number required", value is None)
    if minimum is not None:
        _require(value > minimum if strict else value >= minimum, f"{label}: below permitted bound")
    return value


def _integer(value: Any, label: str) -> int:
    _require(type(value) is int and value > 0, f"{label}: positive integer required", value is None)
    return value


def _strings(value: Any, label: str) -> list[str]:
    _require(isinstance(value, list) and bool(value), f"{label}: nonempty string list required", value is None)
    for item in value:
        _text(item, label)
    _require(len(set(value)) == len(value), f"{label}: duplicate values")
    return value


def _time(value: Any, label: str) -> datetime:
    _text(value, label)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError) as exc:
        raise EvidenceError(f"{label}: invalid timestamp") from exc
    _require(parsed.tzinfo is not None, f"{label}: timezone required")
    return parsed.astimezone(timezone.utc)


def _fresh(value: dict, label: str, now: datetime) -> None:
    observed = _time(value.get("observed_at"), f"{label}.observed_at")
    expires = _time(value.get("expires_at"), f"{label}.expires_at")
    _require(observed <= now < expires and observed < expires, f"{label}: future-dated or expired evidence")


def _subject(value: Any) -> dict:
    subject = _object(value, "subject")
    _require(set(subject) == set(SUBJECT_KEYS), "subject: exact product/revision/environment/configuration keys required")
    for key in SUBJECT_KEYS:
        _text(subject[key], f"subject.{key}")
    return subject


def _digest(value: Any, label: str) -> str:
    _require(isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value), f"{label}: lowercase sha256 required", value is None)
    return value


def _json(data: bytes, label: str) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise EvidenceError(f"{label}: duplicate JSON key {key}")
            result[key] = value
        return result
    try:
        parsed = json.loads(data.decode("utf-8-sig"), object_pairs_hook=pairs,
                            parse_constant=lambda value: (_ for _ in ()).throw(EvidenceError(f"{label}: nonfinite JSON constant {value}")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"{label}: invalid UTF-8 JSON") from exc
    return _object(parsed, label)


def _receipt(value: Any, root: Path, label: str, parse: bool = False) -> tuple[Any, Path, str]:
    receipt = _object(value, label)
    relative = _text(receipt.get("path"), f"{label}.path")
    expected = _digest(receipt.get("sha256"), f"{label}.sha256")
    raw_path = Path(relative)
    _require(not raw_path.is_absolute(), f"{label}: path must be relative to evidence root")
    path = (root / raw_path).resolve()
    _require(path.is_relative_to(root), f"{label}: path escapes evidence root")
    _require(path.is_file(), f"{label}: evidence file missing", True)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise EvidenceError(f"{label}: unreadable evidence file", True) from exc
    _require(hashlib.sha256(data).hexdigest() == expected, f"{label}: evidence hash mismatch")
    return (_json(data, label) if parse else data), path, expected


def _bound(value: dict, subject: dict, kind: str, label: str, now: datetime) -> None:
    _require(value.get("kind") == kind, f"{label}: wrong evidence kind")
    _require(_subject(value.get("subject")) == subject, f"{label}: subject mismatch")
    _fresh(value, label, now)


def _checks(value: Any, required: tuple[str, ...], label: str) -> None:
    checks = _object(value, label)
    for name in required:
        _require(checks.get(name) is True, f"{label}.{name}: exercised passing evidence required", name not in checks)


def _model(value: Any, label: str) -> dict:
    model = _object(value, label)
    for name in ("provider", "id", "version"):
        _text(model.get(name), f"{label}.{name}")
    _require(model.get("version_mutable") is False, f"{label}: provider-declared immutable version required", "version_mutable" not in model)
    _require(model["version"].lower() not in ("latest", "auto", "default"), f"{label}.version: moving aliases are not model pins")
    _digest(model.get("configuration_sha256"), f"{label}.configuration_sha256")
    _strings(model.get("capabilities"), f"{label}.capabilities")
    return model


def _thresholds(value: Any, label: str) -> dict:
    thresholds = _object(value, label)
    _integer(thresholds.get("min_samples"), f"{label}.min_samples")
    for name in ("quality_noninferiority_margin", "min_product_outcome_improvement"):
        _number(thresholds.get(name), f"{label}.{name}", 0)
    for name in ("min_quality_uplift", "min_cost_improvement_fraction", "min_latency_improvement_fraction", "max_cost_per_task", "max_latency_p95_ms", "min_confidence_level"):
        _number(thresholds.get(name), f"{label}.{name}", 0, True)
    for name in ("min_cost_improvement_fraction", "min_latency_improvement_fraction"):
        _require(thresholds[name] <= 1, f"{label}.{name}: must be at most 1")
    _require(thresholds["min_confidence_level"] < 1, f"{label}.min_confidence_level: must be below 1")
    return thresholds


def _capability(config: dict, root: Path, subject: dict, now: datetime) -> dict:
    _require(config.get("schema") == SCHEMA, "model_evolution: unsupported schema")
    _require(_subject(config.get("subject")) == subject, "model_evolution: subject mismatch")
    _fresh(config, "model_evolution", now)
    values = config.get("tasks")
    _require(isinstance(values, list) and bool(values), "tasks: nonempty tasks required", values is None or values == [])
    declared_tasks = [_text(_object(task, "task").get("id"), "task.id") for task in values]
    _require(len(set(declared_tasks)) == len(declared_tasks), "tasks: duplicate task id")
    controls = _object(config.get("controls"), "controls")
    for name, checks in CONTROL_CHECKS.items():
        record = _object(controls.get(name), f"controls.{name}")
        owner = _text(record.get("owner"), f"controls.{name}.owner")
        proof, _, _ = _receipt(record.get("evidence"), root, f"controls.{name}.evidence", True)
        _bound(proof, subject, "model-evolution/control-proof@1", name, now)
        _require(proof.get("control") == name and proof.get("owner") == owner, f"{name}: proof control/owner mismatch")
        _require(set(_strings(proof.get("covered_tasks"), f"{name}.covered_tasks")) == set(declared_tasks),
                 f"{name}: control does not cover the declared tasks")
        _checks(proof.get("checks"), checks, name)

    refresh = _object(config.get("refresh"), "refresh")
    _text(refresh.get("owner"), "refresh.owner")
    _require(refresh["owner"] == controls["refresh_watch"]["owner"], "refresh: owner differs from exercised control")
    cadence = _number(refresh.get("cadence_hours"), "refresh.cadence_hours", 0, True)
    reviewed = _time(refresh.get("last_reviewed_at"), "refresh.last_reviewed_at")
    due = _time(refresh.get("next_review_at"), "refresh.next_review_at")
    _require(reviewed <= now < due and (due - reviewed).total_seconds() / 3600 <= cadence,
             "refresh: overdue, future reviewed date, or cadence exceeded")
    sources = refresh.get("official_sources")
    _require(isinstance(sources, list) and bool(sources), "refresh.official_sources: sources required", sources is None or sources == [])
    providers = set()
    for index, source in enumerate(sources):
        source = _object(source, f"source[{index}]")
        providers.add(_text(source.get("provider"), "source.provider"))
        url = urlparse(_text(source.get("url"), "source.url"))
        _require(url.scheme == "https" and bool(url.hostname) and not url.username and not url.password, "source.url: HTTPS source required")
        _fresh(source, "source", now)
        _require(_time(source["observed_at"], "source.observed_at") <= reviewed,
                 "source: source captured after declared review")
        _receipt(source.get("artifact"), root, "source.artifact")

    tasks = {}
    for record in values:
        task = _object(record, "task")
        task_id = _text(task.get("id"), "task.id")
        _require(task_id not in tasks, "tasks: duplicate task id")
        champion = _model(task.get("champion"), f"{task_id}.champion")
        _require(champion["provider"] in providers, f"{task_id}: missing current provider source", True)
        required = _strings(task.get("required_capabilities"), f"{task_id}.required_capabilities")
        _require(set(required) <= set(champion["capabilities"]), f"{task_id}: champion lacks required capabilities")
        _, _, config_hash = _receipt(task.get("configuration"), root, f"{task_id}.configuration")
        _require(champion["configuration_sha256"] == config_hash, f"{task_id}: champion configuration mismatch")
        _thresholds(task.get("thresholds"), f"{task_id}.thresholds")
        protocol = _object(task.get("evaluation_protocol"), f"{task_id}.evaluation_protocol")
        for name in ("dataset", "scorer", "configuration"):
            _receipt(protocol.get(name), root, f"{task_id}.evaluation_protocol.{name}")
        outcome = _object(task.get("product_outcome"), f"{task_id}.product_outcome")
        _text(outcome.get("metric"), "product_outcome.metric")
        _require(outcome.get("direction") in ("higher", "lower"), "product_outcome.direction: higher or lower required")
        tasks[task_id] = task
    return tasks


def _candidate(record: Any, tasks: dict, root: Path, subject: dict, now: datetime, providers: set[str]) -> dict:
    record = _object(record, "candidate")
    candidate_id = _text(record.get("id"), "candidate.id")
    task_id = _text(record.get("task"), "candidate.task")
    _require(task_id in tasks, "candidate: unknown task")
    task = tasks[task_id]
    model = _model(record.get("model"), "candidate.model")
    identity_keys = ("provider", "id", "version", "configuration_sha256")
    _require(any(model[key] != task["champion"][key] for key in identity_keys), "candidate: challenger equals champion")
    _require(model["provider"] in providers, "candidate: missing current provider source", True)
    _require(set(task["required_capabilities"]) <= set(model["capabilities"]), "candidate: required capabilities absent")
    _, _, model_config = _receipt(record.get("configuration"), root, "candidate.configuration")
    _require(model["configuration_sha256"] == model_config, "candidate: configuration mismatch")
    report, _, report_hash = _receipt(record.get("evaluation"), root, "candidate.evaluation", True)
    _bound(report, subject, "model-evolution/paired-evaluation@1", "candidate.evaluation", now)
    _require(report.get("candidate_id") == candidate_id and report.get("task") == task_id, "candidate: evaluation identity mismatch")
    _require(report.get("champion") == task["champion"] and report.get("challenger") == model, "candidate: evaluated model pins differ")
    protocol = task["evaluation_protocol"]
    for name in ("dataset", "scorer", "configuration"):
        _require(report.get(f"{name}_sha256") == protocol[name]["sha256"], f"candidate: paired {name} mismatch")
    _require(report.get("paired") is True, "candidate: paired comparison required")
    _receipt(report.get("trace"), root, "candidate.trace")
    limits = task["thresholds"]
    samples = _integer(report.get("sample_count"), "candidate.sample_count")
    _require(samples >= limits["min_samples"], "candidate: insufficient samples")
    confidence = _number(report.get("confidence_level"), "candidate.confidence_level", 0, True)
    _require(limits["min_confidence_level"] <= confidence < 1, "candidate: insufficient or invalid confidence level")
    _text(report.get("confidence_method"), "candidate.confidence_method")
    _checks(report.get("checks"), CANDIDATE_CHECKS, "candidate.checks")
    quality = _object(report.get("quality"), "candidate.quality")
    for name in ("champion_mean", "challenger_mean", "delta_lower_bound", "delta_upper_bound"):
        _number(quality.get(name), f"candidate.quality.{name}")
    delta = quality["challenger_mean"] - quality["champion_mean"]
    lower = quality["delta_lower_bound"]
    upper = quality["delta_upper_bound"]
    _require(math.isfinite(delta) and lower <= delta <= upper, "candidate: inconsistent quality interval")
    _require(lower >= -limits["quality_noninferiority_margin"], "candidate: quality noninferiority failed")
    cost = _object(report.get("cost"), "candidate.cost")
    latency = _object(report.get("latency"), "candidate.latency")
    champion_cost = _number(cost.get("champion_per_task"), "candidate.cost.champion_per_task", 0, True)
    challenger_cost = _number(cost.get("challenger_per_task"), "candidate.cost.challenger_per_task", 0)
    champion_latency = _number(latency.get("champion_p95_ms"), "candidate.latency.champion_p95_ms", 0, True)
    challenger_latency = _number(latency.get("challenger_p95_ms"), "candidate.latency.challenger_p95_ms", 0)
    _require(challenger_cost <= limits["max_cost_per_task"], "candidate: cost limit exceeded")
    _require(challenger_latency <= limits["max_latency_p95_ms"], "candidate: latency limit exceeded")
    paths = []
    if lower >= limits["min_quality_uplift"]:
        paths.append("quality_lower_bound_uplift")
    if (champion_cost - challenger_cost) / champion_cost >= limits["min_cost_improvement_fraction"]:
        paths.append("cost_improvement_with_quality_noninferiority")
    if (champion_latency - challenger_latency) / champion_latency >= limits["min_latency_improvement_fraction"]:
        paths.append("latency_improvement_with_quality_noninferiority")
    _require(bool(paths), "candidate: no required improvement demonstrated")
    outcome = _object(report.get("product_outcome"), "candidate.product_outcome")
    _require(outcome.get("metric") == task["product_outcome"]["metric"], "candidate: product outcome metric mismatch")
    baseline = _number(outcome.get("champion"), "candidate.product_outcome.champion")
    measured = _number(outcome.get("challenger"), "candidate.product_outcome.challenger")
    change = measured - baseline if task["product_outcome"]["direction"] == "higher" else baseline - measured
    _require(math.isfinite(change) and change >= limits["min_product_outcome_improvement"], "candidate: product outcome regressed or target not met")
    return {"id": candidate_id, "task": task_id, "status": "QUALIFIED", "reasons": [],
            "improvement_paths": paths, "evaluation_sha256": report_hash, "execution_authorized": False}


def evaluate(manifest: dict, base_dir: Path | None = None, now: datetime | None = None) -> dict:
    """Return capability status plus independent candidate decisions; perform no writes.

    ``base_dir`` is the manifest directory. Receipt paths resolve below that root.
    QUALIFIED means review eligible on supplied evidence, never release authority.
    """
    result = {"status": "EVIDENCE_MISSING", "reasons": [], "candidate_decisions": [],
              "execution_authorized": False, "capability_only": True,
              "scope": "structural validation of supplied artifact receipts; no provider or runtime verification"}
    root = Path(base_dir or Path.cwd()).resolve()
    observed_now = now or datetime.now(timezone.utc)
    try:
        _require(isinstance(observed_now, datetime) and observed_now.tzinfo is not None, "now: timezone-aware datetime required")
        _object(manifest, "manifest")
        subject = _subject(manifest.get("subject"))
        config, _, config_hash = _receipt(manifest.get("model_evolution"), root, "model_evolution", True)
        result["config_sha256"] = config_hash
        tasks = _capability(config, root, subject, observed_now)
        candidates = config.get("candidates")
        _require(isinstance(candidates, list), "candidates: explicit list required", candidates is None)
        ids = [_text(_object(candidate, "candidate").get("id"), "candidate.id") for candidate in candidates]
        _require(len(set(ids)) == len(ids), "candidates: duplicate candidate ids")
        providers = {source["provider"] for source in config["refresh"]["official_sources"]}
        for candidate in candidates:
            try:
                decision = _candidate(candidate, tasks, root, subject, observed_now, providers)
            except EvidenceError as exc:
                decision = {"id": candidate["id"], "task": candidate.get("task"),
                            "status": "EVIDENCE_MISSING" if exc.missing else "NOT_READY",
                            "reasons": [str(exc)], "execution_authorized": False}
            result["candidate_decisions"].append(decision)
        result["status"] = "QUALIFIED"
        result["capability_only"] = not any(row["status"] == "QUALIFIED" for row in result["candidate_decisions"])
    except EvidenceError as exc:
        result["status"] = "EVIDENCE_MISSING" if exc.missing else "NOT_READY"
        result["reasons"].append(str(exc))
    except (OSError, ValueError, OverflowError, TypeError) as exc:
        result["status"] = "NOT_READY"
        result["reasons"].append(f"invalid evidence: {type(exc).__name__}: {exc}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        manifest = _json(args.manifest.read_bytes(), "manifest")
        result = evaluate(manifest, args.manifest.resolve().parent)
    except (OSError, EvidenceError) as exc:
        result = {"status": "EVIDENCE_MISSING", "reasons": [str(exc)], "candidate_decisions": [], "execution_authorized": False}
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["status"] == "QUALIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
