"""Finite scheduling, authenticated help receipts and portable evidence export."""
from __future__ import annotations

import html
import secrets
from .common import AssuranceError, digest, encoded, loads, require, write
from .contracts import validate


def request_help(engine, run_id, request):
    validate("help", request)
    require(request["status"] == "DRAFT" and request["attempts"] == 0, "new help is a draft, never delivered")
    with engine.store.tx() as db:
        run = engine._load(db, run_id, active=True)
        require(request["deadline"] > engine.clock(), "help deadline passed")
        require(request["risk_id"] in engine._latest_risks(db, run_id), "help must link an open risk")
        require(not db.execute("SELECT 1 FROM help WHERE id=?", (request["id"],)).fetchone(), "help identity cannot reset")
        db.execute("INSERT INTO help VALUES(?,?,?)", (request["id"], run_id, encoded(request).decode()))
        run["state"] = "WAITING_FOR_HELP"
        engine._save(db, run, "HELP_DRAFT", {"request_sha": digest(request)})
    return {"status": "DRAFT", "delivered": False, "request": request}


def help_receipt(engine, run_id, envelope):
    with engine.store.tx() as db:
        run = engine._load(db, run_id, active=True)
        engine._verify(envelope, run, "help-adapter", "help")
        value = validate("help", envelope["body"]["payload"])
        row = db.execute("SELECT value FROM help WHERE id=? AND run=?", (value["id"], run_id)).fetchone()
        require(row is not None, "unknown help request")
        old = loads(row[0])
        for key in set(old) - {"status", "attempts", "delivery_reference"}:
            require(value[key] == old[key], "help receipt changed immutable request")
        states = {"DRAFT": {"DELIVERED", "DEAD_LETTER"}, "DELIVERED": {"ACKNOWLEDGED", "DEAD_LETTER"},
                  "ACKNOWLEDGED": {"RESOLVED", "DEAD_LETTER"}}
        require(value["status"] in states.get(old["status"], set()), "invalid help transition")
        require(old["attempts"] <= value["attempts"] <= 3 and value["delivery_reference"] != "not-delivered", "delivery attempts/receipt invalid")
        require(engine._claim_invocation(db, envelope), "help receipt replay")
        db.execute("UPDATE help SET value=? WHERE id=?", (encoded(value).decode(), value["id"]))
        engine.store.artifact(db, run_id, "help-receipt", envelope)
        # RESOLVED is a response, not verified repair or automatic parent acceptance.
        engine._save(db, run, "HELP_RECEIPT", {"id": value["id"], "status": value["status"]})
        return {"status": value["status"], "retest_required": True, "authority": "none"}


def register_schedule(engine, run_id, spec):
    validate("schedule", spec)
    with engine.store.tx() as db:
        run = engine._load(db, run_id, active=True)
        require(not db.execute("SELECT 1 FROM schedules WHERE run=? OR id=?", (run_id, spec["id"])).fetchone(), "schedule budget cannot reset")
        value = {"spec": spec, "dispatches": 0, "failures": 0, "status": "READY", "lease": None, "lease_until": 0, "last_decision": None}
        db.execute("INSERT INTO schedules VALUES(?,?,?)", (spec["id"], run_id, encoded(value).decode()))
        engine._save(db, run, "SCHEDULE", {"id": spec["id"]})
    return {"status": "REGISTERED", "daemon_installed": False}


def tick(engine):
    """One finite worker invocation; host scheduling is an external prerequisite."""
    dispatched = []
    with engine.store.tx() as db:
        for row in db.execute("SELECT * FROM help").fetchall():
            request = loads(row["value"])
            if request["deadline"] <= engine.clock() and request["status"] not in {"RESOLVED", "DEAD_LETTER"}:
                request["status"] = "DEAD_LETTER"
                db.execute("UPDATE help SET value=? WHERE id=?", (encoded(request).decode(), row["id"]))
                run = engine.store.run(db, row["run"])
                engine._save(db, run, "HELP_OVERDUE", {"id": row["id"], "reason": "No verified resolution before deadline; no authority granted."})
        for row in db.execute("SELECT * FROM schedules ORDER BY id").fetchall():
            value = loads(row["value"]); spec = value["spec"]
            if value["status"] in {"CANCELLED", "DEAD_LETTER", "EXHAUSTED"}: continue
            if value["lease_until"] > engine.clock() or spec["due"] > engine.clock(): continue
            try:
                run = engine._load(db, row["run"], active=True)
            except AssuranceError as exc:
                value["status"] = "DEAD_LETTER"; value["last_error"] = str(exc)
                db.execute("UPDATE schedules SET value=? WHERE id=?", (encoded(value).decode(), row["id"]))
                continue
            if value["dispatches"] >= spec["max_dispatches"]:
                value["status"] = "EXHAUSTED"
            else:
                value["dispatches"] += 1; value["status"] = "LEASED"
                value["lease"] = secrets.token_hex(16); value["lease_until"] = engine.clock() + spec["lease_seconds"]
                dispatched.append((row["id"], row["run"], value["lease"]))
            db.execute("UPDATE schedules SET value=? WHERE id=?", (encoded(value).decode(), row["id"]))
            engine._save(db, run, "SCHEDULE_CLAIM", {"schedule": row["id"], "dispatches": value["dispatches"]})
    results = []
    for job_id, run_id, lease in dispatched:
        try:
            result = engine.decide(run_id)
            failure = None
        except (AssuranceError, OSError) as exc:
            result, failure = None, str(exc)
        with engine.store.tx() as db:
            row = db.execute("SELECT value FROM schedules WHERE id=?", (job_id,)).fetchone()
            value = loads(row[0])
            require(value["lease"] == lease, "stale scheduler worker")
            value["failures"] += int(failure is not None)
            value["status"] = "DEAD_LETTER" if value["failures"] >= value["spec"]["max_failures"] else "READY"
            value["lease_until"] = 0; value["lease"] = None
            value["spec"]["due"] = engine.clock() + value["spec"]["interval_seconds"]
            value["last_decision"] = digest(result) if result else None
            value["last_error"] = failure
            db.execute("UPDATE schedules SET value=? WHERE id=?", (encoded(value).decode(), job_id))
            results.append({"schedule": job_id, "status": value["status"], "decision": result["decision"] if result else None, "error": failure})
    return {"dispatches": results, "authority": "none"}


def export_pack(engine, run_id, destination):
    """JSON preserves exact data; HTML is escaped and contains no active evidence links."""
    from pathlib import Path
    with engine.store.tx() as db:
        head = engine.store.verify_chain(db)
        run = engine.store.run(db, run_id)
        artifacts = [{"sha": r["sha"], "kind": r["kind"], "value": loads(r["value"])}
                     for r in db.execute("SELECT sha,kind,value FROM artifacts WHERE run=? ORDER BY rowid", (run_id,))]
        history = [dict(r) for r in db.execute("SELECT * FROM events WHERE run=? ORDER BY seq", (run_id,))]
        pack = {"schema": "enterprise-export/v1", "run": run, "artifacts": artifacts, "history": history,
                "help": [loads(row[0]) for row in db.execute("SELECT value FROM help WHERE run=?", (run_id,))],
                "schedules": [loads(row[0]) for row in db.execute("SELECT value FROM schedules WHERE run=?", (run_id,))],
                "history_head": head, "authority": "none", "sensitivity": "RESTRICTED_RAW_EVIDENCE",
                "limitations": ["Local hashes do not establish WORM retention or authentic collection.", "Export may include confidential evidence; distribute only within its authorized scope."]}
    destination = Path(destination)
    require(not destination.exists(), "export destination already exists")
    write(destination / "evidence-pack.json", pack)
    decisions = [a["value"] for a in artifacts if a["kind"] == "decision"]
    latest = decisions[-1] if decisions else {"decision": "NOT_DECIDED", "reasons": ["No decision has been made."]}
    report = "<!doctype html><html><head><meta charset='utf-8'><meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'none'\"><title>Enterprise assurance evidence</title></head><body><h1>Enterprise assurance</h1>"
    report += "<p>Decision at collection time; current authority requires revalidation. No deployment authorization.</p><pre>"
    report += html.escape(encoded(latest).decode()) + "</pre><h2>Complete attempt and risk manifest</h2><pre>"
    report += html.escape(encoded([{k: a[k] for k in ("sha", "kind")} for a in artifacts]).decode()) + "</pre><h2>Help and scheduling</h2><pre>"
    report += html.escape(encoded({"help": pack["help"], "schedules": pack["schedules"]}).decode()) + "</pre></body></html>"
    (destination / "report.html").write_text(report, encoding="utf-8")
    write(destination / "inventory.json", {"pack_sha": digest(pack), "artifact_count": len(artifacts), "authority": "none"})
    return {"export": str(destination), "pack_sha": digest(pack), "authority": "none"}
