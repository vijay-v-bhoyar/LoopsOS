#!/usr/bin/env python3
"""Advisory local progress ledger. Receipts establish integrity, never authority."""
import argparse
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile


class LedgerError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise LedgerError(message)


def exact(value, required, optional=()):
    require(isinstance(value, dict), "expected object")
    require(set(required) <= set(value) <= set(required) | set(optional), "invalid object fields")


def string(value):
    require(isinstance(value, str) and value.strip() and len(value) <= 4096, "expected nonempty bounded string")
    return value


def strings(value, empty=False):
    require(isinstance(value, list) and (empty or value), "expected nonempty list")
    for item in value:
        string(item)
    require(len(set(value)) == len(value), "duplicate list entries")
    return value


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, "invalid integer")


def subject(value):
    exact(value, ("product", "target", "revision", "configuration"))
    for item in value.values():
        string(item)


def timestamp(value):
    string(value)
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LedgerError("invalid timestamp") from exc
    require(parsed.tzinfo is not None and parsed.utcoffset() is not None, "timestamp must have timezone")
    return parsed


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON keys")
        result[key] = value
    return result


def checked_path(value, exists=True):
    path = Path(os.path.abspath(value))
    for component in reversed((path,) + tuple(path.parents)):
        try:
            info = component.lstat()
        except FileNotFoundError:
            require(not exists and component == path, "path does not exist")
            continue
        require(not stat.S_ISLNK(info.st_mode) and not (getattr(info, "st_file_attributes", 0) & 0x400), "symlink/reparse paths are forbidden")
    return path


def reference(root, value):
    string(value)
    require("\\" not in value and ":" not in value and not value.startswith("/"), "reference must be relative POSIX path")
    parts = value.split("/")
    require(all(part not in ("", ".", "..") for part in parts), "unsafe reference")
    path = checked_path(root.joinpath(*parts))
    require(path.is_file(), "reference must be a regular file")
    return path


def read_json(path):
    path = checked_path(path)
    require(path.is_file() and path.stat().st_size <= 4_000_000, "JSON file missing or too large")
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates,
                          parse_constant=lambda _: (_ for _ in ()).throw(LedgerError("nonfinite JSON number")))
    except LedgerError:
        raise
    except (UnicodeError, ValueError) as exc:
        raise LedgerError("invalid JSON") from exc


def file_hash(path):
    checked_path(path)
    require(path.is_file(), "artifact must be a regular file")
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            result.update(chunk)
    checked_path(path)
    return result.hexdigest()


def artifact(root, value, live=True):
    exact(value, ("path", "sha256"))
    string(value["path"])
    hash_value = value["sha256"]
    require(isinstance(hash_value, str) and len(hash_value) == 64 and all(c in "0123456789abcdef" for c in hash_value), "invalid SHA256")
    require("\\" not in value["path"] and ":" not in value["path"] and not value["path"].startswith("/")
            and all(p not in ("", ".", "..") for p in value["path"].split("/")), "unsafe artifact path")
    if live:
        require(file_hash(reference(root, value["path"])) == hash_value, "artifact hash mismatch")


def validate_plan(plan):
    exact(plan, ("goal", "subject", "criteria", "tasks", "limits"), ("controls", "enterprise_assurance"))
    if "enterprise_assurance" in plan:
        binding = plan["enterprise_assurance"]
        exact(binding, ("state", "trust", "trust_sha256", "run_id", "subject_sha256", "parent_subject_sha256", "delivery_engine"))
        for value in binding.values(): string(value)
        for key in ("trust_sha256", "subject_sha256", "parent_subject_sha256"):
            require(len(binding[key]) == 64 and all(c in "0123456789abcdef" for c in binding[key]), "enterprise binding requires SHA-256")
        require(binding["parent_subject_sha256"] == digest(plan["subject"]), "enterprise parent subject binding mismatch")
        require(binding["delivery_engine"] in {"codex-product-build-loop", "product-loop", "agentic-product-loop"}, "exactly one enterprise repair engine required")
    controls = plan.get("controls", [])
    require(isinstance(controls, list), "controls must be a list")
    for control in controls:
        artifact(None, control, False)
    require(len({control["path"] for control in controls}) == len(controls), "duplicate control path")
    exact(plan["goal"], ("id", "outcome"))
    for value in plan["goal"].values():
        string(value)
    subject(plan["subject"])
    criteria = set(strings(plan["criteria"]))
    require(isinstance(plan["tasks"], list) and plan["tasks"], "tasks cannot be empty")
    tasks = {}
    coverage = set()
    for task in plan["tasks"]:
        exact(task, ("id", "criteria", "depends_on"))
        task_id = string(task["id"])
        require(task_id not in tasks, "duplicate task")
        require(set(strings(task["criteria"])) <= criteria, "unknown criterion")
        strings(task["depends_on"], empty=True)
        coverage.update(task["criteria"])
        tasks[task_id] = task
    require(coverage == criteria, "every criterion must map to a task")
    seen, active = set(), set()
    def visit(task_id):
        require(task_id in tasks, "unknown dependency")
        require(task_id not in active, "cyclic task dependencies")
        if task_id in seen:
            return
        active.add(task_id)
        for dep in tasks[task_id]["depends_on"]:
            visit(dep)
        active.remove(task_id)
        seen.add(task_id)
    for task_id in tasks:
        visit(task_id)
    exact(plan["limits"], ("max_total_attempts", "max_attempts_per_task", "max_same_failure"))
    for value in plan["limits"].values():
        integer(value, 1)
    return tasks


CATEGORIES = {"code", "configuration", "capability", "evidence", "input", "authority", "external", "transient", "unknown_effect"}
BLOCK_FIELDS = ("category", "fingerprint", "summary", "needs", "question", "requested_owner", "requested_capability", "expected_acceptance", "wake_condition")


def validate_event(event):
    require(isinstance(event, dict) and "type" in event, "event type required")
    kind = event["type"]
    string(kind)
    fields = {
        "start": ("attempt_id", "owner", "operation_kind"),
        "fail": BLOCK_FIELDS, "block": BLOCK_FIELDS,
        "help_received": ("response",), "resume": ("receipt",),
        "verify": ("receipt",), "reconcile": ("receipt",),
        "invalidate": ("subject", "reason"),
    }
    require(kind in fields, "unknown event type")
    exact(event, ("type",) + (() if kind == "invalidate" else ("task_id",)) + fields[kind],
          ("operation_key",) if kind == "start" else ())
    if kind != "invalidate":
        string(event["task_id"])
    if kind == "start":
        string(event["attempt_id"])
        string(event["owner"])
        require(event["operation_kind"] in ("local", "external"), "invalid operation kind")
        require(("operation_key" in event) == (event["operation_kind"] == "external"), "external operation requires stable key")
        if "operation_key" in event:
            string(event["operation_key"])
    elif kind in ("fail", "block"):
        for field in BLOCK_FIELDS:
            string(event[field])
        require(event["category"] in CATEGORIES, "unknown blocker category")
    elif kind == "invalidate":
        subject(event["subject"])
        string(event["reason"])
    elif kind != "help_received":
        string(event["receipt"])


def receipt_check(doc, root, task_id, expected_subject, criteria, kind, at, live=True, operation_key=None):
    extra = ("operation_key", "effect_state") if kind == "reconciliation" else ()
    exact(doc, ("kind", "task_id", "subject", "result", "criteria", "issued_at", "expires_at", "producer", "method", "artifact") + extra)
    require(doc["kind"] == kind and doc["task_id"] == task_id, "receipt kind/task mismatch")
    subject(doc["subject"])
    require(doc["subject"] == expected_subject and doc["result"] == "PASS", "receipt context/result mismatch")
    covered = set(strings(doc["criteria"], empty=kind != "evidence"))
    require(covered <= set(criteria), "receipt contains unknown task criterion")
    if kind == "evidence":
        require(covered == set(criteria), "receipt must cover every task criterion")
    require(timestamp(doc["issued_at"]) <= timestamp(at) < timestamp(doc["expires_at"]), "receipt is future dated or expired")
    string(doc["producer"])
    string(doc["method"])
    artifact(root, doc["artifact"], live)
    if kind == "reconciliation":
        require(doc["operation_key"] == operation_key, "reconciliation key mismatch")
        require(doc["effect_state"] in ("not_applied", "applied", "compensated"), "unknown external effect")


def base_projection(plan):
    return {"subject": copy.deepcopy(plan["subject"]), "total_attempts": 0, "attempt_ids": [], "operation_keys": [],
            "tasks": {t["id"]: {"status": "pending", "attempts": 0, "failures": {}, "blocker": None,
                "help": [], "receipt": None, "operation": None, "operation_key": None,
                "current_attempt": None, "revalidation": None} for t in plan["tasks"]}}


def revalidation_valid(projection, task_id, tasks, root, at, live=True):
    saved = projection["tasks"][task_id]["revalidation"]
    if saved is None:
        return (True, None)
    try:
        doc = read_json(reference(root, saved["path"])) if live else saved["document"]
        require(digest(doc) == saved["sha256"], "revalidation receipt was changed")
        receipt_check(doc, root, task_id, projection["subject"], tasks[task_id]["criteria"], "revalidation", at, live)
        return (True, None)
    except (LedgerError, OSError) as exc:
        return (False, str(exc))


def current_valid(projection, task_id, tasks, root, at, memo=None):
    memo = {} if memo is None else memo
    if task_id in memo:
        return memo[task_id]
    task = projection["tasks"][task_id]
    try:
        require(task["status"] == "verified" and task["receipt"], "task lacks accepted evidence")
        saved = task["receipt"]
        doc = read_json(reference(root, saved["path"]))
        require(digest(doc) == saved["sha256"], "receipt was changed")
        receipt_check(doc, root, task_id, projection["subject"], tasks[task_id]["criteria"], "evidence", at)
        require(all(current_valid(projection, dep, tasks, root, at, memo)[0] for dep in tasks[task_id]["depends_on"]), "dependency evidence is not current")
        result = (True, None)
    except (LedgerError, OSError) as exc:
        result = (False, str(exc))
    memo[task_id] = result
    return result


def cap_reason(projection, task, limits):
    if projection["total_attempts"] >= limits["max_total_attempts"]:
        return "max_total_attempts"
    if task["attempts"] >= limits["max_attempts_per_task"]:
        return "max_attempts_per_task"
    if any(count >= limits["max_same_failure"] for count in task["failures"].values()):
        return "max_same_failure"
    return None


def transition(projection, event, material, plan, root, at, live):
    validate_event(event)
    tasks = {t["id"]: t for t in plan["tasks"]}
    kind = event["type"]
    if kind == "invalidate":
        require(not material and event["subject"] != projection["subject"], "subject must change")
        projection["subject"] = copy.deepcopy(event["subject"])
        for task in projection["tasks"].values():
            task["receipt"] = None
            if task["operation"] and task["operation"]["effect"] == "unknown":
                task["status"] = "blocked"
                if task["blocker"] is None:
                    task["blocker"] = {
                        "category": "unknown_effect", "fingerprint": "subject_changed_with_unresolved_effect",
                        "summary": "Subject changed while an external effect remained unresolved",
                        "needs": "Reconcile the existing operation before revalidating the new subject",
                        "question": "Was the recorded operation applied, not applied, or compensated?",
                        "requested_owner": task["current_attempt"]["owner"],
                        "requested_capability": "Read actual provider operation state",
                        "expected_acceptance": "Matching reconciliation receipt and current-subject revalidation receipt",
                        "wake_condition": "Provider reconciliation evidence is available",
                    }
            elif task["operation"] and task["operation"]["effect"] == "applied":
                task["status"] = "verify_existing"
            elif task["status"] == "blocked":
                pass
            else:
                task["status"] = "pending"
        return
    task_id = event["task_id"]
    require(task_id in tasks, "unknown task")
    task = projection["tasks"][task_id]
    if kind in ("start", "verify"):
        for dep in tasks[task_id]["depends_on"]:
            require(projection["tasks"][dep]["status"] == "verified", "dependency not verified")
            if live:
                require(current_valid(projection, dep, tasks, root, at)[0], "dependency evidence is not current")
    if kind == "start":
        require(not material and task["status"] == "pending", "task is not available to start")
        require(not task["operation"] or task["operation"]["effect"] in ("not_applied", "compensated"), "external effect requires reconciliation/verification")
        require(not cap_reason(projection, task, plan["limits"]), "persistent attempt/failure limit reached")
        require(revalidation_valid(projection, task_id, tasks, root, at, live)[0], "revalidation evidence is not current")
        require(event["attempt_id"] not in projection["attempt_ids"], "attempt id was already used")
        if task["operation_key"]:
            require(event.get("operation_key") == task["operation_key"], "external retry must retain stable operation key")
        if event["operation_kind"] == "external":
            reservations = projection["operation_keys"]
            for reservation in reservations:
                require(not (reservation["key"] == event["operation_key"]
                             and reservation["task_id"] != task_id), "operation key already belongs to another task in this goal")
            reservation = {"subject": copy.deepcopy(projection["subject"]), "key": event["operation_key"], "task_id": task_id}
            if reservation not in reservations:
                reservations.append(reservation)
            task["operation_key"] = event["operation_key"]
            task["operation"] = {"key": event["operation_key"], "subject": copy.deepcopy(projection["subject"]), "effect": "unknown"}
        task["status"] = "active"
        task["current_attempt"] = {"attempt_id": event["attempt_id"], "owner": event["owner"],
                                   "operation_kind": event["operation_kind"], "started_at": at}
        task["attempts"] += 1
        projection["total_attempts"] += 1
        projection["attempt_ids"].append(event["attempt_id"])
    elif kind in ("fail", "block"):
        require(not material and task["status"] in ("active", "verify_existing", "verified"), "only running work or stale verified evidence may fail/block")
        if task["status"] == "verified" and live:
            require(not current_valid(projection, task_id, tasks, root, at)[0], "current verified evidence cannot fail/block without invalidation")
        task["status"] = "blocked"
        task["blocker"] = {field: event[field] for field in BLOCK_FIELDS}
        fingerprint = event["fingerprint"]
        task["failures"][fingerprint] = task["failures"].get(fingerprint, 0) + 1
    elif kind == "help_received":
        require(not material and task["status"] == "blocked", "help requires blocked task")
        artifact(root, event["response"], live)
        task["help"].append(copy.deepcopy(event["response"]))
    else:
        exact(material, ("document", "sha256"))
        require(digest(material["document"]) == material["sha256"], "recorded receipt digest mismatch")
        doc = material["document"]
        receipt_kind = {"resume": "revalidation", "verify": "evidence", "reconcile": "reconciliation"}[kind]
        operation = task["operation"]
        expected_subject = operation["subject"] if kind == "reconcile" and operation else projection["subject"]
        receipt_check(doc, root, task_id, expected_subject, tasks[task_id]["criteria"], receipt_kind, at, live,
                      operation["key"] if operation else None)
        if live:
            require(digest(read_json(reference(root, event["receipt"]))) == material["sha256"], "receipt changed during operation")
        else:
            artifact(root, {"path": event["receipt"], "sha256": material["sha256"]}, False)
        if kind == "resume":
            require(task["status"] == "blocked" or (task["status"] in ("pending", "verify_existing") and task["revalidation"] is not None), "resume requires blocked task or prior revalidation")
            require(not operation or operation["effect"] in ("not_applied", "compensated", "applied"), "reconcile external effect before resume")
            task["revalidation"] = {"path": event["receipt"], "sha256": material["sha256"], "document": copy.deepcopy(doc)}
            task["status"] = "verify_existing" if operation and operation["effect"] == "applied" else "pending"
        elif kind == "verify":
            require(task["status"] in ("active", "verify_existing", "verified"), "verification requires started or existing work")
            require(not operation or operation["effect"] == "applied", "external verification requires key-bound applied reconciliation first")
            require(revalidation_valid(projection, task_id, tasks, root, at, live)[0], "revalidation evidence is not current")
            task["status"] = "verified"
            task["receipt"] = {"path": event["receipt"], "sha256": material["sha256"]}
            if operation:
                operation["effect"] = "applied"
        else:
            require(operation and operation["effect"] == "unknown" and task["status"] in ("active", "blocked"), "no unresolved external operation")
            operation["effect"] = doc["effect_state"]
            if operation["effect"] == "applied":
                if task["status"] != "blocked":
                    task["status"] = "verify_existing"
            elif task["status"] == "active":
                task["status"] = "pending"


def replay(state, root):
    exact(state, ("schema", "engine_sha256", "plan", "plan_sha256", "revision", "events", "projection"))
    require(state["schema"] == 1 and type(state["schema"]) is int, "unsupported schema")
    require(state["engine_sha256"] == file_hash(Path(__file__)), "ledger engine changed; independent review required")
    validate_plan(state["plan"])
    require(digest(state["plan"]) == state["plan_sha256"], "frozen plan digest mismatch")
    for control in state["plan"].get("controls", []):
        artifact(root, control)
    integer(state["revision"])
    require(isinstance(state["events"], list) and len(state["events"]) == state["revision"], "event/revision mismatch")
    projection = base_projection(state["plan"])
    previous = state["plan_sha256"]
    previous_time = None
    for record in state["events"]:
        exact(record, ("at", "event", "material", "previous", "sha256"))
        current_time = timestamp(record["at"])
        require(previous_time is None or current_time >= previous_time, "event clock moved backward")
        previous_time = current_time
        require(record["previous"] == previous, "event chain mismatch")
        require(record["sha256"] == digest({k: v for k, v in record.items() if k != "sha256"}), "event digest mismatch")
        transition(projection, record["event"], record["material"], state["plan"], root, record["at"], False)
        previous = record["sha256"]
    require(encoded(projection) == encoded(state["projection"]), "projection/history mismatch")
    return projection


class Lock:
    def __init__(self, state_path):
        self.path = checked_path(str(state_path) + ".lock", exists=False)
        self.fd = None
    def __enter__(self):
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise LedgerError("ledger locked; inspect owner, never automatically steal lock") from exc
        os.write(self.fd, str(os.getpid()).encode("ascii"))
        return self
    def __exit__(self, *_):
        os.close(self.fd)
        self.path.unlink()


def atomic_write(path, value):
    checked_path(path, exists=False)
    data = encoded(value) + b"\n"
    require(len(data) <= 4_000_000, "ledger size limit reached; preserve it for operator review")
    fd, temp_name = tempfile.mkstemp(prefix=".progress-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        checked_path(path, exists=False)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def initialize(plan_path, state_path):
    path = checked_path(state_path, exists=False)
    with Lock(path):
        require(not path.exists(), "init refuses existing ledger")
        plan = read_json(plan_path)
        validate_plan(plan)
        for control in plan.get("controls", []):
            artifact(path.parent, control)
        state = {"schema": 1, "engine_sha256": file_hash(Path(__file__)), "plan": plan, "plan_sha256": digest(plan), "revision": 0,
                 "events": [], "projection": base_projection(plan)}
        atomic_write(path, state)
    return {"status": "INITIALIZED", "revision": 0, "authority": "none"}


def apply_event(state_path, event_path, expected_revision):
    path = checked_path(state_path)
    integer(expected_revision)
    with Lock(path):
        state = read_json(path)
        projection = replay(state, path.parent)
        require(state["revision"] == expected_revision, "revision conflict")
        event = read_json(event_path)
        validate_event(event)
        material = {}
        if event["type"] in ("verify", "resume", "reconcile"):
            document = read_json(reference(path.parent, event["receipt"]))
            material = {"document": document, "sha256": digest(document)}
        at = now()
        if state["events"]:
            require(timestamp(at) >= timestamp(state["events"][-1]["at"]), "clock moved backward")
        transition(projection, event, material, state["plan"], path.parent, at, True)
        record = {"at": at, "event": event, "material": material,
                  "previous": state["events"][-1]["sha256"] if state["events"] else state["plan_sha256"]}
        record["sha256"] = digest(record)
        state["events"].append(record)
        state["revision"] += 1
        state["projection"] = projection
        replay(state, path.parent)
        atomic_write(path, state)
    return {"status": "RECORDED", "revision": state["revision"], "authority": "none"}


def enterprise_completion(plan, current_subject):
    """Current verification at the parent boundary; a saved GO is never enough."""
    binding = plan["enterprise_assurance"]
    require(digest(current_subject) == binding["parent_subject_sha256"], "enterprise subject changed; reassessment required")
    runtime = Path(__file__).resolve().parents[2] / "enterprise-ai-assurance-loop" / "scripts"
    require((runtime / "enterprise_assurance/engine.py").is_file(), "enterprise verifier installation missing")
    sys.path.insert(0, str(runtime))
    try:
        from enterprise_assurance import engine as module
        from enterprise_assurance.common import read
        require(Path(module.__file__).resolve() == (runtime / "enterprise_assurance/engine.py").resolve(), "wrong enterprise verifier import")
        engine = module.Engine(checked_path(binding["state"]), read(checked_path(binding["trust"])), binding["trust_sha256"])
        decision = engine.decide(binding["run_id"])
    finally:
        sys.path.remove(str(runtime))
    require(decision["parent_goal"] == plan["goal"]["id"] and set(decision["criterion_ids"]) == set(plan["criteria"]), "enterprise parent acceptance mismatch")
    require(decision["subject_sha"] == binding["subject_sha256"] and decision["delivery_engine"] == binding["delivery_engine"], "enterprise subject or engine mismatch")
    require(decision["decision"] == "GO", "enterprise assurance remains NO_GO or ESCALATE")
    require(decision["proof"] == "ENTERPRISE", "ENTERPRISE_EVIDENCE_REQUIRED")
    return {"status": "ASSURANCE_ACCEPTED_WITHIN_SCOPE", "decision": decision, "deployment_authorized": False}


def next_action(state_path):
    path = checked_path(state_path)
    with Lock(path):
        state = read_json(path)
        projection = replay(state, path.parent)
        tasks = {t["id"]: t for t in state["plan"]["tasks"]}
        at = now()
        validity = {task_id: current_valid(projection, task_id, tasks, path.parent, at) for task_id in tasks}
        unresolved = sorted(set(state["plan"]["criteria"]) - {criterion for task_id, task in tasks.items()
                            if validity[task_id][0] for criterion in task["criteria"]})
        result = {"revision": state["revision"], "authority": "none", "evidence_scope": "recorded local integrity only",
                  "unresolved_criteria": unresolved, "tasks": []}
        actions = []
        for task_id, spec in tasks.items():
            task = projection["tasks"][task_id]
            deps = [dep for dep in spec["depends_on"] if not validity[dep][0]]
            cap = cap_reason(projection, task, state["plan"]["limits"])
            revalidation = revalidation_valid(projection, task_id, tasks, path.parent, at)
            help_integrity = []
            for response in task["help"]:
                try:
                    artifact(path.parent, response)
                    help_integrity.append({"reference": response, "current": True, "issue": None})
                except (LedgerError, OSError) as exc:
                    help_integrity.append({"reference": response, "current": False, "issue": str(exc)})
            info = {"task_id": task_id, "status": task["status"], "attempts": task["attempts"],
                    "current_attempt": task["current_attempt"],
                    "failures": task["failures"], "unresolved_dependencies": deps, "budget_blocker": cap,
                    "evidence_current": validity[task_id][0], "evidence_issue": validity[task_id][1],
                    "revalidation_current": revalidation[0], "revalidation_issue": revalidation[1],
                    "help_references": task["help"], "help_integrity": help_integrity, "blocker": task["blocker"]}
            result["tasks"].append(info)
            operation = task["operation"]
            if operation and operation["effect"] == "unknown":
                actions.append((0, {"action": "RECONCILE_EXTERNAL_EFFECT", "task_id": task_id, "operation_key": operation["key"]}))
            elif task["status"] == "active":
                actions.append((0, {"action": "INSPECT_INTERRUPTED_ATTEMPT", "task_id": task_id}))
            elif task["status"] in ("pending", "verify_existing") and not revalidation[0] and (not cap or task["status"] == "verify_existing"):
                actions.append((3, {"action": "REVALIDATE_HELP", "task_id": task_id, "authority": "must be checked separately"}))
            elif task["status"] == "verify_existing" and revalidation[0] and not deps:
                actions.append((1, {"action": "VERIFY_EXISTING_EFFECT", "task_id": task_id}))
            elif task["status"] == "verified" and not validity[task_id][0] and not deps:
                actions.append((1, {"action": "REVERIFY_EVIDENCE", "task_id": task_id}))
            elif task["status"] == "pending" and not deps and not cap and revalidation[0]:
                actions.append((2, {"action": "START_TASK", "task_id": task_id}))
            elif task["status"] == "blocked" and any(entry["current"] for entry in help_integrity) and not cap:
                actions.append((3, {"action": "REVALIDATE_HELP", "task_id": task_id, "authority": "must be checked separately"}))
        if all(value[0] for value in validity.values()):
            result["status"] = "READY_FOR_GOAL_REVIEW"
            result["action"] = "REVIEW_GOAL_AND_AUTHORITY"
            if "enterprise_assurance" in state["plan"]:
                try:
                    result["enterprise_assurance"] = enterprise_completion(state["plan"], projection["subject"])
                except (ValueError, OSError, ImportError, KeyError, sqlite3.Error) as exc:
                    result["status"] = "BLOCKED_ENTERPRISE_ASSURANCE"
                    result["action"] = "REASSESS_ENTERPRISE_EVIDENCE"
                    result["enterprise_assurance"] = {"status": "BLOCKED", "reason": str(exc), "deployment_authorized": False}
        elif actions:
            actions.sort(key=lambda pair: pair[0])
            result["status"] = "ACTION_REQUIRED"
            result["action"] = actions[0][1]
            result["available_actions"] = [entry[1] for entry in actions]
        else:
            capped = [t["task_id"] for t in result["tasks"] if not t["evidence_current"] and t["budget_blocker"]]
            result["status"] = "NEEDS_BUDGET_DECISION" if capped else "WAITING_FOR_HELP"
            result["action"] = "REQUEST_HELP_WITH_BLOCKERS"
            result["budget_blocked_tasks"] = capped
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--plan", required=True)
    init.add_argument("--state", required=True)
    read = sub.add_parser("next")
    read.add_argument("--state", required=True)
    apply = sub.add_parser("apply")
    apply.add_argument("--state", required=True)
    apply.add_argument("--event", required=True)
    apply.add_argument("--expected-revision", required=True, type=int)
    args = parser.parse_args()
    try:
        if args.command == "init":
            result = initialize(args.plan, args.state)
        elif args.command == "next":
            result = next_action(args.state)
        else:
            result = apply_event(args.state, args.event, args.expected_revision)
        print(json.dumps(result, indent=2))
        return 0
    except (LedgerError, OSError, RecursionError) as exc:
        print(json.dumps({"status": "INVALID_OR_BLOCKED", "error": str(exc), "authority": "none"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
