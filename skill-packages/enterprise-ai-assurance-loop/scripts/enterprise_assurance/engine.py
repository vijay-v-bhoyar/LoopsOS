"""Typed assurance reducer. Produces scoped decisions, never deploys or grants credentials."""
from __future__ import annotations

import secrets
import sqlite3
from .catalog import applicable, catalog, evaluate
from .common import AssuranceError, bundle_digest, digest, encoded, identifier, loads, now, require
from .contracts import validate
from .store import Store
from .trust import verify

ENGINES = {"codex-product-build-loop", "product-loop", "agentic-product-loop"}
PRELIMINARY = (0, 5, 8, 9, 11)
PROOF_ORDER = {"FIXTURE": 0, "ENTERPRISE": 1}
SECURITY_FLOOR = {"DISCOVERY-ROUTES", "AGENT-AUTHORITY", "AGENT-RESTART", "CRYPTO-REPLAY", "REGULATORY-COMPOSITION"}


class Engine:
    def __init__(self, state, trust, expected_trust_sha, clock=now):
        validate("trust", trust)
        require(digest(trust) == expected_trust_sha, "operator trust pin mismatch")
        self.store = Store(state)
        self.trust, self.clock = trust, clock

    def _current(self, run):
        at = self.clock()
        require(self.trust["issued_at"] <= at < self.trust["expires_at"], "trust checkpoint expired")
        require(self.trust["epoch"] >= run["trust_epoch"], "trust checkpoint rollback")
        require(run["verifier_sha"] == bundle_digest() and run["verifier_sha"] in self.trust["approved_verifiers"], "verifier changed or revoked; reviewed migration required")
        require(run["profile_sha"] in self.trust["approved_profiles"] and run["profile_sha"] not in self.trust["revoked_profiles"], "profile revoked")
        require(at >= run["last_time"], "clock rollback")
        require(at < run["deadline"], "cumulative run time budget exhausted")
        require(run["events"] < run["profile"]["max_events"], "event budget exhausted")

    def _load(self, db, run_id, active=False):
        self.store.verify_chain(db)
        run = self.store.run(db, run_id)
        row = db.execute("SELECT value FROM events WHERE run=? ORDER BY seq DESC LIMIT 1", (run_id,)).fetchone()
        require(row and loads(row[0]).get("state_sha") == digest(run), "run state/history mismatch")
        self._current(run)
        if active:
            require(run["state"] not in {"CANCELLED", "SUSPENDED"}, "run is stopped; signed fresh admission required")
        return run

    def _save(self, db, run, operation, detail):
        run["last_time"] = self.clock()
        run["trust_epoch"] = self.trust["epoch"]
        run["events"] += 1
        self.store.save(db, run)
        self.store.event(db, run["id"], {"operation": operation, "at": self.clock(), "detail": detail, "state_sha": digest(run)})

    def admit(self, run_id, subject, profile, parent_goal, criteria, delivery_engine, ancestors=(), _continuation=None):
        identifier(run_id); identifier(parent_goal)
        validate("subject", subject); validate("profile", profile)
        require(delivery_engine in ENGINES and not set(ancestors) & (ENGINES | {"enterprise-ai-assurance-loop"}), "recursive delivery/assurance nesting")
        require(criteria and len(set(criteria)) == len(criteria), "unique parent acceptance criteria required")
        for criterion in criteria: identifier(criterion)
        require(profile["limits"]["min_samples"] >= 1, "positive sample denominator required")
        require(SECURITY_FLOOR <= set(profile["nonwaivable_cases"]), "profile weakens mandatory security floor")
        if subject["environment"] != "ISOLATED_TEST" or profile["exposure"] != "ISOLATED_TEST":
            require(profile["required_proof"] == "ENTERPRISE", "fixture evidence cannot admit enterprise exposure")
        at = self.clock()
        run = {"id": run_id, "subject": subject, "subject_sha": digest(subject), "profile": profile,
               "profile_sha": digest(profile), "verifier_sha": bundle_digest(), "parent_goal": parent_goal,
               "criteria": criteria, "delivery_engine": delivery_engine, "ancestors": list(ancestors),
               "nonce": secrets.token_hex(24), "trust_epoch": self.trust["epoch"], "last_time": at,
               "deadline": at + profile["run_seconds"], "events": 0, "state": "PLANNED", "requested_product_mode": "UNKNOWN",
               "observed_product_mode": "UNKNOWN", "repairs": {}, "invalidated_owners": [], "incident": "NONE",
               "evidence_generation": 0, "retest_after": at, "continuation_of": None, "inherited_risks": {}, "inherited_failed_cases": []}
        if _continuation:
            previous, risk_refs, migration, failed_cases = _continuation
            run.update(continuation_of=previous["id"], deadline=min(run["deadline"], previous["deadline"]),
                       events=previous["events"] + 1, repairs=previous["repairs"],
                       evidence_generation=previous["evidence_generation"] + 1,
                       inherited_risks=risk_refs, inherited_failed_cases=failed_cases)
        self._current(run)
        with self.store.tx() as db:
            require(not db.execute("SELECT 1 FROM runs WHERE id=?", (run_id,)).fetchone(), "run already exists; budgets cannot reset")
            existing = [loads(row[0]) for row in db.execute("SELECT value FROM runs")]
            if _continuation:
                previous = _continuation[0]
                current = self.store.run(db, previous["id"])
                require(digest(current) == digest(previous), "continuation parent changed")
                require(not any(r["continuation_of"] == previous["id"] for r in existing), "parent already has a continuation")
                current["state"] = "CANCELLED"
                current["requested_product_mode"] = "DISABLED"
                self._save(db, current, "SUPERSEDED_BY_REVIEWED_CONTINUATION", {"child": run_id, "migration_sha": digest(_continuation[2])})
            else:
                require(not any(r["parent_goal"] == parent_goal for r in existing), "parent goal already exists; signed continuation required to preserve budgets")
            db.execute("INSERT INTO runs VALUES(?,?)", (run_id, encoded(run).decode()))
            if _continuation:
                self.store.artifact(db, run_id, "migration", _continuation[2])
            self._save(db, run, "ADMITTED", {"subject_sha": run["subject_sha"], "profile_sha": run["profile_sha"]})
        return self.plan(run_id)

    def continue_run(self, parent_run, run_id, subject, profile, envelope):
        """Reviewed immutable subject migration; preserves cumulative limits and risk debt."""
        validate("subject", subject); validate("profile", profile); validate("envelope", envelope)
        with self.store.tx() as db:
            self.store.verify_chain(db)
            previous = self.store.run(db, parent_run)
            payload = validate("operation", envelope["body"]["payload"])
            require(payload["action"] == "MIGRATE" and payload["expected_state_sha"] == digest(previous), "reviewed current parent migration required")
            require(set(payload["references"]) == {digest(subject), digest(profile)}, "migration must bind new subject and profile")
            require(envelope["body"]["run_id"] == run_id and envelope["body"]["nonce"] == previous["nonce"], "migration run/parent nonce mismatch")
            issuer = verify(envelope, self.trust, "operator", digest(subject), digest(profile), self.clock(), "operation")
            require(not issuer["test_only"] or subject["environment"] == "ISOLATED_TEST", "test-only migration cannot grant enterprise scope")
            risk_refs = {**previous["inherited_risks"], **{key: pair[0] for key, pair in self._latest_risks(db, parent_run).items()}}
            failed_cases = set(previous["inherited_failed_cases"])
            failed_cases.update(c["case_id"] for _, e in self.store.artifacts(db, parent_run, "evidence")
                                for c in e["body"]["payload"]["cases"] if c["outcome"] == "FAIL")
            require(self.clock() >= previous["last_time"], "migration clock rollback")
        # Admission transaction rechecks parent hash and one-child invariant.
        return self.admit(run_id, subject, profile, previous["parent_goal"], previous["criteria"], previous["delivery_engine"],
                          previous["ancestors"], _continuation=(previous, risk_refs, envelope, sorted(failed_cases)))

    def plan(self, run_id):
        with self.store.tx() as db:
            run = self._load(db, run_id)
            return {"run_id": run_id, "subject_sha": run["subject_sha"], "profile_sha": run["profile_sha"],
                    "nonce": run["nonce"], "delivery_engine": run["delivery_engine"], "authority": "none",
                    "evidence_generation": run["evidence_generation"],
                    "stages": [list(PRELIMINARY), [1, 2, 3, 4, 6, 7, 12], [5, 8, 10]],
                    "owners": [{"owner": owner["owner"], "skill": owner["skill"],
                                "applicable": applicable(owner["owner"], run["subject"]),
                                "case_manifest_sha": digest(owner["cases"]), "cases": owner["cases"]}
                               for owner in catalog()]}

    def _verify(self, envelope, run, role, purpose):
        validate("envelope", envelope)
        body = envelope.get("body", {})
        require(body.get("run_id") == run["id"] and body.get("nonce") == run["nonce"], "wrong run or nonce")
        issuer = verify(envelope, self.trust, role, run["subject_sha"], run["profile_sha"], self.clock(), purpose)
        if issuer["test_only"]:
            require(run["subject"]["environment"] == "ISOLATED_TEST" and run["profile"]["required_proof"] == "FIXTURE", "test-only signer cannot prove enterprise readiness")
        return issuer

    def _claim_invocation(self, db, envelope):
        invocation = envelope["body"]["invocation_id"]
        row = db.execute("SELECT sha FROM invocations WHERE id=?", (invocation,)).fetchone()
        if row:
            require(row[0] == digest(envelope), "invocation replay/substitution")
            return False  # Idempotent import does not mint another authorization.
        db.execute("INSERT INTO invocations VALUES(?,?)", (invocation, digest(envelope)))
        return True

    def _evidence(self, run, envelope, blobs=None):
        issuer = self._verify(envelope, run, "collector", "evidence")
        value = validate("evidence", envelope["body"]["payload"])
        owner = catalog()[value["owner"]]
        require(value["owner"] in issuer["owners"], "collector cannot attest this owner")
        require(value["verifier_sha"] == run["verifier_sha"], "evidence from different harness")
        require(value["case_manifest_sha"] == digest(owner["cases"]), "required test manifest changed")
        at = self.clock()
        require(value["generation"] == run["evidence_generation"], "evidence belongs to a prior repair generation")
        require(value["observed_at"] >= max(run["retest_after"], self.trust["evidence_not_before"]), "observations predate repair or trust checkpoint")
        require(value["observed_at"] <= envelope["body"]["issued_at"] and at - value["observed_at"] <= run["profile"]["max_evidence_age"], "stale or future observations")
        require(value["model_evidence_expires_at"] > at, "stale model evidence")
        require(PROOF_ORDER[value["proof"]] >= PROOF_ORDER[run["profile"]["required_proof"]], "insufficient proof level")
        require(not issuer["test_only"] or value["proof"] == "FIXTURE", "test signer cannot attest ENTERPRISE")
        applies = applicable(value["owner"], run["subject"])
        require((value["scope"] == "APPLICABLE") == applies, "false applicability/N/A")
        expected = {case["id"]: case for case in owner["cases"]} if applies else {}
        rows = {case["case_id"]: case for case in value["cases"]}
        require(len(rows) == len(value["cases"]) and set(rows) == set(expected), "missing, duplicate, or unexpected case")
        require(set(value["trial_ids"]) == set(value["all_dispatched_trials"]), "omitted trials")
        require(not applies or len(value["trial_ids"]) >= run["profile"]["limits"]["min_samples"], "insufficient sample denominator")
        manifest_hashes = set(value["raw_manifest"].values())
        for case_id, row in rows.items():
            require(row["raw_sha"] in manifest_hashes, "raw evidence missing from manifest")
            if row["outcome"] in {"PASS", "FAIL"}:
                failures = evaluate(expected[case_id], row["observations"], run["profile"]["limits"])
                require((not failures) == (row["outcome"] == "PASS"), "claimed result contradicts observations")
        if blobs is not None:
            import hashlib
            for sha in manifest_hashes:
                require(sha in blobs and hashlib.sha256(blobs[sha]).hexdigest() == sha, "missing or altered raw artifact")
        return value

    def ingest(self, run_id, envelope, blobs):
        with self.store.tx() as db:
            run = self._load(db, run_id, active=True)
            value = self._evidence(run, envelope, blobs)
            if not self._claim_invocation(db, envelope): return {"status": "ALREADY_INGESTED", "sha": digest(envelope)}
            # Raw bytes are retained in content-addressed artifacts without active rendering.
            import base64
            for sha in set(value["raw_manifest"].values()):
                self.store.artifact(db, run_id, "raw", {"content_sha": sha, "base64": base64.b64encode(blobs[sha]).decode()})
            sha = self.store.artifact(db, run_id, "evidence", envelope)
            run["invalidated_owners"] = [o for o in run["invalidated_owners"] if o != value["owner"]]
            run["state"] = "TESTING"
            self._save(db, run, "EVIDENCE", {"sha": sha, "owner": value["owner"]})
            return {"status": "INGESTED", "sha": sha, "authority": "none"}

    def record_risk(self, run_id, envelope):
        with self.store.tx() as db:
            run = self._load(db, run_id, active=True)
            issuer = self._verify(envelope, run, "collector", "risk")
            risk = validate("risk", envelope["body"]["payload"])
            require(risk["owner"] in issuer["owners"] and risk["subject_sha"] == run["subject_sha"], "risk owner/subject mismatch")
            case_ids = {c["id"] for o in catalog() for c in o["cases"]}
            require(set(risk["requirement_ids"]) <= case_ids, "unknown risk requirement")
            require(risk["accountable"] != risk["challenger"], "risk challenge conflict")
            if not self._claim_invocation(db, envelope): return {"status": "ALREADY_RECORDED"}
            sha = self.store.artifact(db, run_id, "risk", envelope)
            self._save(db, run, "RISK", {"id": risk["id"], "sha": sha})
            return {"status": "RECORDED", "sha": sha}

    def _latest_risks(self, db, run_id):
        return {e["body"]["payload"]["id"]: (sha, e) for sha, e in self.store.artifacts(db, run_id, "risk")}

    def manifest(self, db, run):
        # Includes all attempts, not just latest successes. Any addition invalidates challenge.
        return digest({"subject": run["subject_sha"], "profile": run["profile_sha"],
                       "evidence": [sha for sha, _ in self.store.artifacts(db, run["id"], "evidence")],
                       "risks": [sha for sha, _ in self.store.artifacts(db, run["id"], "risk")],
                       "waivers": [sha for sha, _ in self.store.artifacts(db, run["id"], "waiver")],
                       "repairs": run["repairs"], "invalidated": run["invalidated_owners"]})

    def challenge(self, run_id, envelope):
        with self.store.tx() as db:
            run = self._load(db, run_id, active=True)
            reviewer = self._verify(envelope, run, "challenger", "challenge")
            review = validate("review", envelope["body"]["payload"])
            require(review["manifest_sha"] == self.manifest(db, run), "challenge binds stale manifest")
            require(not review["conflicts"], "unresolved reviewer conflict")
            require(set(review["criterion_ids"]) == set(run["criteria"]), "parent criteria incomplete")
            prior_reviews = {sha: item for sha, item in self.store.artifacts(db, run_id, "challenge")}
            for veto_sha in review["resolves_vetoes"]:
                veto = prior_reviews.get(veto_sha)
                require(review["decision"] == "APPROVE" and veto and veto["body"]["payload"]["decision"] == "VETO", "invalid veto resolution")
                require(veto["body"]["principal"] == envelope["body"]["principal"], "only original independent challenger can resolve this veto")
            for _, item in self.store.artifacts(db, run_id, "evidence") + self.store.artifacts(db, run_id, "risk"):
                producer = self.trust["issuers"].get(item["issuer"], {})
                require(reviewer["principal"] != producer.get("principal") and reviewer["organization_unit"] != producer.get("organization_unit"), "organizational independence not established")
            if not self._claim_invocation(db, envelope): return {"status": "ALREADY_CHALLENGED"}
            sha = self.store.artifact(db, run_id, "challenge", envelope)
            run["state"] = "CHALLENGE"
            self._save(db, run, "CHALLENGE", {"sha": sha, "decision": review["decision"]})
            return {"status": "CHALLENGED", "sha": sha}

    def waiver(self, run_id, envelope):
        with self.store.tx() as db:
            run = self._load(db, run_id, active=True)
            self._verify(envelope, run, "risk-executive", "waiver")
            value = validate("waiver", envelope["body"]["payload"])
            risk_pair = self._latest_risks(db, run_id).get(value["risk_id"])
            require(risk_pair and risk_pair[0] == value["risk_sha"], "waiver risk changed")
            risk = risk_pair[1]["body"]["payload"]
            require(set(value["case_ids"]) == set(risk["requirement_ids"]), "waiver scope mismatch")
            require(not set(value["case_ids"]) & set(run["profile"]["nonwaivable_cases"]), "non-waivable requirement")
            require(envelope["body"]["expires_at"] - envelope["body"]["issued_at"] <= run["profile"]["waiver_days"] * 86400, "waiver exceeds ceiling")
            require(risk["exposure"] is not None and risk["exposure"] <= value["exposure_limit"] <= run["profile"]["limits"]["max_total_exposure"], "unknown or excessive exposure")
            refs = {sha: item for sha, item in self.store.artifacts(db, run_id, "evidence")}
            compensating_cases = set()
            for ref in value["compensating_evidence"]:
                require(ref in refs, "compensating control lacks evidence")
                proof = self._evidence(run, refs[ref])
                require(proof["cases"] and all(c["outcome"] == "PASS" for c in proof["cases"]), "compensating control not verified")
                compensating_cases.update(c["case_id"] for c in proof["cases"])
            for case_id in value["case_ids"]:
                approved_controls = run["profile"]["waiver_compensations"].get(case_id)
                require(approved_controls and set(approved_controls) <= compensating_cases, "profile-approved compensating controls missing")
            if not self._claim_invocation(db, envelope): return {"status": "ALREADY_RECORDED"}
            sha = self.store.artifact(db, run_id, "waiver", envelope)
            self._save(db, run, "WAIVER", {"sha": sha})
            return {"status": "RECORDED", "sha": sha}

    def decide(self, run_id):
        with self.store.tx() as db:
            run = self._load(db, run_id)
            blockers, escalations, coverage = [], [], []
            valid_until = [run["deadline"], self.trust["expires_at"]]
            latest = {e["body"]["payload"]["owner"]: (sha, e) for sha, e in self.store.artifacts(db, run_id, "evidence")}
            accepted_cases, valid_waivers = set(), []
            risks = self._latest_risks(db, run_id)
            for missing in set(run["inherited_risks"]) - set(risks):
                blockers.append(f"INHERITED_RISK_REASSESSMENT_REQUIRED:{missing}")
            for sha, waiver in self.store.artifacts(db, run_id, "waiver"):
                try:
                    self._verify(waiver, run, "risk-executive", "waiver")
                    w = waiver["body"]["payload"]
                    require(w["risk_id"] in risks and risks[w["risk_id"]][0] == w["risk_sha"], "risk acceptance stale")
                    require(not set(w["case_ids"]) & set(run["profile"]["nonwaivable_cases"]), "waiver now prohibited")
                    compensating_cases = set()
                    for ref in w["compensating_evidence"]:
                        item = next((e for s, e in self.store.artifacts(db, run_id, "evidence") if s == ref), None)
                        require(item is not None, "compensating evidence missing")
                        proof = self._evidence(run, item)
                        require(proof["cases"] and all(c["outcome"] == "PASS" for c in proof["cases"]), "compensating proof no longer valid")
                        compensating_cases.update(c["case_id"] for c in proof["cases"])
                        valid_until.extend([item["body"]["expires_at"], proof["model_evidence_expires_at"], proof["observed_at"] + run["profile"]["max_evidence_age"]])
                    for case_id in w["case_ids"]:
                        approved_controls = run["profile"]["waiver_compensations"].get(case_id)
                        require(approved_controls and set(approved_controls) <= compensating_cases, "compensating controls no longer meet profile")
                    accepted_cases.update(w["case_ids"]); valid_waivers.append(w)
                    valid_until.extend([waiver["body"]["expires_at"], self.trust["issuers"][waiver["issuer"]]["valid_until"]])
                except AssuranceError as exc:
                    escalations.append(f"WAIVER_INVALID:{sha}:{exc}")
            total_exposure = 0
            for risk_id, (_, envelope) in risks.items():
                risk = envelope["body"]["payload"]
                valid_until.extend([risk["review_at"], envelope["body"]["expires_at"],
                                    self.trust["issuers"].get(envelope["issuer"], {}).get("valid_until", 0)])
                try: self._verify(envelope, run, "collector", "risk")
                except AssuranceError: blockers.append(f"RISK_UNTRUSTED:{risk_id}")
                if risk["exposure"] is None:
                    blockers.append(f"UNBOUNDED_EXPOSURE:{risk_id}")
                elif risk["treatment"] != "CLOSED": total_exposure += risk["exposure"]
                if risk["review_at"] <= self.clock(): blockers.append(f"RISK_REVIEW_OVERDUE:{risk_id}")
                if risk["gate_effect"] == "NONE_WITH_CURRENT_EVIDENCE":
                    if risk["evidence"] != "VERIFIED_CURRENT" or risk["treatment"] not in {"CLOSED", "MITIGATED_VERIFIED"} or not risk["evidence_refs"]:
                        blockers.append(f"UNVERIFIED_CLOSURE:{risk_id}")
                    for ref in risk["evidence_refs"]:
                        pair = next((e for s, e in self.store.artifacts(db, run_id, "evidence") if s == ref), None)
                        try:
                            require(pair is not None, "closure evidence missing")
                            proof = self._evidence(run, pair)
                            require(set(risk["requirement_ids"]) <= {c["case_id"] for c in proof["cases"] if c["outcome"] == "PASS"}, "closure retest missing")
                        except AssuranceError: blockers.append(f"STALE_CLOSURE:{risk_id}")
                elif not any(w["risk_id"] == risk_id for w in valid_waivers) or risk["gate_effect"] != "PERMIT_WITH_VALID_ACCEPTANCE":
                    blockers.append(f"OPEN_RISK:{risk_id}")
            if total_exposure > run["profile"]["limits"]["max_total_exposure"]: blockers.append("AGGREGATE_EXPOSURE_EXCEEDED")
            operational = set()
            for owner in catalog():
                owner_id = owner["owner"]
                applies = applicable(owner_id, run["subject"])
                row = {"owner": owner_id, "skill": owner["skill"], "applicable": applies, "status": "MISSING", "cases": []}
                try:
                    require(owner_id in latest, "owner evidence missing")
                    require(owner_id not in run["invalidated_owners"], "repair invalidated evidence")
                    sha, envelope = latest[owner_id]
                    evidence = self._evidence(run, envelope)
                    require(set(evidence["risks"]) <= set(risks), "owner omitted declared risk records")
                    row.update(status="NOT_APPLICABLE" if not applies else "PASS", cases=evidence["cases"], evidence_sha=sha)
                    operational.update(evidence["operational_claims"])
                    valid_until.extend([envelope["body"]["expires_at"], evidence["model_evidence_expires_at"],
                                        evidence["observed_at"] + run["profile"]["max_evidence_age"],
                                        self.trust["issuers"][envelope["issuer"]]["valid_until"]])
                    for case in evidence["cases"]:
                        if case["outcome"] != "PASS":
                            row["status"] = case["outcome"]
                            if case["case_id"] not in accepted_cases: blockers.append(f"CASE_{case['outcome']}:{case['case_id']}")
                except AssuranceError as exc:
                    row["status"] = "MISSING_OR_INVALID"; row["reason"] = str(exc)
                    blockers.append(f"OWNER_EVIDENCE:{owner_id}:{exc}")
                coverage.append(row)
            # A passing retry cannot silently erase an earlier failure.
            failed_before = {c["case_id"] for _, e in self.store.artifacts(db, run_id, "evidence")
                             for c in e["body"]["payload"]["cases"] if c["outcome"] == "FAIL"}
            failed_before.update(run["inherited_failed_cases"])
            closed_cases = {case for _, e in risks.values() for case in e["body"]["payload"]["requirement_ids"]
                            if e["body"]["payload"]["gate_effect"] == "NONE_WITH_CURRENT_EVIDENCE"
                            and e["body"]["payload"]["id"] in run["repairs"]}
            for case_id in failed_before - closed_cases - accepted_cases:
                blockers.append(f"UNRESOLVED_PRIOR_FAILURE:{case_id}")
            if run["profile"]["required_proof"] == "ENTERPRISE":
                for claim in set(run["profile"]["enterprise_prerequisites"]) - operational:
                    blockers.append(f"ENTERPRISE_EVIDENCE_REQUIRED:{claim}")
            manifest = self.manifest(db, run)
            approved = False
            vetoes, resolved_vetoes = set(), set()
            for review_sha, review in self.store.artifacts(db, run_id, "challenge"):
                try:
                    self._verify(review, run, "challenger", "challenge")
                    r = review["body"]["payload"]
                    reviewer = self.trust["issuers"][review["issuer"]]
                    for _, item in self.store.artifacts(db, run_id, "evidence") + self.store.artifacts(db, run_id, "risk"):
                        producer = self.trust["issuers"].get(item["issuer"], {})
                        require(reviewer["principal"] != producer.get("principal") and reviewer["organization_unit"] != producer.get("organization_unit"), "review independence changed")
                    if r["decision"] == "VETO": vetoes.add(review_sha)
                    if r["manifest_sha"] == manifest and r["decision"] == "APPROVE":
                        approved = True
                        resolved_vetoes.update(r["resolves_vetoes"])
                        valid_until.extend([review["body"]["expires_at"], self.trust["issuers"][review["issuer"]]["valid_until"]])
                except AssuranceError: escalations.append("CHALLENGE_INVALID")
            if vetoes - resolved_vetoes: blockers.append("INDEPENDENT_VETO")
            if not approved: escalations.append("CURRENT_INDEPENDENT_CHALLENGE_REQUIRED")
            if run["state"] in {"CANCELLED", "SUSPENDED"}: blockers.append("RUN_STOPPED")
            decision = "NO_GO" if blockers else "ESCALATE" if escalations else "GO"
            run["requested_product_mode"] = run["profile"]["exposure"] if decision == "GO" else "DISABLED"
            result = {"schema": "enterprise-decision/v1", "run_id": run_id, "subject_sha": run["subject_sha"], "profile_sha": run["profile_sha"],
                      "manifest_sha": manifest, "decision": decision, "reasons": sorted(set(blockers + escalations)),
                      "requested_product_mode": run["requested_product_mode"], "observed_product_mode": run["observed_product_mode"],
                      "permission_manifest": {"workflow": run["subject"]["workflow"], "tenant": run["subject"]["tenant"], "environment": run["subject"]["environment"],
                          "principals": run["profile"]["principals"] if decision == "GO" else [],
                          "operations": run["profile"]["operations"] if decision == "GO" else [],
                          "data_classes": run["subject"]["data_classes"], "limits": run["profile"]["limits"], "expires_at": min(valid_until)},
                      "coverage": coverage, "risks": [e["body"]["payload"] for _, e in risks.values()], "valid_acceptances": valid_waivers,
                      "parent_goal": run["parent_goal"], "parent_goal_accepted": False,
                      "assurance_criteria_satisfied": decision == "GO", "criterion_ids": run["criteria"],
                      "delivery_engine": run["delivery_engine"], "authority": "none", "proof": run["profile"]["required_proof"],
                      "deployment_authorized": False, "issued_at": self.clock()}
            sha = self.store.artifact(db, run_id, "decision", result)
            self._save(db, run, "DECISION", {"sha": sha, "decision": decision})
            return result

    def operate(self, run_id, envelope):
        with self.store.tx() as db:
            run = self._load(db, run_id)
            self._verify(envelope, run, "operator", "operation")
            action = validate("operation", envelope["body"]["payload"])
            require(action["expected_state_sha"] == digest(run), "stale operation state")
            require(self._claim_invocation(db, envelope), "operation replay")
            if action["action"] == "RESUME":
                require(run["state"] != "CANCELLED", "cancelled run needs new reviewed continuation")
                run["state"] = "TESTING"
            elif action["action"] in {"CANCEL", "SUSPEND"}:
                run["state"] = "CANCELLED" if action["action"] == "CANCEL" else "SUSPENDED"
                run["requested_product_mode"] = "DISABLED"
            elif action["action"] == "MODE_OBSERVED":
                require(action["references"], "observed mode requires enforcement receipt")
                available = {sha for sha, _ in self.store.artifacts(db, run_id, "evidence")}
                require(set(action["references"]) <= available, "enforcement receipt is not retained evidence")
                run["observed_product_mode"] = action["observed_mode"]
            elif action["action"] == "REPAIR":
                require(run["state"] not in {"CANCELLED", "SUSPENDED"}, "repair run stopped")
                risks = self._latest_risks(db, run_id)
                require(action["risk_id"] in risks, "repair needs registered risk")
                attempts = run["repairs"].setdefault(action["risk_id"], [])
                require(len(attempts) < run["profile"]["max_repairs"], "repair attempts exhausted")
                require(action["patch_sha"] not in [item["patch_sha"] for item in attempts], "repeated repair without progress")
                attempts.append({"patch_sha": action["patch_sha"], "references": action["references"], "at": self.clock()})
                run["invalidated_owners"] = list(range(13))
                run["evidence_generation"] += 1
                run["retest_after"] = self.clock()
            else:
                raise AssuranceError("migration needs offline reviewed backup/restore and a new run; no in-place semantic rewrite")
            sha = self.store.artifact(db, run_id, "operation", envelope)
            self._save(db, run, action["action"], {"sha": sha})
            return {"state": run["state"], "requested_product_mode": run["requested_product_mode"], "observed_product_mode": run["observed_product_mode"], "authority": "none"}

    def inspect(self, run_id):
        # Inspection stays available after expiry/revocation so incidents remain visible.
        with self.store.tx() as db:
            head = self.store.verify_chain(db)
            run = self.store.run(db, run_id)
            return {"run": run, "state_sha": digest(run), "manifest_sha": self.manifest(db, run), "history_head": head,
                    "help": [loads(r[0]) for r in db.execute("SELECT value FROM help WHERE run=?", (run_id,))], "authority": "none"}
