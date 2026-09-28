"""Cooperative, local SQLite fleet admission and bounded process execution.

No provider billing authority, distributed lock, sandbox or automatic git merge.
Reservations are charged in full, including failed/cancelled/unknown attempts.
"""
import argparse
import contextlib
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
import uuid


class FleetError(ValueError):
    pass


class ContainmentError(RuntimeError):
    """Do not release a running reservation when termination cannot be proved."""


def need(condition, message):
    if not condition:
        raise FleetError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def positive(value):
    return type(value) is int and 0 < value <= 10**9


def duration(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 < value <= 10**9


def claims_valid(claims):
    need(isinstance(claims, list) and claims, "nonempty resource claims required")
    for item in claims:
        need(isinstance(item, dict) and set(item) == {"resource", "mode"}, "invalid claim")
        resource = item["resource"]
        need(isinstance(resource, str) and resource == resource.lower() and len(resource) <= 500, "canonical lowercase resource required")
        need(resource == "*" or (resource.startswith(("file:", "contract:", "state:")) and len(resource.split(":", 1)[1]) > 0), "resource namespace required")
        need("\\" not in resource and ".." not in resource and "//" not in resource, "noncanonical resource")
        need(item["mode"] in ("read", "write"), "invalid claim mode")
        need(resource != "*" or item["mode"] == "write", "unknown resources require exclusive claim")


def conflict(a, b):
    for x in a:
        for y in b:
            p, q = x["resource"], y["resource"]
            overlap = p == "*" or q == "*" or p == q or p.startswith(q.rstrip("/") + "/") or q.startswith(p.rstrip("/") + "/")
            if overlap and "write" in (x["mode"], y["mode"]):
                return True
    return False


class Fleet:
    def __init__(self, path):
        self.path = str(Path(path).resolve())

    @contextlib.contextmanager
    def tx(self):
        need(Path(self.path).is_file(), "fleet database missing; explicit init required")
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def init(self, subject, budget, concurrency, spawns, deadline_seconds, workspace=None):
        need(isinstance(subject, dict) and set(subject) == {"product", "target", "revision", "configuration"}, "exact subject required")
        need(all(isinstance(v, str) and v.strip() for v in subject.values()), "nonempty subject values required")
        need(all(positive(x) for x in (budget, concurrency, spawns, deadline_seconds)), "positive integer limits required")
        workspace = str(Path(workspace or Path(self.path).parent).resolve())
        need(Path(workspace).is_dir(), "existing workspace required")
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        db = sqlite3.connect(self.path)
        try:
            db.executescript("""
              CREATE TABLE fleet (id INTEGER PRIMARY KEY CHECK(id=1), subject TEXT, budget INTEGER,
                concurrency INTEGER, spawns INTEGER, deadline REAL, owner TEXT, fence INTEGER,
                lease_until REAL, cancel INTEGER, integration TEXT, integration_charge INTEGER, workspace TEXT);
              CREATE TABLE jobs (id TEXT PRIMARY KEY, claims TEXT, reserve INTEGER, status TEXT,
                owner TEXT, fence INTEGER, pid INTEGER, result TEXT);
            """)
            db.execute("INSERT INTO fleet VALUES (1,?,?,?,?,?,?,0,0,0,'pending',0,?)", (json.dumps(subject, sort_keys=True), budget, concurrency, spawns, time.time()+deadline_seconds, "",workspace))
            db.commit()
        finally:
            db.close()

    def acquire(self, owner, seconds=30):
        need(isinstance(owner, str) and owner and positive(seconds), "owner and lease duration required")
        with self.tx() as db:
            row = db.execute("SELECT * FROM fleet").fetchone()
            need(row["lease_until"] <= time.time(), "coordinator lease occupied")
            need(db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0] == 0, "unreconciled workers; takeover refused")
            need(row["integration"] != "running", "unreconciled integration; takeover refused")
            fence = row["fence"]+1
            db.execute("UPDATE fleet SET owner=?,fence=?,lease_until=?", (owner, fence, time.time()+seconds))
            return fence

    def guarded(self, db, owner, fence):
        row = db.execute("SELECT * FROM fleet").fetchone()
        need(row["owner"] == owner and row["fence"] == fence and row["lease_until"] > time.time(), "stale coordinator fence or expired lease")
        return row

    def renew(self, owner, fence, seconds=30):
        need(positive(seconds), "invalid lease duration")
        with self.tx() as db:
            self.guarded(db, owner, fence)
            db.execute("UPDATE fleet SET lease_until=?", (time.time()+seconds,))

    def admit(self, owner, fence, job_id, claims, reserve):
        need(isinstance(job_id, str) and job_id.strip() and len(job_id) < 200, "job identity required")
        claims_valid(claims)
        need(positive(reserve), "positive worst-case reservation required")
        with self.tx() as db:
            row = self.guarded(db, owner, fence)
            need(not row["cancel"] and row["deadline"] > time.time(), "fleet cancelled or deadline exhausted")
            need(row["integration"] == "pending", "integration started; further admission refused")
            jobs = db.execute("SELECT * FROM jobs").fetchall()
            need(not any(j["id"] == job_id for j in jobs), "duplicate job identity")
            need(len(jobs) < row["spawns"], "spawn ceiling exhausted")
            need(sum(j["reserve"] for j in jobs)+reserve <= row["budget"], "aggregate reservation exceeds budget")
            active = [j for j in jobs if j["status"] == "running"]
            need(len(active) < row["concurrency"], "concurrency ceiling exhausted")
            need(not any(conflict(claims, json.loads(j["claims"])) for j in active), "shared resource conflict")
            db.execute("INSERT INTO jobs VALUES (?,?,?,'running',?,?,NULL,NULL)", (job_id,json.dumps(claims),reserve,owner,fence))
            return {"job_id":job_id,"reservation":reserve,"fence":fence}

    def attach(self, owner, fence, job_id, pid):
        with self.tx() as db:
            row = self.guarded(db, owner, fence)
            need(not row["cancel"], "fleet cancelled before process attachment")
            changed = db.execute("UPDATE jobs SET pid=? WHERE id=? AND owner=? AND fence=? AND status='running' AND pid IS NULL", (pid,job_id,owner,fence)).rowcount
            need(changed == 1, "job not attachable")

    def finish(self, owner, fence, job_id, status, result):
        need(status in ("succeeded", "failed", "cancelled", "timed_out"), "invalid completion status")
        with self.tx() as db:
            self.guarded(db, owner, fence)
            changed = db.execute("UPDATE jobs SET status=?,result=? WHERE id=? AND owner=? AND fence=? AND status='running'", (status,json.dumps(result,sort_keys=True),job_id,owner,fence)).rowcount
            need(changed == 1, "job not completable")

    def cancel(self):
        with self.tx() as db:
            db.execute("UPDATE fleet SET cancel=1")

    def snapshot(self):
        with self.tx() as db:
            fleet = dict(db.execute("SELECT * FROM fleet").fetchone())
            jobs = [dict(r) for r in db.execute("SELECT * FROM jobs ORDER BY id")]
            return {"fleet":fleet, "jobs":jobs, "charged":sum(j["reserve"] for j in jobs)+fleet["integration_charge"], "authority":"local cooperative accounting only"}


def validate_command(argv, cwd):
    need(isinstance(argv, list) and argv and all(isinstance(a,str) and a and "\x00" not in a for a in argv), "nonempty argv required; no shell strings")
    need(Path(argv[0]).is_absolute() and Path(argv[0]).is_file(), "absolute executable required")
    need(Path(cwd).is_absolute() and Path(cwd).is_dir(), "existing absolute cwd required")


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
                        raise ContainmentError("cannot confirm Job is empty")
                    if info.active == 0:
                        break
                    if time.monotonic() >= deadline:
                        raise ContainmentError("Job descendants not fully reaped")
                    time.sleep(.02)
            finally:
                self.api.CloseHandle(self.handle)
                self.handle=None


def terminate_tree(child, job=None):
    if job is not None:
        job.stop()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired as exc:
            raise ContainmentError("terminated worker not reaped") from exc
        return
    if child.poll() is not None:
        return
    if os.name == "nt":
        # Before Job assignment this wrapper is blocked on stdin and has no child.
        child.kill()
    else:
        os.killpg(child.pid, signal.SIGKILL)
    child.wait(timeout=10)


def bounded(fleet, owner, fence, argv, cwd, seconds, attached=None):
    validate_command(argv, cwd)
    need(duration(seconds), "positive finite process duration required")
    child = None
    job = None
    started = time.monotonic()
    try:
        fleet.renew(owner, fence)
        state = fleet.snapshot()["fleet"]
        need(not state["cancel"] and state["deadline"] > time.time(), "fleet cancelled or deadline exhausted")
        actual_argv = argv
        if os.name == "nt":
            wrapper = "import sys,subprocess,json; token=sys.stdin.buffer.read(1); sys.exit(subprocess.run(json.loads(sys.argv[1]),stdin=subprocess.DEVNULL).returncode if token == b'G' else 125)"
            actual_argv = [sys.executable,"-B","-c",wrapper,json.dumps(argv)]
        child = subprocess.Popen(actual_argv, cwd=cwd, stdin=subprocess.PIPE if os.name == "nt" else subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, shell=False,
                                 start_new_session=(os.name != "nt"))
        if os.name == "nt":
            job=WindowsJob(child)
        if attached:
            attached(child.pid)
        if os.name == "nt":
            child.stdin.write(b"G");child.stdin.flush();child.stdin.close()
        while child.poll() is None:
            fleet.renew(owner, fence)
            state = fleet.snapshot()["fleet"]
            reason = "cancelled" if state["cancel"] else "timed_out" if time.monotonic()-started >= seconds or state["deadline"] <= time.time() else None
            if reason:
                terminate_tree(child,job)
                return {"status":reason,"exit_code":child.returncode,"pid":child.pid,"reaped":True}
            time.sleep(.05)
        return {"status":"succeeded" if child.returncode == 0 else "failed","exit_code":child.returncode,"pid":child.pid,"reaped":True}
    except BaseException:
        if child is not None:
            terminate_tree(child,job)
        raise
    finally:
        if job is not None:
            job.close()


def artifact_paths(artifacts):
    need(isinstance(artifacts, list) and artifacts and all(isinstance(x,str) and x and not Path(x).is_absolute() and ".." not in Path(x).parts and ":" not in x and "\\" not in x for x in artifacts), "canonical relative output artifacts required")
    need(len(artifacts) == len(set(artifacts)), "unique output artifacts required")


def artifact_hashes(cwd, artifacts):
    artifact_paths(artifacts)
    root = Path(cwd).resolve()
    output = {}
    for name in artifacts:
        need(isinstance(name,str) and name and not Path(name).is_absolute() and ".." not in Path(name).parts, "relative output path required")
        path = root/name
        need(path.is_file() and path.resolve().is_relative_to(root), "output missing or escapes working directory")
        output[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return output


def file_snapshot(fleet, cwd):
    """Observe actual working-directory changes; declarations still own semantics."""
    workspace=Path(fleet.snapshot()["fleet"]["workspace"])
    root=Path(cwd).resolve()
    need(root.is_relative_to(workspace),"worker cwd must be under declared workspace")
    files={}; total=0
    for folder, dirs, names in os.walk(root,followlinks=False):
        need(not any((Path(folder)/d).is_symlink() for d in dirs),"symlink directories require isolated prepared workspace")
        dirs[:]=[d for d in dirs if d != ".git"]
        for name in names:
            path=Path(folder)/name
            if str(path) in (fleet.path,fleet.path+"-journal",fleet.path+"-wal",fleet.path+"-shm"):
                continue
            need(not path.is_symlink(),"symlink files require isolated prepared workspace")
            size=path.stat().st_size;total+=size
            need(total <= 64*1024*1024,"snapshot exceeds 64 MiB; prepare bounded isolated workspace")
            files[path.relative_to(workspace).as_posix().lower()]=hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def run_job(fleet, owner, fence, job_id, claims, reserve, argv, cwd, seconds, artifacts):
    validate_command(argv, cwd)
    need(duration(seconds), "positive finite duration required")
    # Validate output path declarations before admitting an effectful command.
    artifact_paths(artifacts)
    before = file_snapshot(fleet,cwd)
    fleet.admit(owner, fence, job_id, claims, reserve)
    try:
        result = bounded(fleet,owner,fence,argv,cwd,seconds, lambda pid:fleet.attach(owner,fence,job_id,pid))
        if result["status"] == "succeeded":
            after=file_snapshot(fleet,cwd)
            changed=sorted(p for p in set(before)|set(after) if before.get(p) != after.get(p))
            writes=[c for c in claims if c["mode"] == "write"]
            need(all(conflict(writes,[{"resource":"file:"+p,"mode":"write"}]) for p in changed),"actual changed files exceed reserved surfaces")
            result["observed_changed_files"]=changed
            result["artifacts"] = artifact_hashes(cwd,artifacts)
            result["cwd"] = str(Path(cwd).resolve())
        result["invocation_sha256"] = digest({"argv":argv,"cwd":cwd,"seconds":seconds,"claims":claims,"artifacts":artifacts})
        fleet.finish(owner,fence,job_id,result["status"],result)
        return result
    except (FleetError,OSError,subprocess.SubprocessError) as exc:
        # Lease loss cannot release admission; unresolved work blocks takeover.
        fleet.finish(owner,fence,job_id,"failed",{"error":str(exc)})
        raise


def integrate(fleet, owner, fence, plan):
    need(isinstance(plan,dict) and set(plan) == {"expected_jobs","steps","verify","cwd","seconds","artifacts","criteria","reserve"}, "exact integration plan required")
    need(isinstance(plan["steps"],list), "serial integration steps required")
    need(isinstance(plan["criteria"],list) and plan["criteria"] and all(isinstance(x,str) and x.strip() for x in plan["criteria"]), "nonempty parent acceptance criteria required")
    for argv in plan["steps"]+[plan["verify"]]:
        validate_command(argv,plan["cwd"])
    need(duration(plan["seconds"]), "positive finite integration duration required")
    need(positive(plan["reserve"]), "integration reservation required")
    artifact_paths(plan["artifacts"])
    with fleet.tx() as db:
        state = fleet.guarded(db,owner,fence)
        need(not state["cancel"] and state["deadline"] > time.time(), "fleet unavailable")
        need(state["integration"] == "pending", "integration already started")
        jobs = db.execute("SELECT * FROM jobs ORDER BY id").fetchall()
        need(isinstance(plan["expected_jobs"],list) and len(plan["expected_jobs"]) == len(set(plan["expected_jobs"])), "unique expected job IDs required")
        need(jobs and sorted(plan["expected_jobs"]) == [j["id"] for j in jobs], "exact full job set required")
        need(all(j["status"] == "succeeded" for j in jobs), "every job must succeed before integration")
        need(sum(j["reserve"] for j in jobs)+plan["reserve"] <= state["budget"], "integration exceeds aggregate budget")
        for j in jobs:
            result = json.loads(j["result"])
            need(artifact_hashes(result["cwd"],list(result["artifacts"])) == result["artifacts"], "worker evidence drift")
        evidence = digest([dict(j) for j in jobs])
        subject = json.loads(state["subject"])
        db.execute("UPDATE fleet SET integration='running',integration_charge=?",(plan["reserve"],))
    results = []
    started = time.monotonic()
    try:
        for argv in plan["steps"]+[plan["verify"]]:
            remaining = plan["seconds"]-(time.monotonic()-started)
            need(remaining > 0, "integration total duration exhausted")
            result = bounded(fleet,owner,fence,argv,plan["cwd"],remaining)
            results.append(result)
            need(result["status"] == "succeeded", "serial integration or final acceptance failed")
        hashes = artifact_hashes(plan["cwd"],plan["artifacts"])
        receipt = {"status":"INTEGRATED_LOCALLY","subject":subject,"parent_criteria":plan["criteria"],"plan_sha256":digest(plan),"worker_evidence_sha256":evidence,"artifacts":hashes,"executions":results,"authority":"no production promotion"}
        with fleet.tx() as db:
            fleet.guarded(db,owner,fence)
            need(not db.execute("SELECT cancel FROM fleet").fetchone()[0], "cancelled before integration acceptance")
            db.execute("UPDATE fleet SET integration=?",(json.dumps(receipt,sort_keys=True),))
        return receipt
    except ContainmentError:
        raise
    except BaseException:
        with fleet.tx() as db:
            fleet.guarded(db,owner,fence)
            db.execute("UPDATE fleet SET integration='failed'")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    parser.add_argument("action",choices=("init","acquire","renew","admit","run","integrate","cancel","status"))
    parser.add_argument("--input",help="JSON object matching the action's Python arguments")
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8")) if args.input else {}
    fleet = Fleet(args.database)
    if args.action == "run":
        result = run_job(fleet,**data)
    elif args.action == "integrate":
        result = integrate(fleet,**data)
    elif args.action == "status":
        result = fleet.snapshot()
    else:
        result = getattr(fleet,args.action)(**data)
    print(json.dumps({"result":result,"authority":"local cooperative only"},sort_keys=True))
    return 2 if isinstance(result,dict) and result.get("status") in ("failed","cancelled","timed_out") else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (FleetError,OSError,sqlite3.Error,TypeError,KeyError) as exc:
        print(json.dumps({"status":"BLOCKED","reason":str(exc)}))
        sys.exit(2)
