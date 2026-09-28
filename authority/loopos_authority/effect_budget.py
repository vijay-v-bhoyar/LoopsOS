"""Durable cumulative request-exposure accounting. Never estimates unobserved business loss."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Any


class EffectBudgetDenied(RuntimeError):
    pass


SCHEMA = (
    "CREATE TABLE IF NOT EXISTS effect_budget_policy (singleton INTEGER PRIMARY KEY CHECK (singleton = 1), epoch BIGINT NOT NULL, policy_hash TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS effect_budget_accounts (tenant_id TEXT NOT NULL, unit TEXT NOT NULL, used BIGINT NOT NULL CHECK (used >= 0), PRIMARY KEY (tenant_id, unit))",
    "CREATE TABLE IF NOT EXISTS effect_budget_reservations (tenant_id TEXT NOT NULL, invocation_id TEXT NOT NULL, run_id TEXT NOT NULL, request_hash TEXT NOT NULL, policy_hash TEXT NOT NULL, charges_json TEXT NOT NULL, status TEXT NOT NULL, fence BIGINT NOT NULL, lease_expires_at DOUBLE PRECISION NOT NULL, result_json TEXT, PRIMARY KEY (tenant_id, invocation_id))",
    "CREATE TABLE IF NOT EXISTS effect_budget_events (event_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, invocation_id TEXT NOT NULL, kind TEXT NOT NULL, observed_at DOUBLE PRECISION NOT NULL, detail_json TEXT NOT NULL)",
)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def positive(value: Any) -> bool:
    return type(value) is int and 0 < value <= 10**15


def validate_policy(policy: Any) -> dict[str, Any]:
    if policy is None:
        return {}
    if not isinstance(policy, dict) or policy.get("version") != 1 or policy.get("scope") != "cumulative" or not isinstance(policy.get("tenants"), dict):
        raise EffectBudgetDenied("External-effect policy must declare version 1, cumulative scope and tenants.")
    if not positive(policy.get("policy_epoch", 1)):
        raise EffectBudgetDenied("Policy epoch must be a positive monotonic integer.")
    for tenant, item in policy["tenants"].items():
        if not isinstance(tenant, str) or not tenant or not isinstance(item, dict):
            raise EffectBudgetDenied("Invalid effect-budget tenant.")
        ceilings, routes = item.get("ceilings"), item.get("routes")
        if not isinstance(ceilings, dict) or not ceilings or any(not isinstance(unit, str) or not unit or not positive(cap) for unit, cap in ceilings.items()):
            raise EffectBudgetDenied("Every budget ceiling needs an explicit unit and positive integer quantity.")
        if not isinstance(routes, list) or not routes:
            raise EffectBudgetDenied("Every effect-budget tenant needs reviewed routes.")
        seen = set()
        for route in routes:
            if not isinstance(route, dict) or not isinstance(route.get("endpoint"), str) or route.get("method") not in {"POST", "PUT", "PATCH", "DELETE"} or not route.get("evidence_ref"):
                raise EffectBudgetDenied("Each effect route needs exact endpoint, method and reviewed metric evidence.")
            key = (route["endpoint"], route["method"])
            if key in seen:
                raise EffectBudgetDenied("Ambiguous effect route.")
            seen.add(key)
            charges = route.get("charges")
            if not isinstance(charges, list) or not charges:
                raise EffectBudgetDenied("External effects cannot have an empty exposure charge.")
            units = set()
            for charge in charges:
                if not isinstance(charge, dict) or charge.get("unit") not in ceilings or charge["unit"] in units:
                    raise EffectBudgetDenied("Invalid or duplicate effect unit.")
                units.add(charge["unit"])
                if "fixed" in charge:
                    if not positive(charge["fixed"]) or "amount_path" in charge:
                        raise EffectBudgetDenied("Fixed exposure must be an explicit positive integer.")
                elif not isinstance(charge.get("amount_path"), str) or not charge["amount_path"] or not positive(charge.get("max_amount")):
                    raise EffectBudgetDenied("Variable exposure requires a bounded integer amount path.")
                if charge["unit"].endswith("_minor"):
                    currency = charge.get("currency")
                    if not isinstance(currency, str) or len(currency) != 3 or not currency.isupper() or charge["unit"] != currency + "_minor" or not charge.get("currency_path") or "fixed" in charge:
                        raise EffectBudgetDenied("Money requires explicit ISO currency and integer minor-unit request paths.")
            if not any(charge.get("unit") == "dispatch_count" and charge.get("fixed") == 1 for charge in charges):
                raise EffectBudgetDenied("Every external route must also charge one dispatch_count unit.")
    return policy


def at_path(body: Any, path: str) -> Any:
    for part in path.split("."):
        if not isinstance(body, dict) or part not in body:
            raise EffectBudgetDenied("Required request exposure field is missing.")
        body = body[part]
    return body


@dataclass(frozen=True)
class Reservation:
    tenant_id: str
    invocation_id: str
    fence: int
    replay: dict[str, Any] | None = None


class EffectBudget:
    def __init__(self, store, policy: Any, *, clock=time.time, lease_seconds: float = 60):
        self.store, self.policy, self.clock, self.lease_seconds = store, json.loads(canonical(validate_policy(policy))), clock, lease_seconds
        self.policy_hash = hashlib.sha256(canonical(self.policy).encode()).hexdigest()
        # This uses the same durable authority database, never a process-local counter.
        with store.transaction() as cursor:
            if isinstance(store.connection, sqlite3.Connection):
                for statement in SCHEMA:
                    cursor.execute(statement)
                for verb in ("UPDATE", "DELETE"):
                    cursor.execute(f"CREATE TRIGGER IF NOT EXISTS effect_budget_events_no_{verb.lower()} BEFORE {verb} ON effect_budget_events BEGIN SELECT RAISE(ABORT, 'Effect budget events are append-only'); END")
            else:
                # Production schema/RLS comes only from the reviewed migration, never ad hoc DDL.
                for table in ("effect_budget_policy", "effect_budget_accounts", "effect_budget_reservations", "effect_budget_events"):
                    cursor.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
            if self.policy:
                epoch = self.policy.get("policy_epoch", 1)
                cursor.execute("INSERT INTO effect_budget_policy VALUES (1, ?, ?) ON CONFLICT (singleton) DO NOTHING", (epoch, self.policy_hash))
                cursor.execute("UPDATE effect_budget_policy SET epoch = epoch WHERE singleton = 1")
                active = cursor.execute("SELECT * FROM effect_budget_policy WHERE singleton = 1").fetchone()
                if epoch < active["epoch"] or (epoch == active["epoch"] and active["policy_hash"] != self.policy_hash):
                    raise EffectBudgetDenied("Policy changed without a newer reviewed epoch, or this worker has stale policy.")
                if epoch > active["epoch"]:
                    cursor.execute("UPDATE effect_budget_policy SET epoch = ?, policy_hash = ? WHERE singleton = 1", (epoch, self.policy_hash))
                    self._event(cursor, "__policy__", "__policy__", "policy_epoch_advanced", {"epoch": epoch, "policy_hash": self.policy_hash})

    def _active_policy(self, cursor) -> None:
        # Lock the active epoch before account/reservation locks to fence concurrent policy replacement.
        cursor.execute("UPDATE effect_budget_policy SET epoch = epoch WHERE singleton = 1")
        active = cursor.execute("SELECT * FROM effect_budget_policy WHERE singleton = 1").fetchone()
        if not active or active["policy_hash"] != self.policy_hash:
            raise EffectBudgetDenied("External-effect policy was revoked or changed; stale worker dispatch denied.")

    def ready(self) -> bool:
        if not self.policy.get("tenants"):
            return False
        try:
            with self.store.transaction() as cursor:
                self._active_policy(cursor)
                cursor.execute("SELECT COUNT(*) AS count FROM effect_budget_accounts").fetchone()
                cursor.execute("SELECT COUNT(*) AS count FROM effect_budget_reservations").fetchone()
            return True
        except Exception:
            return False

    def _event(self, cursor, tenant: str, invocation: str, kind: str, detail: dict[str, Any]) -> None:
        cursor.execute("INSERT INTO effect_budget_events VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), tenant, invocation, kind, self.clock(), canonical(detail)))

    def reserve(self, tenant: str, run_id: str, invocation: str, request: dict[str, Any]) -> Reservation:
        tenant_policy = self.policy.get("tenants", {}).get(tenant)
        if not tenant_policy:
            raise EffectBudgetDenied("No configured aggregate external-effect ceiling for this tenant.")
        arguments = request.get("arguments", {})
        matches = [route for route in tenant_policy["routes"] if route["endpoint"] == arguments.get("endpoint") and route["method"] == arguments.get("method")]
        if len(matches) != 1:
            raise EffectBudgetDenied("External effect has no reviewed exposure mapping.")
        charges: dict[str, int] = {}
        for charge in matches[0]["charges"]:
            amount = charge.get("fixed") if "fixed" in charge else at_path(arguments.get("body", {}), charge["amount_path"])
            if type(amount) is not int or amount < 0 or amount > charge.get("max_amount", amount):
                raise EffectBudgetDenied("Request exposure is not a bounded integer quantity.")
            if "currency" in charge and at_path(arguments.get("body", {}), charge["currency_path"]) != charge["currency"]:
                raise EffectBudgetDenied("Request currency differs from the configured budget unit.")
            charges[charge["unit"]] = amount
        request_hash = hashlib.sha256(canonical(request).encode()).hexdigest()
        policy_hash = self.policy_hash
        with self.store.transaction() as cursor:
            self._active_policy(cursor)
            # Serialize all contenders per tenant/unit in a deterministic order on SQLite and Postgres.
            for unit in sorted(charges):
                cursor.execute("INSERT INTO effect_budget_accounts VALUES (?, ?, 0) ON CONFLICT (tenant_id, unit) DO NOTHING", (tenant, unit))
                cursor.execute("UPDATE effect_budget_accounts SET used = used WHERE tenant_id = ? AND unit = ?", (tenant, unit))
            row = cursor.execute("SELECT * FROM effect_budget_reservations WHERE tenant_id = ? AND invocation_id = ?", (tenant, invocation)).fetchone()
            if row:
                if row["request_hash"] != request_hash or row["charges_json"] != canonical(charges):
                    raise EffectBudgetDenied("Reservation identity cannot be reused for changed exposure.")
                if row["status"] == "consumed" and row["result_json"]:
                    return Reservation(tenant, invocation, int(row["fence"]), json.loads(row["result_json"]))
                if row["policy_hash"] != self.policy_hash:
                    raise EffectBudgetDenied("Unsent reservation was created under a different policy; review and replan required.")
                if row["status"] != "reserved" or row["lease_expires_at"] > self.clock():
                    raise EffectBudgetDenied("External outcome is unknown, already claimed, cancelled, or needs reconciliation; dispatch denied.")
                fence = int(row["fence"]) + 1
                cursor.execute("UPDATE effect_budget_reservations SET fence = ?, lease_expires_at = ? WHERE tenant_id = ? AND invocation_id = ?", (fence, self.clock()+self.lease_seconds, tenant, invocation))
                self._event(cursor, tenant, invocation, "reclaimed_before_dispatch", {"fence": fence})
                return Reservation(tenant, invocation, fence)
            for unit, amount in charges.items():
                row = cursor.execute("SELECT used FROM effect_budget_accounts WHERE tenant_id = ? AND unit = ?", (tenant, unit)).fetchone()
                if row["used"] + amount > tenant_policy["ceilings"][unit]:
                    raise EffectBudgetDenied("Aggregate external-effect budget exhausted: " + unit)
            for unit, amount in charges.items():
                cursor.execute("UPDATE effect_budget_accounts SET used = used + ? WHERE tenant_id = ? AND unit = ?", (amount, tenant, unit))
            cursor.execute("INSERT INTO effect_budget_reservations VALUES (?, ?, ?, ?, ?, ?, 'reserved', 1, ?, NULL)",
                (tenant, invocation, run_id, request_hash, policy_hash, canonical(charges), self.clock()+self.lease_seconds))
            self._event(cursor, tenant, invocation, "reserved", {"charges": charges, "policy_hash": policy_hash, "fence": 1})
        return Reservation(tenant, invocation, 1)

    def _row(self, cursor, reservation: Reservation):
        preliminary = cursor.execute("SELECT charges_json FROM effect_budget_reservations WHERE tenant_id = ? AND invocation_id = ?", (reservation.tenant_id, reservation.invocation_id)).fetchone()
        if preliminary:
            for unit in sorted(json.loads(preliminary["charges_json"])):
                cursor.execute("UPDATE effect_budget_accounts SET used = used WHERE tenant_id = ? AND unit = ?", (reservation.tenant_id, unit))
        cursor.execute("UPDATE effect_budget_reservations SET fence = fence WHERE tenant_id = ? AND invocation_id = ?", (reservation.tenant_id, reservation.invocation_id))
        row = cursor.execute("SELECT * FROM effect_budget_reservations WHERE tenant_id = ? AND invocation_id = ?", (reservation.tenant_id, reservation.invocation_id)).fetchone()
        if not row or row["fence"] != reservation.fence:
            raise EffectBudgetDenied("Stale external-effect reservation fence.")
        return row

    def dispatch(self, reservation: Reservation) -> None:
        with self.store.transaction() as cursor:
            self._active_policy(cursor)
            row = self._row(cursor, reservation)
            if row["policy_hash"] != self.policy_hash:
                raise EffectBudgetDenied("Reservation policy no longer matches the current approved epoch.")
            if row["status"] != "reserved" or row["lease_expires_at"] <= self.clock():
                raise EffectBudgetDenied("Reservation is not currently dispatchable.")
            if self.store._kill_switch_active_cursor(cursor, reservation.tenant_id):
                raise EffectBudgetDenied("Kill switch blocks consequential dispatch.")
            cursor.execute("UPDATE effect_budget_reservations SET status = 'dispatched' WHERE tenant_id = ? AND invocation_id = ?", (reservation.tenant_id, reservation.invocation_id))
            self._event(cursor, reservation.tenant_id, reservation.invocation_id, "dispatched", {"fence": reservation.fence})

    def finish(self, reservation: Reservation, result: dict[str, Any] | None) -> None:
        with self.store.transaction() as cursor:
            row = self._row(cursor, reservation)
            if row["status"] != "dispatched":
                raise EffectBudgetDenied("Only a dispatched reservation may record an outcome.")
            state = "consumed" if result is not None else "unknown"
            cursor.execute("UPDATE effect_budget_reservations SET status = ?, result_json = ? WHERE tenant_id = ? AND invocation_id = ?", (state, canonical(result) if result is not None else None, reservation.tenant_id, reservation.invocation_id))
            self._event(cursor, reservation.tenant_id, reservation.invocation_id, state, {"fence": reservation.fence})

    def cancel_before_dispatch(self, reservation: Reservation) -> None:
        with self.store.transaction() as cursor:
            row = self._row(cursor, reservation)
            if row["status"] != "reserved":
                raise EffectBudgetDenied("Dispatched exposure cannot be cancelled or automatically refunded.")
            for unit, amount in json.loads(row["charges_json"]).items():
                cursor.execute("UPDATE effect_budget_accounts SET used = used - ? WHERE tenant_id = ? AND unit = ?", (amount, reservation.tenant_id, unit))
            cursor.execute("UPDATE effect_budget_reservations SET status = 'cancelled', fence = fence + 1 WHERE tenant_id = ? AND invocation_id = ?", (reservation.tenant_id, reservation.invocation_id))
            self._event(cursor, reservation.tenant_id, reservation.invocation_id, "cancelled_before_dispatch", {})

    def reconcile(self, reservation: Reservation, *, outcome: str, evidence_ref: str, actor_id: str, result: dict[str, Any] | None = None) -> None:
        """Trusted operator seam only; caller must independently authorize and verify external evidence."""
        if outcome not in {"applied", "not_applied"} or not evidence_ref.strip() or not actor_id.strip() or (outcome == "applied" and result is None):
            raise EffectBudgetDenied("Reconciliation requires an observed outcome, accountable operator and evidence.")
        with self.store.transaction() as cursor:
            row = self._row(cursor, reservation)
            if row["status"] not in {"unknown", "dispatched"}:
                raise EffectBudgetDenied("Only an unresolved external effect can be reconciled.")
            # No refund after dispatch: even a not-applied report cannot prove zero vendor cost/loss.
            cursor.execute("UPDATE effect_budget_reservations SET status = ?, result_json = ?, fence = fence + 1 WHERE tenant_id = ? AND invocation_id = ?", ("consumed" if outcome == "applied" else "reconciled_not_applied", canonical(result) if result is not None else None, reservation.tenant_id, reservation.invocation_id))
            self._event(cursor, reservation.tenant_id, reservation.invocation_id, "reconciled", {"outcome": outcome, "evidence_ref": evidence_ref, "actor_id": actor_id, "budget_refunded": False})
