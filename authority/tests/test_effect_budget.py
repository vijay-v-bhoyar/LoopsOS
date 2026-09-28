from __future__ import annotations

import asyncio
import copy
import json
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import httpx

from loopos_authority.effect_budget import EffectBudget, EffectBudgetDenied
from loopos_authority.models import Actor, ApprovalRequest
from loopos_authority.engine import ExecutionEngine
from loopos_authority.postgres_store import split_postgres_script
from loopos_authority.store import AuthorityStore, Conflict
from loopos_authority.tools import TerminalToolFailure, ToolRegistry
from test_authority import AuthorityHarness, plan, request


def policy(ceiling=100, money=10000, endpoint="http://localhost/change"):
    return {"version": 1, "scope": "cumulative", "tenants": {"tenant-a": {"ceilings": {"dispatch_count": ceiling, "USD_minor": money}, "routes": [{
        "endpoint": endpoint, "method": "POST", "evidence_ref": "fixture-reviewed-payment-contract",
        "charges": [{"unit": "dispatch_count", "fixed": 1}, {"unit": "USD_minor", "amount_path": "amount_minor", "currency_path": "currency", "currency": "USD", "max_amount": 10000}],
    }]}}}


def action(amount=100):
    return {"tool": "http_json_action", "arguments": {"endpoint": "http://localhost/change", "method": "POST", "body": {"amount_minor": amount, "currency": "USD"}}}


class BudgetLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/"budget.sqlite"
        self.store = AuthorityStore(self.path, None)
        self.now = 1000.0
        self.ledger = EffectBudget(self.store, policy(2, 250), clock=lambda: self.now)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def used(self, unit="USD_minor"):
        row = self.store.connection.execute("SELECT used FROM effect_budget_accounts WHERE tenant_id=? AND unit=?", ("tenant-a", unit)).fetchone()
        return row["used"] if row else 0

    def test_aggregate_across_runs_and_atomic_multiple_units(self):
        self.ledger.reserve("tenant-a", "run-1", "inv-1", action(200))
        with self.assertRaisesRegex(EffectBudgetDenied, "exhausted"):
            self.ledger.reserve("tenant-a", "run-2", "inv-2", action(100))
        self.assertEqual(self.used(), 200)
        self.assertEqual(self.used("dispatch_count"), 1)
        self.ledger.reserve("tenant-a", "run-2", "inv-2", action(50))
        self.assertEqual(self.used(), 250)

    def test_success_replay_and_restart_do_not_reserve_twice(self):
        item = self.ledger.reserve("tenant-a", "run", "inv", action())
        self.ledger.dispatch(item)
        self.ledger.finish(item, {"status": "applied"})
        reopened = AuthorityStore(self.path, None)
        try:
            restarted = EffectBudget(reopened, policy(2, 250))
            replay = restarted.reserve("tenant-a", "retry-run", "inv", action())
            self.assertEqual(replay.replay, {"status": "applied"})
            self.assertEqual(self.used(), 100)
        finally:
            reopened.close()

    def test_unknown_outcome_never_expires_into_redispatch(self):
        item = self.ledger.reserve("tenant-a", "run", "inv", action())
        self.ledger.dispatch(item)
        self.ledger.finish(item, None)
        self.now += 10**7
        with self.assertRaises(EffectBudgetDenied):
            self.ledger.reserve("tenant-a", "run", "inv", action())
        with self.assertRaises(EffectBudgetDenied):
            self.ledger.cancel_before_dispatch(item)
        self.assertEqual(self.used(), 100)

    def test_restart_after_dispatch_before_response_remains_reserved(self):
        item = self.ledger.reserve("tenant-a", "run", "inv", action())
        self.ledger.dispatch(item)
        self.now += 10000
        restarted = EffectBudget(self.store, policy(2, 250), clock=lambda: self.now)
        with self.assertRaises(EffectBudgetDenied):
            restarted.reserve("tenant-a", "new-run", "inv", action())
        self.assertEqual(self.used(), 100)

    def test_expired_pre_dispatch_lease_has_fencing_and_no_double_charge(self):
        old = self.ledger.reserve("tenant-a", "run", "inv", action())
        self.now += 61
        current = self.ledger.reserve("tenant-a", "run", "inv", action())
        with self.assertRaisesRegex(EffectBudgetDenied, "fence"):
            self.ledger.dispatch(old)
        with self.assertRaisesRegex(EffectBudgetDenied, "fence"):
            self.ledger.cancel_before_dispatch(old)
        self.ledger.dispatch(current)
        self.assertEqual(self.used(), 100)

    def test_cancel_before_dispatch_releases_but_old_fence_cannot_dispatch(self):
        item = self.ledger.reserve("tenant-a", "run", "inv", action())
        self.ledger.cancel_before_dispatch(item)
        self.assertEqual(self.used(), 0)
        with self.assertRaises(EffectBudgetDenied):
            self.ledger.dispatch(item)

    def test_operator_reconciliation_preserves_exposure_and_fences_stale_worker(self):
        item = self.ledger.reserve("tenant-a", "run", "inv", action())
        self.ledger.dispatch(item)
        self.ledger.reconcile(item, outcome="not_applied", evidence_ref="receipt:no-effect", actor_id="operator-1")
        self.assertEqual(self.used(), 100)
        with self.assertRaises(EffectBudgetDenied):
            self.ledger.finish(item, {"status": "applied"})
        with self.assertRaises(EffectBudgetDenied):
            self.ledger.reserve("tenant-a", "run", "inv", action())

    def test_compensation_is_an_additional_exposure_not_a_refund(self):
        item = self.ledger.reserve("tenant-a", "run", "inv", action(200))
        self.ledger.dispatch(item)
        self.ledger.finish(item, None)
        compensation = self.ledger.reserve("tenant-a", "run", "compensation-inv", action(50))
        self.ledger.dispatch(compensation)
        self.ledger.finish(compensation, None)
        self.assertEqual(self.used(), 250)
        with self.assertRaises(EffectBudgetDenied):
            self.ledger.reserve("tenant-a", "run", "retry-compensation", action(1))

    def test_missing_policy_bad_amount_currency_and_tenant_fail_closed(self):
        with self.assertRaises(EffectBudgetDenied):
            EffectBudget(self.store, None).reserve("tenant-a", "run", "inv", action())
        with self.assertRaises(EffectBudgetDenied):
            self.ledger.reserve("tenant-b", "run", "inv", action())
        for amount in (-1, 1.1, True, "100", 10001):
            with self.subTest(amount=amount), self.assertRaises(EffectBudgetDenied):
                self.ledger.reserve("tenant-a", "run", "inv", action(amount))
        wrong = action()
        wrong["arguments"]["body"]["currency"] = "EUR"
        with self.assertRaises(EffectBudgetDenied):
            self.ledger.reserve("tenant-a", "run", "inv", wrong)
        self.assertEqual(self.used(), 0)

    def test_durable_storage_unavailable_is_not_in_memory_fallback(self):
        self.store.connection.execute("DROP TABLE effect_budget_accounts")
        self.assertFalse(self.ledger.ready())
        with self.assertRaises(sqlite3.Error):
            self.ledger.reserve("tenant-a", "run", "inv", action())

    def test_ledger_history_is_append_only(self):
        self.ledger.reserve("tenant-a", "run", "inv", action())
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.connection.execute("DELETE FROM effect_budget_events")

    def test_real_concurrent_connections_cannot_overspend(self):
        stores = [AuthorityStore(self.path, None) for _ in range(8)]
        ledgers = [EffectBudget(store, {**policy(100, 250), "policy_epoch": 2}) for store in stores]
        barrier = threading.Barrier(8)
        def compete(index):
            barrier.wait()
            try:
                ledgers[index].reserve("tenant-a", f"run-{index}", f"inv-{index}", action(100))
                return True
            except EffectBudgetDenied:
                return False
        try:
            with ThreadPoolExecutor(max_workers=8) as pool:
                outcomes = list(pool.map(compete, range(8)))
            self.assertEqual(sum(outcomes), 2)
            self.assertEqual(self.used(), 200)
        finally:
            for store in stores:
                store.close()

    def test_changed_policy_cannot_reclaim_or_dispatch_old_reservations(self):
        old = self.ledger.reserve("tenant-a", "run", "inv", action(200))
        with self.assertRaisesRegex(EffectBudgetDenied, "epoch"):
            EffectBudget(self.store, policy(2, 100))
        new = EffectBudget(self.store, {**policy(2, 100), "policy_epoch": 2}, clock=lambda: self.now)
        self.assertFalse(self.ledger.ready())
        with self.assertRaisesRegex(EffectBudgetDenied, "stale"):
            self.ledger.dispatch(old)
        with self.assertRaisesRegex(EffectBudgetDenied, "policy"):
            new.dispatch(old)
        self.now += 100
        with self.assertRaisesRegex(EffectBudgetDenied, "policy"):
            new.reserve("tenant-a", "run", "inv", action(200))
        self.assertEqual(self.used(), 200)
        with self.assertRaisesRegex(EffectBudgetDenied, "epoch"):
            EffectBudget(self.store, policy(2, 250))

    def test_policy_revocation_fences_existing_worker(self):
        old = self.ledger.reserve("tenant-a", "run", "inv", action())
        EffectBudget(self.store, {"version": 1, "scope": "cumulative", "policy_epoch": 2, "tenants": {}})
        with self.assertRaises(EffectBudgetDenied):
            self.ledger.dispatch(old)

    def test_caller_cannot_mutate_policy_dictionary_to_expand_live_ceiling(self):
        configured = policy(2, 250)
        ledger = EffectBudget(self.store, configured)
        configured["tenants"]["tenant-a"]["ceilings"]["USD_minor"] = 10000
        with self.assertRaisesRegex(EffectBudgetDenied, "exhausted"):
            ledger.reserve("tenant-a", "run", "inv", action(300))
        self.assertEqual(self.used(), 0)

    def test_kill_switch_fences_dispatch_and_allows_only_unsent_cancellation(self):
        item = self.ledger.reserve("tenant-a", "run", "inv", action())
        self.store.activate_kill_switch(Actor(tenant_id="tenant-a", user_id="executive", name="Executive", role="Executive"), "Stop synthetic effect")
        with self.assertRaisesRegex(EffectBudgetDenied, "Kill switch"):
            self.ledger.dispatch(item)
        self.ledger.cancel_before_dispatch(item)
        self.assertEqual(self.used(), 0)

    def test_postgres_migration_has_all_tables_rls_and_append_only_history(self):
        migration = Path(__file__).resolve().parents[2]/"supabase/migrations/20260921010000_effect_budget.sql"
        text = migration.read_text(encoding="utf-8").lower()
        for table in ("effect_budget_policy", "effect_budget_accounts", "effect_budget_reservations", "effect_budget_events"):
            self.assertIn(f"create table if not exists {table}", text)
            self.assertIn(f"alter table {table} enable row level security", text)
        statements = split_postgres_script(text)
        self.assertEqual(len([stmt for stmt in statements if stmt.startswith("do $$")]), 1)
        self.assertIn("effect_budget_events_no_delete", text)
        self.assertIn("effect_budget_events_no_update", text)
        self.assertIn("revoke all on effect_budget_policy", text)


class EffectDispatchTests(AuthorityHarness):
    def test_invocation_replay_is_bound_to_workspace_and_workflow(self):
        execution_plan = plan(rollback=True, external=True, tool="http_json_action", arguments=action()["arguments"])
        first = self.store.create_run(self.operator, request(execution_plan=execution_plan), "workflow-scope-origin")
        action_spec = execution_plan.action
        invocation_id, replay = self.store.begin_invocation(
            first.tenant_id, first.run_id, action_spec.tool, action_spec.idempotency_key,
            action_spec.model_dump(mode="json"),
        )
        self.assertIsNone(replay)
        result = {"status": "applied", "sensitive_record": "origin-run-result"}
        self.store.complete_invocation(first.tenant_id, first.run_id, invocation_id, result)

        same_workflow = self.store.create_run(
            Actor(tenant_id="tenant-a", user_id="operator-b", name="Operator B", role="Operator"),
            request(execution_plan=execution_plan),
            "workflow-scope-same-workflow",
        )
        same_id, same_result = self.store.begin_invocation(
            same_workflow.tenant_id, same_workflow.run_id, action_spec.tool, action_spec.idempotency_key,
            action_spec.model_dump(mode="json"),
        )
        self.assertEqual(same_id, invocation_id)
        self.assertEqual(same_result, result)

        other_workflow = self.store.create_run(
            self.operator,
            request(loop_id="loop-008-requirements-traceability-loop", execution_plan=execution_plan),
            "workflow-scope-other-workflow",
        )
        with self.assertRaisesRegex(Conflict, "outside its tenant workflow scope"):
            self.store.begin_invocation(
                other_workflow.tenant_id, other_workflow.run_id, action_spec.tool, action_spec.idempotency_key,
                action_spec.model_dump(mode="json"),
            )

        other_workspace_request = request(execution_plan=execution_plan).model_copy(update={"workspace_id": "workspace-other"})
        other_workspace = self.store.create_run(
            self.operator, other_workspace_request, "workflow-scope-other-workspace"
        )
        with self.assertRaisesRegex(Conflict, "outside its tenant workflow scope"):
            self.store.begin_invocation(
                other_workspace.tenant_id, other_workspace.run_id, action_spec.tool, action_spec.idempotency_key,
                action_spec.model_dump(mode="json"),
            )

        count = self.store.connection.execute("SELECT COUNT(*) AS count FROM tool_invocations").fetchone()["count"]
        self.assertEqual(count, 1)

    def test_concurrent_cross_workflow_key_race_admits_only_one_scope(self):
        execution_plan = plan(rollback=True, external=True, tool="http_json_action", arguments=action()["arguments"])
        first = self.store.create_run(self.operator, request(execution_plan=execution_plan), "workflow-race-origin")
        other_store = AuthorityStore(self.settings.database_path, self.corpus)
        other_run = other_store.create_run(
            self.operator,
            request(loop_id="loop-008-requirements-traceability-loop", execution_plan=execution_plan),
            "workflow-race-other",
        )
        barrier = threading.Barrier(2)
        action_spec = execution_plan.action

        def begin(store, run):
            barrier.wait()
            try:
                invocation_id, replay = store.begin_invocation(
                    run.tenant_id, run.run_id, action_spec.tool, action_spec.idempotency_key,
                    action_spec.model_dump(mode="json"),
                )
                return ("admitted", invocation_id, replay)
            except Conflict:
                return ("conflict", None, None)

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = [
                    pool.submit(begin, self.store, first),
                    pool.submit(begin, other_store, other_run),
                ]
                outcomes = [future.result(timeout=10) for future in results]
            self.assertCountEqual([item[0] for item in outcomes], ["admitted", "conflict"])
            self.assertEqual(
                self.store.connection.execute("SELECT COUNT(*) AS count FROM tool_invocations").fetchone()["count"],
                1,
            )
        finally:
            other_store.close()

    def test_engine_blocks_unknown_outcome_without_claiming_local_compensation(self):
        calls = []
        def handler(req):
            calls.append(req)
            raise httpx.ReadTimeout("synthetic lost response")
        tools = ToolRegistry(replace(self.settings, allowed_http_hosts=("localhost",), effect_budget_policy=policy()), self.store, transport=httpx.MockTransport(handler))
        engine = ExecutionEngine(self.corpus, self.store, tools)
        execution_plan = plan(rollback=True, external=True, tool="http_json_action", arguments=action()["arguments"])
        run = self.store.create_run(self.operator, request(execution_plan=execution_plan), "unknown-engine-run")
        try:
            asyncio.run(engine.execute(run.tenant_id, run.run_id))
            self.store.approve(self.approver, run.run_id, ApprovalRequest(payload_hash=run.payload_hash, decision_reason="Fixture action and fallback reviewed."))
            asyncio.run(engine.execute(run.tenant_id, run.run_id))
            current = self.store.get_run(run.tenant_id, run.run_id)
            self.assertEqual(current.state, "BLOCKED")
            self.assertEqual(current.output["action_error_code"], "external_outcome_unknown")
            self.assertEqual(len(calls), 1)
            invocations = self.store.connection.execute("SELECT tool_name FROM tool_invocations").fetchall()
            self.assertEqual([row["tool_name"] for row in invocations], ["http_json_action"])
        finally:
            asyncio.run(tools.close())
    def test_lost_response_holds_budget_and_same_key_never_redispatches(self):
        calls = []
        def handler(req):
            calls.append(req)
            raise httpx.ReadTimeout("synthetic lost response")
        settings = replace(self.settings, allowed_http_hosts=("localhost",), effect_budget_policy=policy())
        tools = ToolRegistry(settings, self.store, transport=httpx.MockTransport(handler))
        execution_plan = plan(rollback=True, external=True, tool="http_json_action", arguments=action()["arguments"])
        run = self.store.create_run(self.operator, request(execution_plan=execution_plan), "unknown-effect-run")
        try:
            for _ in range(2):
                with self.assertRaises(TerminalToolFailure):
                    asyncio.run(tools.execute_action(run.tenant_id, run.run_id, execution_plan.action, 3))
            self.assertEqual(len(calls), 1)
            row = self.store.connection.execute("SELECT status FROM effect_budget_reservations").fetchone()
            self.assertEqual(row["status"], "unknown")
        finally:
            asyncio.run(tools.close())

    def test_missing_policy_denies_http_before_network_and_local_record_still_works(self):
        calls = []
        tools = ToolRegistry(replace(self.settings, allowed_http_hosts=("localhost",)), self.store,
            transport=httpx.MockTransport(lambda req: calls.append(req) or httpx.Response(200, json={"ok": True})))
        execution_plan = plan(rollback=True, external=True, tool="http_json_action", arguments=action()["arguments"])
        run = self.store.create_run(self.operator, request(execution_plan=execution_plan), "unconfigured-effect-run")
        try:
            with self.assertRaisesRegex(TerminalToolFailure, "ceiling"):
                asyncio.run(tools.execute_action(run.tenant_id, run.run_id, execution_plan.action, 3))
            self.assertEqual(calls, [])
            local = plan().action
            result = asyncio.run(tools.execute_action(run.tenant_id, run.run_id, local, 3))
            self.assertEqual(result["status"], "applied")
        finally:
            asyncio.run(tools.close())
