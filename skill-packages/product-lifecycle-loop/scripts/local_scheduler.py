"""Finite local scheduler for the pinned product-loop cycle adapter.

SQLite serializes cooperating schedulers. This is not an OS sandbox, hosted daemon,
provider money meter, authorization service, or semantic completion verifier.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import sys
import time

import progress_state as ledger


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def connect(path):
    path = ledger.checked_path(path, exists=False)
    connection = sqlite3.connect(path, timeout=15, isolation_level=None, factory=ClosingConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, spec TEXT NOT NULL, status TEXT NOT NULL, due REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, seconds_reserved REAL NOT NULL DEFAULT 0, active TEXT, last_result TEXT)")
    connection.execute("CREATE TABLE IF NOT EXISTS help (id TEXT PRIMARY KEY, goal TEXT NOT NULL, request_sha TEXT NOT NULL, destination TEXT NOT NULL, delivered_sha TEXT NOT NULL, response TEXT)")
    return connection


def number(value):
    ledger.require(type(value) in (int, float) and math.isfinite(value) and value > 0, "positive finite number required")


def pin(value):
    ledger.exact(value, ("path", "sha256"))
    ledger.require(Path(value["path"]).is_absolute(), "pin path must be absolute")
    ledger.require(ledger.file_hash(ledger.checked_path(value["path"])) == value["sha256"], "pin changed")


def validate(spec):
    ledger.exact(spec, ("id", "goal", "python", "adapter", "config", "cycle_state", "interval_seconds", "max_dispatches", "per_dispatch_seconds", "total_seconds", "due_epoch"))
    ledger.require(isinstance(spec["id"], str) and re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", spec["id"]), "invalid job id")
    ledger.string(spec["goal"])
    for item in ("python", "adapter", "config"): pin(spec[item])
    ledger.require(Path(spec["cycle_state"]).is_absolute(), "absolute cycle state required")
    ledger.checked_path(spec["cycle_state"])
    for item in ("interval_seconds", "per_dispatch_seconds", "total_seconds", "due_epoch"): number(spec[item])
    ledger.integer(spec["max_dispatches"], 1)
    ledger.require(spec["max_dispatches"] <= 10000 and spec["per_dispatch_seconds"] <= spec["total_seconds"], "invalid dispatch ceiling")
    config = ledger.read_json(spec["config"]["path"])
    ledger.require(config.get("capability") == "local-process" and config.get("parent_goal", {}).get("id") == spec["goal"], "wrong capability or parent goal")
    return config


def register(db, spec):
    validate(spec)
    with connect(db) as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing_goals=[json.loads(row[0])["goal"] for row in connection.execute("SELECT spec FROM jobs")]
        ledger.require(spec["goal"] not in existing_goals,"goal already has a schedule; preserve its cumulative budget")
        try:
            connection.execute("INSERT INTO jobs(id,spec,status,due) VALUES(?,?,?,?)", (spec["id"], json.dumps(spec), "READY", spec["due_epoch"]))
        except sqlite3.IntegrityError as exc:
            raise ledger.LedgerError("job already exists; cannot reset its budget") from exc
        connection.commit()
    return {"status": "REGISTERED", "job": spec["id"], "authority": "none"}


def status(db):
    with connect(db) as connection:
        return {"jobs": [dict(row) for row in connection.execute("SELECT id,status,due,attempts,seconds_reserved,active,last_result FROM jobs ORDER BY id")], "authority": "none"}


def reconfigure(db, spec, previous_spec_sha):
    new_config=validate(spec)
    with connect(db) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row=connection.execute("SELECT * FROM jobs WHERE id=?",(spec["id"],)).fetchone()
        ledger.require(row and row["status"] in ("READY","BLOCKED"),"job must be idle and inspected before reconfiguration")
        old=json.loads(row["spec"])
        ledger.require(ledger.digest(old)==previous_spec_sha,"previous schedule specification changed")
        for key in ("id","goal","max_dispatches","per_dispatch_seconds","total_seconds"):
            ledger.require(spec[key]==old[key],"schedule goal and resource ceilings remain fixed")
        old_config=ledger.read_json(old["config"]["path"])
        ledger.require(ledger.file_hash(Path(old["config"]["path"]))==old["config"]["sha256"],"retain old configuration bytes for reconfiguration review")
        ledger.require(old_config["identity"]["repo"]==new_config["identity"]["repo"] and old_config["parent_goal"]==new_config["parent_goal"],"repository and parent acceptance remain fixed")
        connection.execute("UPDATE jobs SET spec=?,status='READY',due=? WHERE id=?",(json.dumps(spec),spec["due_epoch"],spec["id"]))
        connection.commit()
    return {"status":"RECONFIGURED", "attempts":"preserved", "authority":"none"}


def complete(db, job_id, review_path, expected_sha):
    ledger.require(ledger.file_hash(Path(review_path))==expected_sha,"goal review changed")
    review=ledger.read_json(review_path)
    ledger.exact(review,("goal","reviewer","result","state","artifact"))
    ledger.string(review["reviewer"])
    ledger.require(review["result"]=="GOAL_VERIFIED","final goal review required")
    with connect(db) as connection:
        scheduled=connection.execute("SELECT spec FROM jobs WHERE id=?",(job_id,)).fetchone()
    ledger.require(scheduled is not None,"scheduled job missing")
    spec=json.loads(scheduled["spec"])
    config=validate(spec)
    pin(review["state"]);pin(review["artifact"])
    state=ledger.read_json(review["state"]["path"])
    ledger.require(state["plan"]["goal"]["id"]==review["goal"],"goal state mismatch")
    ledger.require(set(state["plan"]["criteria"])==set(config["parent_goal"]["criteria"]),"scheduled acceptance criteria mismatch")
    expected_subject={"product":config["identity"]["repo"],"target":"local-process","revision":config["identity"]["head"],"configuration":spec["config"]["sha256"]}
    ledger.require(state["projection"]["subject"]==expected_subject,"scheduled subject mismatch")
    ledger.require(ledger.next_action(review["state"]["path"])["status"]=="READY_FOR_GOAL_REVIEW","mandatory goal criteria not current")
    admitted=subprocess.run([spec["python"]["path"],"-B",spec["adapter"]["path"],"admit","--config",spec["config"]["path"],"--config-sha256",spec["config"]["sha256"]],capture_output=True,timeout=60)
    ledger.require(admitted.returncode==0 and len(admitted.stdout)<=4_000_000,"current repository admission failed")
    ledger.require(json.loads(admitted.stdout).get("status")=="LOCAL_PROCESS_ADMITTED","current repository admission missing")
    with connect(db) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row=connection.execute("SELECT * FROM jobs WHERE id=?",(job_id,)).fetchone()
        ledger.require(row and row["status"] in ("READY","BLOCKED","BUDGET_EXHAUSTED"),"job must be idle before goal completion")
        ledger.require(row["spec"]==scheduled["spec"],"schedule changed during completion review")
        ledger.require(json.loads(row["spec"])["goal"]==review["goal"],"scheduled goal mismatch")
        # Recheck immediately before persisting; records remain local assertions.
        pin(review["state"]);pin(review["artifact"])
        connection.execute("UPDATE jobs SET status='COMPLETED',last_result=? WHERE id=?",(json.dumps({"review":str(Path(review_path).absolute()),"sha256":expected_sha,"semantic_truth":"caller verified"}),job_id))
        connection.commit()
    return {"status":"COMPLETED", "authority":"none"}


def kill_owned(proc):
    if proc.poll() is not None: return True
    try:
        if os.name == "nt":
            subprocess.run([str(Path(os.environ["SystemRoot"])/"System32/taskkill.exe"), "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=10)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=10)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def cancel(db, job_id):
    with connect(db) as connection:
        changed = connection.execute("UPDATE jobs SET status=CASE WHEN status='RUNNING' THEN 'CANCEL_REQUESTED' ELSE 'CANCELLED' END WHERE id=? AND status IN ('READY','RUNNING')", (job_id,)).rowcount
    ledger.require(changed == 1, "job not ready/running")
    return {"status": "CANCELLATION_REQUESTED", "job": job_id}


def tick(db):
    connection = connect(db)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT * FROM jobs WHERE status='READY' AND due<=? ORDER BY due,id LIMIT 1", (time.time(),)).fetchone()
        if row is None:
            connection.commit()
            return {"status": "NO_DUE_WORK"}
        spec = json.loads(row["spec"])
        try: validate(spec)
        except (ledger.LedgerError, OSError) as exc:
            connection.execute("UPDATE jobs SET status='BLOCKED',last_result=? WHERE id=?", (json.dumps({"error": str(exc)}), row["id"]))
            connection.commit()
            return {"status": "BLOCKED", "job": row["id"], "error": str(exc)}
        reservation = spec["per_dispatch_seconds"]
        if row["attempts"] >= spec["max_dispatches"] or row["seconds_reserved"] + reservation > spec["total_seconds"]:
            connection.execute("UPDATE jobs SET status='BUDGET_EXHAUSTED' WHERE id=?", (row["id"],))
            connection.commit()
            return {"status": "BUDGET_EXHAUSTED", "job": row["id"]}
        run_id = f"{row['id']}:{row['attempts']+1}"
        connection.execute("UPDATE jobs SET status='RUNNING',active=?,attempts=attempts+1,seconds_reserved=seconds_reserved+? WHERE id=?", (run_id, reservation, row["id"]))
        connection.commit()
    finally:
        connection.close()
    # A crash after reservation stays RUNNING. Never reclaim it from age or a saved PID.
    result = {"status": "UNKNOWN", "job": spec["id"], "run_id": run_id, "parent_acceptance": "NOT_EVALUATED"}
    proc = None
    started = time.monotonic()
    output = Path(db).absolute().with_name(f".{spec['id']}-{row['attempts']+1}.dispatch.log")
    try:
        validate(spec)
        ledger.require(not output.exists(), "dispatch log already exists")
        with output.open("xb") as stream:
            proc = subprocess.Popen([spec["python"]["path"], "-B", spec["adapter"]["path"], "run", "--config", spec["config"]["path"], "--config-sha256", spec["config"]["sha256"], "--state", spec["cycle_state"]], stdin=subprocess.DEVNULL, stdout=stream, stderr=stream, start_new_session=os.name != "nt")
            while proc.poll() is None:
                with connect(db) as connection:
                    cancelled = connection.execute("SELECT status FROM jobs WHERE id=?", (spec["id"],)).fetchone()[0] == "CANCEL_REQUESTED"
                if cancelled or time.monotonic()-started >= reservation:
                    result["status"] = ("CANCELLED" if cancelled else "TIMED_OUT") if kill_owned(proc) else "UNKNOWN"
                    break
                time.sleep(0.025)
        if result["status"] == "UNKNOWN" and proc.poll() is not None:
            ledger.require(output.stat().st_size <= 4_000_000, "adapter output exceeds cap")
            child = ledger.read_json(output)
            ledger.require(isinstance(child, dict), "invalid adapter result")
            if proc.returncode == 0 and child.get("status") == "CYCLE_REPORTED":
                result.update(status="CYCLE_REPORTED", child=child)
            else:
                result.update(status="BLOCKED", child=child)
    except (ledger.LedgerError, OSError, subprocess.SubprocessError) as exc:
        result["error"] = str(exc)
        if proc is None:
            result["status"] = "BLOCKED"
        elif proc.poll() is None:
            result["status"] = "BLOCKED" if kill_owned(proc) else "UNKNOWN"
    result["elapsed_seconds"] = time.monotonic()-started
    result["reserved_seconds"] = reservation
    with connect(db) as connection:
        connection.execute("BEGIN IMMEDIATE")
        latest = connection.execute("SELECT status,active FROM jobs WHERE id=?", (spec["id"],)).fetchone()
        ledger.require(latest["active"] == run_id, "dispatch ownership changed")
        state = "READY" if result["status"] == "CYCLE_REPORTED" else result["status"]
        if latest["status"] == "CANCEL_REQUESTED": state = "CANCELLED" if result["status"] != "UNKNOWN" else "UNKNOWN"
        connection.execute("UPDATE jobs SET status=?,due=?,active=?,last_result=? WHERE id=?", (state, time.time()+spec["interval_seconds"], run_id if state=="UNKNOWN" else None, json.dumps(result), spec["id"]))
        connection.commit()
    return result


def deliver_help(db, request_path, expected_sha, spool):
    ledger.require(ledger.file_hash(Path(request_path)) == expected_sha, "help request changed")
    request = ledger.read_json(request_path)
    ledger.exact(request, ("id", "goal", "question", "recipient", "acceptance", "wake_condition"))
    ledger.require(isinstance(request["id"], str) and re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", request["id"]), "invalid help id")
    for value in request.values(): ledger.string(value)
    spool = ledger.checked_path(spool)
    ledger.require(spool.is_dir(), "existing local inbox directory required")
    destination = spool/(request["id"]+".json")
    with connect(db) as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing=connection.execute("SELECT * FROM help WHERE id=?",(request["id"],)).fetchone()
        if existing:
            ledger.require(existing["request_sha"]==expected_sha and existing["destination"]==str(destination) and ledger.file_hash(destination)==existing["delivered_sha"], "help delivery conflicts or changed")
            connection.commit()
            return {"status":"ALREADY_FILE_DELIVERED", "recipient_acknowledged":False}
        # Persist the file first. A matching orphan file after a crash can be adopted.
        if destination.exists():
            ledger.require(ledger.read_json(destination)==request, "inbox id collision")
        else: ledger.atomic_write(destination,request)
        connection.execute("INSERT INTO help VALUES(?,?,?,?,?,NULL)",(request["id"],request["goal"],expected_sha,str(destination),ledger.file_hash(destination)))
        connection.commit()
    return {"status":"FILE_DELIVERED", "path":str(destination), "recipient_acknowledged":False}


def receive_help(db, response_path, expected_sha):
    ledger.require(ledger.file_hash(Path(response_path))==expected_sha,"response changed")
    response=ledger.read_json(response_path)
    ledger.exact(response,("id","goal","responder","answer"))
    for value in response.values(): ledger.string(value)
    with connect(db) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row=connection.execute("SELECT * FROM help WHERE id=?",(response["id"],)).fetchone()
        ledger.require(row and row["goal"]==response["goal"],"response does not match requested goal")
        ledger.require(ledger.file_hash(Path(row["destination"]))==row["delivered_sha"],"delivered request changed")
        record=json.dumps({"path":str(Path(response_path).absolute()),"sha256":expected_sha})
        ledger.require(row["response"] is None or row["response"]==record,"conflicting response; preserve and inspect both")
        connection.execute("UPDATE help SET response=? WHERE id=?",(record,response["id"]))
        connection.commit()
    return {"status":"RESPONSE_RECORDED", "revalidation":"REQUIRED", "authority":"none"}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=["register","reconfigure","complete","tick","serve","status","cancel","deliver-help","receive-help"])
    p.add_argument("--db",required=True)
    for name in ("spec","job","request","response","sha256","spool","review","previous-spec-sha256"): p.add_argument("--"+name)
    p.add_argument("--ticks",type=int,default=1);p.add_argument("--poll-seconds",type=float,default=1)
    a=p.parse_args()
    try:
        if a.action=="register": result=register(a.db,ledger.read_json(a.spec))
        elif a.action=="reconfigure": result=reconfigure(a.db,ledger.read_json(a.spec),a.previous_spec_sha256)
        elif a.action=="complete": result=complete(a.db,a.job,a.review,a.sha256)
        elif a.action=="tick": result=tick(a.db)
        elif a.action=="status": result=status(a.db)
        elif a.action=="cancel": result=cancel(a.db,a.job)
        elif a.action=="deliver-help": result=deliver_help(a.db,a.request,a.sha256,a.spool)
        elif a.action=="receive-help": result=receive_help(a.db,a.response,a.sha256)
        else:
            ledger.require(1<=a.ticks<=10000,"finite tick bound required");number(a.poll_seconds)
            ledger.require(a.poll_seconds<=60,"poll interval exceeds 60 seconds")
            for i in range(a.ticks):
                print(json.dumps(tick(a.db)),flush=True)
                if i+1<a.ticks: time.sleep(a.poll_seconds)
            return 0
        print(json.dumps(result,indent=2));return 0
    except (ledger.LedgerError,OSError,sqlite3.Error,ValueError,TypeError,RecursionError,subprocess.SubprocessError) as exc:
        print(json.dumps({"status":"BLOCKED","error":str(exc),"authority":"none"}));return 2


if __name__=="__main__": sys.exit(main())
