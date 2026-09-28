#!/usr/bin/env python3
"""Portable, finite local-cycle admission and execution. Not a sandbox or release executor."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

CONTRACT = "product-loop/local-cycle@1"
RELEASE = "BLOCKED_LEGACY_COMPATIBILITY"


class Refused(ValueError):
    pass


class ContainmentError(Refused):
    """Keep the reservation active if process-family termination is uncertain."""


def need(value, message):
    if not value:
        raise Refused(message)


def exact(obj, fields):
    need(isinstance(obj, dict) and set(obj) == set(fields), "invalid-fields:" + ",".join(fields))


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def path_check(value):
    path = Path(value).absolute()
    for part in [path, *path.parents]:
        if part.exists() or part.is_symlink():
            need(not part.is_symlink(), "symlink-path")
            need(not getattr(part.lstat(), "st_file_attributes", 0) & 1024, "reparse-path")
    return path


def sha(path):
    path = path_check(path)
    need(path.is_file(), "file-missing:" + str(path))
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def no_duplicates(pairs):
    obj = {}
    for key, value in pairs:
        need(key not in obj, "duplicate-json-key")
        obj[key] = value
    return obj


def read(path):
    path = path_check(path)
    need(path.stat().st_size <= 4_000_000, "json-too-large")
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates,
                          parse_constant=lambda _: (_ for _ in ()).throw(Refused("nonfinite-json")))
    except (UnicodeError, ValueError) as error:
        raise Refused("invalid-json") from error


def write(path, obj):
    path = path_check(path)
    data = canonical(obj)
    need(len(data) <= 4_000_000, "state-too-large")
    fd, name = tempfile.mkstemp(prefix=".cycle-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Lock:
    def __init__(self, state):
        self.path = path_check(str(state) + ".lock")

    def __enter__(self):
        try:
            self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as error:
            raise Refused("state-locked:inspect-owner-before-recovery") from error
        return self

    def __exit__(self, *_):
        os.close(self.fd)
        self.path.unlink()


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, timeout=15)
    need(result.returncode == 0, "git-command-failed:" + args[0])
    return result.stdout


def snapshot(repo):
    repo = path_check(repo)
    root = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    need(root == repo.resolve(), "wrong-repository-root")
    paths = sorted(set(git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard").decode().split("\0")) - {""})
    files = {}
    for name in paths:
        path = path_check(repo / name)
        need(path.is_relative_to(repo), "git-path-outside-repo")
        need(not path.is_dir(), "submodule-or-directory-not-supported")
        files[name] = sha(path) if path.exists() else "DELETED"
    return {"repo": str(repo.resolve()), "head": git(repo, "rev-parse", "HEAD").decode().strip(),
            "branch": git(repo, "branch", "--show-current").decode().strip(),
            "files_sha256": digest(files), "status_sha256": hashlib.sha256(git(repo, "status", "--porcelain=v1", "-z")).hexdigest()}


def text(value):
    return isinstance(value, str) and 0 < len(value) <= 4096


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def validate_config(config):
    exact(config, ["schema", "capability", "parent_goal", "identity", "argv", "pins", "limits", "expires_at_epoch", "environment"])
    need(type(config["schema"]) is int and config["schema"] == 1, "unsupported-schema")
    need(config["capability"] == "local-process", "release-and-provider-capabilities-blocked")
    exact(config["parent_goal"], ["id", "criteria"])
    need(text(config["parent_goal"]["id"]), "missing-parent-goal")
    criteria = config["parent_goal"]["criteria"]
    need(isinstance(criteria, list) and criteria and all(text(x) for x in criteria) and len(set(criteria)) == len(criteria), "invalid-parent-criteria")
    exact(config["identity"], ["repo", "head", "branch", "files_sha256", "status_sha256"])
    need(all(text(v) for v in config["identity"].values()), "invalid-identity")
    need(Path(config["identity"]["repo"]).is_absolute(), "repo-must-be-absolute")
    need(config["identity"]["branch"].startswith(("codex/", "loop/")), "branch-not-admitted")
    argv = config["argv"]
    need(isinstance(argv, list) and argv and all(text(x) and "\0" not in x for x in argv), "invalid-argv")
    need(Path(argv[0]).is_absolute(), "executable-must-be-absolute")
    need(Path(argv[0]).suffix.lower() not in (".cmd", ".bat", ".sh", ".ps1"), "shell-script-not-direct-executable")
    pins = config["pins"]
    need(isinstance(pins, list) and pins, "missing-bundle-pins")
    seen = set()
    for pin in pins:
        exact(pin, ["path", "sha256"])
        need(text(pin["path"]) and Path(pin["path"]).is_absolute(), "pin-must-be-absolute")
        need(isinstance(pin["sha256"], str) and re.fullmatch("[0-9a-f]{64}", pin["sha256"]), "pin-requires-full-sha256")
        normalized = str(Path(pin["path"]).resolve()).casefold()
        need(normalized not in seen, "duplicate-pin")
        seen.add(normalized)
    need(str(Path(argv[0]).resolve()).casefold() in seen, "executable-not-pinned")
    if os.name == "nt":
        need(str(Path(sys.executable).resolve()).casefold() in seen, "wrapper-python-not-pinned")
    exact(config["limits"], ["max_cycles", "wall_seconds", "per_cycle_seconds"])
    limits = config["limits"]
    need(type(limits["max_cycles"]) is int and 0 < limits["max_cycles"] <= 10000, "invalid-cycle-cap")
    need(positive(limits["wall_seconds"]) and positive(limits["per_cycle_seconds"]), "invalid-time-cap")
    need(limits["per_cycle_seconds"] <= limits["wall_seconds"], "cycle-exceeds-budget")
    need(positive(config["expires_at_epoch"]), "invalid-expiry")
    # No caller-provided secrets or provider-usage promises are accepted in this local lane.
    need(config["environment"] == "minimal-local", "unsupported-environment")


def load_config(path, expected_hash):
    need(isinstance(expected_hash, str) and re.fullmatch("[0-9a-f]{64}", expected_hash), "required-config-sha256")
    need(sha(path) == expected_hash, "config-hash-mismatch")
    config = read(path)
    validate_config(config)
    return config


def admission(config):
    validate_config(config)
    repo = path_check(config["identity"]["repo"])
    need(not (repo / ".loop" / "STOP").exists(), "STOP")
    need(time.time() < config["expires_at_epoch"], "configuration-expired")
    for pin in config["pins"]:
        need(sha(pin["path"]) == pin["sha256"], "bundle-drift:" + pin["path"])
    need(snapshot(repo) == config["identity"], "repository-identity-or-content-drift")
    return {"contract": CONTRACT, "status": "LOCAL_PROCESS_ADMITTED", "identity": config["identity"],
            "authority": "caller-must-enforce", "release": RELEASE, "parent_goal": config["parent_goal"]}


def seal(state):
    state["state_sha256"] = digest({k: v for k, v in state.items() if k != "state_sha256"})
    return state


def load_state(path, config):
    state = read(path)
    exact(state, ["schema", "config_digest", "engine_sha256", "cycles_reserved", "seconds_reserved", "active", "records", "parked", "state_sha256"])
    need(state["schema"] == 1 and state["config_digest"] == digest(config), "state-config-drift")
    need(state["engine_sha256"] == sha(__file__), "state-engine-drift")
    need(state["state_sha256"] == digest({k: v for k, v in state.items() if k != "state_sha256"}), "state-corrupt")
    need(type(state["cycles_reserved"]) is int and state["cycles_reserved"] >= 0, "invalid-reservations")
    need(type(state["seconds_reserved"]) in (int, float) and math.isfinite(state["seconds_reserved"]) and state["seconds_reserved"] >= 0, "invalid-reservations")
    need(isinstance(state["records"], list) and isinstance(state["parked"], dict), "invalid-state-ledgers")
    need(state["cycles_reserved"] == len(state["records"]) + (state["active"] is not None), "reservation-ledger-drift")
    need(state["seconds_reserved"] == state["cycles_reserved"] * config["limits"]["per_cycle_seconds"], "reservation-ledger-drift")
    return state


def initialize(path, config):
    path = path_check(path)
    need(not path.is_relative_to(Path(config["identity"]["repo"]).resolve()), "state-must-be-outside-product-repository")
    admission(config)
    with Lock(path):
        need(not path.exists(), "state-already-exists")
        state = seal({"schema": 1, "config_digest": digest(config), "engine_sha256": sha(__file__),
                      "cycles_reserved": 0, "seconds_reserved": 0, "active": None, "records": [], "parked": {}})
        write(path, state)
    return {"status": "INITIALIZED", "release": RELEASE}


def prerequisites(value):
    need(isinstance(value, dict) and value and all(text(k) and text(v) for k, v in value.items()), "invalid-prerequisites")
    return digest(value)


def parked_event(path, config, event):
    with Lock(path):
        state = load_state(path, config)
        need(state["active"] is None, "interrupted-cycle-requires-inspection")
        exact(event, ["action", "item", "prerequisites", "reason"])
        need(text(event["item"]) and text(event["reason"]), "invalid-park-record")
        fingerprint = prerequisites(event["prerequisites"])
        old = state["parked"].get(event["item"])
        if event["action"] == "park":
            state["parked"][event["item"]] = {"fingerprint": fingerprint, "reason": event["reason"], "reconsidered": old["reconsidered"] if old else []}
            status = "PARKED"
        elif event["action"] == "reconsider":
            need(old is not None, "item-not-parked")
            need(fingerprint != old["fingerprint"], "prerequisites-unchanged")
            need(fingerprint not in old["reconsidered"], "prerequisites-already-reconsidered")
            old["reconsidered"].append(fingerprint)
            status = "REVALIDATION_REQUIRED"
        else:
            raise Refused("invalid-park-action")
        write(path, seal(state))
    return {"status": status, "item": event["item"], "execution_authority": "none"}


class WindowsJob:
    """Assign a waiting wrapper before it can launch the requested command."""
    def __init__(self, child):
        from ctypes import wintypes as w
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        class Basic(ctypes.Structure):
            _fields_ = [("per_process",ctypes.c_longlong),("per_job",ctypes.c_longlong),("flags",w.DWORD),("min_ws",ctypes.c_size_t),("max_ws",ctypes.c_size_t),("active",w.DWORD),("affinity",ctypes.c_size_t),("priority",w.DWORD),("scheduling",w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name,ctypes.c_ulonglong) for name in ("ro","wo","oo","rt","wt","ot")]
        class Extended(ctypes.Structure):
            _fields_ = [("basic",Basic),("io",IO),("process_memory",ctypes.c_size_t),("job_memory",ctypes.c_size_t),("peak_process",ctypes.c_size_t),("peak_job",ctypes.c_size_t)]
        self.api.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR]; self.api.CreateJobObjectW.restype=w.HANDLE
        self.api.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD];self.api.SetInformationJobObject.restype=w.BOOL
        self.api.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];self.api.AssignProcessToJobObject.restype=w.BOOL
        self.api.TerminateJobObject.argtypes=[w.HANDLE,w.UINT];self.api.TerminateJobObject.restype=w.BOOL
        self.api.CloseHandle.argtypes=[w.HANDLE];self.api.CloseHandle.restype=w.BOOL
        self.api.QueryInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.c_void_p];self.api.QueryInformationJobObject.restype=w.BOOL
        self.handle=self.api.CreateJobObjectW(None,None)
        need(bool(self.handle),"Windows Job creation failed")
        info=Extended();info.basic.flags=0x2000
        try:
            need(bool(self.api.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info))),"Windows Job limits failed")
            need(bool(self.api.AssignProcessToJobObject(self.handle,int(child._handle))),"Windows Job assignment failed before dispatch")
        except BaseException:
            self.close()
            raise

    def stop(self):
        if not self.api.TerminateJobObject(self.handle,1):
            raise ContainmentError("Windows Job termination failed; reservation remains running")

    def close(self):
        if self.handle:
            from ctypes import wintypes as w
            class Accounting(ctypes.Structure):
                _fields_ = [("user",ctypes.c_longlong),("kernel",ctypes.c_longlong),("period_user",ctypes.c_longlong),("period_kernel",ctypes.c_longlong),("faults",w.DWORD),("total",w.DWORD),("active",w.DWORD),("terminated",w.DWORD)]
            try:
                self.stop()
                deadline=time.monotonic()+10
                while True:
                    info=Accounting()
                    if not self.api.QueryInformationJobObject(self.handle,1,ctypes.byref(info),ctypes.sizeof(info),None):
                        raise ContainmentError("cannot confirm Job descendants terminated")
                    if info.active==0: break
                    if time.monotonic()>=deadline:
                        raise ContainmentError("Job descendants not fully reaped")
                    time.sleep(.02)
            finally:
                closed=self.api.CloseHandle(self.handle)
                self.handle=None
                if not closed: raise ContainmentError("Windows Job close failed")


def terminate(proc, job=None):
    if job is not None:
        job.stop()
        proc.wait(timeout=10)
        return
    if proc.poll() is not None:
        return
    if os.name == "nt":
        # A wrapper without an assigned job is waiting for dispatch and has no child.
        proc.kill()
    else:
        os.killpg(proc.pid, signal.SIGKILL)
    proc.wait(timeout=10)


def validate_receipt(path, config, run_id):
    receipt = read(path)
    exact(receipt, ["contract", "run_id", "config_digest", "parent_goal", "result", "artifact"])
    need(receipt["contract"] == CONTRACT and receipt["run_id"] == run_id and receipt["config_digest"] == digest(config), "receipt-subject-mismatch")
    need(receipt["parent_goal"] == config["parent_goal"], "receipt-parent-mismatch")
    need(receipt["result"] in ("LOCAL_WORK_REPORTED", "PARKED", "REVIEWED"), "invalid-terminal-result")
    exact(receipt["artifact"], ["path", "sha256"])
    artifact = path_check(receipt["artifact"]["path"])
    need(artifact.is_relative_to(Path(config["identity"]["repo"]).resolve()), "artifact-outside-product")
    need(sha(artifact) == receipt["artifact"]["sha256"], "terminal-artifact-drift")
    return receipt


def run_cycle(path, config):
    path = path_check(path)
    with Lock(path):
        state = load_state(path, config)
        need(state["active"] is None, "interrupted-cycle-requires-inspection")
        admission(config)
        limits = config["limits"]
        need(state["cycles_reserved"] < limits["max_cycles"], "cycle-budget-exhausted")
        reserve = limits["per_cycle_seconds"]
        need(state["seconds_reserved"] + reserve <= limits["wall_seconds"], "wall-budget-exhausted")
        number = state["cycles_reserved"] + 1
        run_id = f"{digest(config)}:{number}"
        receipt_path = path_check(str(path) + f".cycle-{number}.json")
        need(not receipt_path.exists(), "preexisting-terminal-receipt")
        state["cycles_reserved"] = number
        state["seconds_reserved"] = number * reserve
        state["active"] = {"run_id": run_id, "started_at_epoch": time.time()}
        write(path, seal(state))  # Reservation survives a crash before process creation.
        started = time.monotonic()
        proc = None
        job = None
        result = "FAILED"
        receipt = None
        error = None
        try:
            admission(config)  # Recheck after reservation and immediately before invocation.
            env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "TEMP", "TMP", "PATH") if key in os.environ}
            env.update({"LOOP_RUN_ID": run_id, "LOOP_CONFIG_DIGEST": digest(config), "LOOP_RECEIPT_PATH": str(receipt_path),
                        "LOOP_PARENT_GOAL": json.dumps(config["parent_goal"]), "PYTHONDONTWRITEBYTECODE": "1"})
            argv = config["argv"]
            if os.name == "nt":
                wrapper = "import sys,subprocess,json; token=sys.stdin.buffer.read(1); sys.exit(subprocess.run(json.loads(sys.argv[1]),stdin=subprocess.DEVNULL).returncode if token == b'G' else 125)"
                argv = [sys.executable, "-B", "-c", wrapper, json.dumps(argv)]
            proc = subprocess.Popen(argv, cwd=config["identity"]["repo"], env=env,
                                    stdin=subprocess.PIPE if os.name == "nt" else subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    start_new_session=os.name != "nt")
            if os.name == "nt":
                job = WindowsJob(proc)
            state["active"]["pid"] = proc.pid
            write(path, seal(state))
            if os.name == "nt":
                admission(config)
                proc.stdin.write(b"G")
                proc.stdin.flush()
                proc.stdin.close()
            while proc.poll() is None:
                if (Path(config["identity"]["repo"]) / ".loop" / "STOP").exists():
                    result = "CANCELLED"
                    terminate(proc, job)
                    break
                if time.monotonic() - started >= reserve or time.time() >= config["expires_at_epoch"]:
                    result = "TIMED_OUT"
                    terminate(proc, job)
                    break
                time.sleep(0.025)
            if result not in ("CANCELLED", "TIMED_OUT"):
                need(proc.returncode == 0, "child-nonzero-exit")
                receipt = validate_receipt(receipt_path, config, run_id)
                result = "CYCLE_REPORTED"
        except (Refused, OSError, subprocess.SubprocessError) as exc:
            error = str(exc)
            if (Path(config["identity"]["repo"]) / ".loop" / "STOP").exists():
                result = "CANCELLED"
            if proc is not None and proc.poll() is None:
                try:
                    terminate(proc, job)
                except (Refused, OSError, subprocess.SubprocessError) as cancellation_error:
                    error += "; cancellation: " + str(cancellation_error)
        finally:
            if proc is not None and getattr(proc,"stdin",None) is not None and not proc.stdin.closed:
                try:
                    proc.stdin.close()
                except OSError:
                    pass
            if job is not None:
                try:
                    job.close()
                except (Refused,OSError) as close_error:
                    result="UNKNOWN_CANCELLATION"
                    error=(error or "")+"; containment: "+str(close_error)
            elapsed = time.monotonic() - started
            if proc is not None and proc.poll() is None:
                result = "UNKNOWN_CANCELLATION"
            record = {"run_id": run_id, "status": result, "elapsed_seconds": elapsed, "reserved_seconds": reserve,
                      "returncode": proc.returncode if proc else None, "receipt": receipt, "error": error,
                      "parent_acceptance": "NOT_EVALUATED", "release": RELEASE}
            if result == "UNKNOWN_CANCELLATION":
                state["active"]["uncertainty"] = record
            else:
                state["records"].append(record)
                state["active"] = None
            write(path, seal(state))
        return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["snapshot", "admit", "init", "run", "park"])
    parser.add_argument("--repo")
    parser.add_argument("--config")
    parser.add_argument("--config-sha256")
    parser.add_argument("--state")
    parser.add_argument("--event")
    args = parser.parse_args(argv)
    try:
        if args.action == "snapshot":
            need(args.repo is not None, "repo-required")
            result = snapshot(args.repo)
        else:
            need(args.config is not None, "config-required")
            config = load_config(args.config, args.config_sha256)
            if args.action == "admit":
                result = admission(config)
            else:
                need(args.state is not None, "state-required")
                if args.action == "init":
                    result = initialize(args.state, config)
                elif args.action == "run":
                    result = run_cycle(args.state, config)
                else:
                    need(args.event is not None, "event-required")
                    result = parked_event(args.state, config, read(args.event))
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("status") not in {"FAILED", "CANCELLED", "TIMED_OUT", "UNKNOWN_CANCELLATION"} else 2
    except (Refused, OSError, subprocess.SubprocessError, TypeError, KeyError) as error:
        print(json.dumps({"status": "BLOCKED", "reason": str(error), "release": RELEASE}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
