"""Executable local reference for atomic business effects and compensation.

This is an adapter contract, not an OS sandbox or identity provider. Product hosts
must protect this DB/API and authenticate the approval/policy administration path.
No network calls are made. Dispatch must be coupled to a provider adapter enforcing
its stated last controllable prevention point; external commit cannot be atomic
with SQLite. UNKNOWN retains exposure until independently reconciled.
"""
from __future__ import annotations

import secrets
from .common import digest, encoded, finite, loads, require
from .store import Store


class ActionGateway:
    def __init__(self, state):
        self.store = Store(state)
        with self.store.tx() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS policy(id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS limits(id TEXT PRIMARY KEY, ceiling INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS approvals(token TEXT PRIMARY KEY, action_sha TEXT NOT NULL, expires INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS effects(id TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')

    def configure(self, policy):
        require(set(policy) == {"id", "principal", "tenant", "environment", "operations", "targets", "epoch", "enabled", "limits"}, "invalid enforcement policy")
        require(type(policy["epoch"]) is int and policy["epoch"] >= 1, "invalid revocation epoch")
        require(type(policy["enabled"]) is bool and policy["limits"], "limits required")
        for ceiling in policy["limits"].values():
            require(type(ceiling) is int and ceiling >= 0, "integer business units required")
        with self.store.tx() as db:
            old = db.execute("SELECT value FROM policy WHERE id=?", (policy["id"],)).fetchone()
            if old:
                previous = loads(old[0])
                require(policy["epoch"] > previous["epoch"], "policy replay or downgrade")
                require(set(previous["limits"]) <= set(policy["limits"]), "cannot discard cumulative accounting scopes")
                for key in ("principal", "tenant", "environment"):
                    require(policy[key] == previous[key], "identity reassignment needs separate policy")
            for scope, ceiling in policy["limits"].items():
                current = db.execute("SELECT ceiling FROM limits WHERE id=?", (scope,)).fetchone()
                if current:
                    require(current[0] == ceiling, "shared ceiling changes require separate reviewed migration")
                else: db.execute("INSERT INTO limits VALUES(?,?)", (scope, ceiling))
            db.execute("INSERT OR REPLACE INTO policy VALUES(?,?)", (policy["id"], encoded(policy).decode()))

    def _policy(self, db, policy_id):
        row = db.execute("SELECT value FROM policy WHERE id=?", (policy_id,)).fetchone()
        require(row is not None, "unknown authority policy")
        return loads(row[0])

    def _check(self, policy, action, at):
        require(set(action) == {"id", "principal", "tenant", "environment", "operation", "target", "resource_revision", "parameters", "units", "epoch", "expires_at"}, "invalid action contract")
        require(policy["enabled"] and policy["epoch"] == action["epoch"], "authority stopped or stale generation")
        for key in ("principal", "tenant", "environment"):
            require(action[key] == policy[key], "action identity/scope mismatch")
        require(action["operation"] in policy["operations"] and action["target"] in policy["targets"], "operation or target denied")
        require(type(action["units"]) is int and action["units"] > 0, "positive integer business effect required")
        require(at < action["expires_at"], "expired action")
        require(isinstance(action["resource_revision"], str) and action["resource_revision"], "resource revision required")

    def approve(self, policy_id, action, at):
        with self.store.tx() as db:
            self._check(self._policy(db, policy_id), action, at)
            token = secrets.token_hex(24)
            db.execute("INSERT INTO approvals(token,action_sha,expires) VALUES(?,?,?)", (token, digest(action), action["expires_at"]))
            return token

    def reserve(self, policy_id, action, approval, at):
        with self.store.tx() as db:
            policy = self._policy(db, policy_id)
            self._check(policy, action, at)
            previous = db.execute("SELECT value FROM effects WHERE id=?", (action["id"],)).fetchone()
            if previous:
                previous = loads(previous[0])
                require(previous["action_sha"] == digest(action) and previous["policy_id"] == policy_id, "business idempotency substitution")
                return previous
            approval_row = db.execute("SELECT * FROM approvals WHERE token=?", (approval,)).fetchone()
            require(approval_row and not approval_row["used"] and approval_row["expires"] > at and approval_row["action_sha"] == digest(action), "approval mismatch/replay")
            effects = [loads(row[0]) for row in db.execute("SELECT value FROM effects")]
            for scope, ceiling in policy["limits"].items():
                occupied = sum(e["action"]["units"] for e in effects if scope in e["scopes"] and e["status"] not in {"FAILED_NO_EFFECT", "CANCELLED_NO_EFFECT"})
                require(occupied + action["units"] <= ceiling, "aggregate business exposure exhausted")
            value = {"action": action, "action_sha": digest(action), "policy_id": policy_id,
                     "scopes": list(policy["limits"]), "status": "AUTHORIZED", "receipts": [],
                     "compensation": "NOT_REQUIRED", "compensation_effect": None}
            db.execute("INSERT INTO effects VALUES(?,?)", (action["id"], encoded(value).decode()))
            db.execute("UPDATE approvals SET used=1 WHERE token=?", (approval,))
            return value

    def transition(self, action_id, target, at, receipt, resource_revision=None):
        allowed = {"AUTHORIZED": {"DISPATCHED", "CANCELLED_NO_EFFECT"},
                   "DISPATCHED": {"ACKNOWLEDGED", "COMMITTED", "UNKNOWN", "FAILED_NO_EFFECT"},
                   "ACKNOWLEDGED": {"COMMITTED", "UNKNOWN", "FAILED_NO_EFFECT"},
                   "UNKNOWN": {"COMMITTED", "FAILED_NO_EFFECT"}}
        with self.store.tx() as db:
            row = db.execute("SELECT value FROM effects WHERE id=?", (action_id,)).fetchone()
            require(row is not None, "unknown effect")
            value = loads(row[0])
            require(target in allowed.get(value["status"], set()) and receipt, "invalid effect transition or missing reconciliation receipt")
            if target == "DISPATCHED":
                self._check(self._policy(db, value["policy_id"]), value["action"], at)
                require(resource_revision == value["action"]["resource_revision"], "resource changed after approval")
            value["status"] = target
            value["receipts"].append({"status": target, "receipt": receipt, "at": at})
            db.execute("UPDATE effects SET value=? WHERE id=?", (encoded(value).decode(), action_id))
            return value

    def stop(self, policy_id):
        with self.store.tx() as db:
            policy = self._policy(db, policy_id)
            policy["epoch"] += 1; policy["enabled"] = False
            db.execute("UPDATE policy SET value=? WHERE id=?", (encoded(policy).decode(), policy_id))
            effects = [loads(r[0]) for r in db.execute("SELECT value FROM effects")]
            return {"dispatch_disabled": True, "epoch": policy["epoch"], "effects": [e for e in effects if e["policy_id"] == policy_id],
                    "external_cancellation_confirmed": False, "customer_recovery_complete": False}

    def compensate(self, action_id, state, compensation_effect, receipt):
        allowed = {"NOT_REQUIRED": {"REQUIRED"}, "REQUIRED": {"IN_PROGRESS", "IMPOSSIBLE"},
                   "IN_PROGRESS": {"PARTIAL", "FAILED", "COMPLETED_VERIFIED"},
                   "PARTIAL": {"IN_PROGRESS", "FAILED", "IMPOSSIBLE"}, "FAILED": {"IN_PROGRESS", "IMPOSSIBLE"}}
        with self.store.tx() as db:
            row = db.execute("SELECT value FROM effects WHERE id=?", (action_id,)).fetchone()
            require(row is not None and receipt, "effect and independent receipt required")
            value = loads(row[0])
            require(value["status"] == "COMMITTED", "reconcile original outcome before compensation")
            require(state in allowed.get(value["compensation"], set()), "invalid compensation transition")
            if state in {"IN_PROGRESS", "COMPLETED_VERIFIED"}:
                other = db.execute("SELECT value FROM effects WHERE id=?", (compensation_effect,)).fetchone()
                require(other and compensation_effect != action_id, "compensation requires separately authorized action")
                if state == "COMPLETED_VERIFIED": require(loads(other[0])["status"] == "COMMITTED", "compensation not committed")
            value["compensation"] = state; value["compensation_effect"] = compensation_effect
            value["receipts"].append({"compensation": state, "receipt": receipt})
            db.execute("UPDATE effects SET value=? WHERE id=?", (encoded(value).decode(), action_id))
            return value
