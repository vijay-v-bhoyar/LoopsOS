from __future__ import annotations

from typing import Any

from .corpus import Corpus
from .store import AuthorityStore, Conflict, Forbidden
from .tools import TerminalToolFailure, ToolFailure, ToolRegistry


class ExecutionEngine:
    def __init__(self, corpus: Corpus, store: AuthorityStore, tools: ToolRegistry):
        self.corpus = corpus
        self.store = store
        self.tools = tools

    async def execute(self, tenant_id: str, run_id: str, reclaim_running: bool = False) -> None:
        run = self.store.claim_run(tenant_id, run_id, reclaim_running=reclaim_running)
        try:
            if self._interrupt_if_kill_switch_active(run, "before_preparation"):
                return
            if run.state == "EFFECTIVENESS_PENDING":
                await self._complete_effectiveness(run)
                return
            run = await self._prepare(run)
            if self._interrupt_if_kill_switch_active(run, "before_authorization"):
                return
            if run.state == "PLANNED":
                if run.requires_approval:
                    try:
                        self.store.consume_approval(tenant_id, run_id, run.payload_hash)
                    except Forbidden:
                        self.store.release_run(tenant_id, run_id, "awaiting_approval")
                        return
                    if self._interrupt_if_kill_switch_active(run, "after_approval"):
                        return
                run = self.store.transition(tenant_id, run_id, "AUTHORIZED", "authority-engine", {"payload_hash": run.payload_hash})

            if run.state == "AUTHORIZED":
                if self._interrupt_if_kill_switch_active(run, "before_action_dispatch"):
                    return
                run = self.store.transition(tenant_id, run_id, "ACTION_IN_PROGRESS", "authority-engine")

            if run.state != "ACTION_IN_PROGRESS":
                raise Conflict(f"Run cannot execute from {run.state}.")

            self.store.increment_attempt(tenant_id, run_id)
            evidence = self.store.list_evidence(tenant_id, run_id)
            try:
                action_output = await self.tools.execute_action(tenant_id, run_id, run.plan.action, run.plan.max_attempts)
            except ToolFailure as error:
                await self._fail_action(run, str(error))
                return

            if self._interrupt_if_kill_switch_active(
                run,
                "after_action_dispatch",
                action_output=action_output,
                action_external_effect=run.plan.action.external_effect,
            ):
                return
            run = self.store.transition(tenant_id, run_id, "ACTION_APPLIED", "authority-engine", {"action_output": action_output})
            validation_passed, validation_results = await self._run_probes(run, "validation", run.plan.validation_probes, action_output, evidence)
            self.store.set_output(tenant_id, run_id, {
                "action": action_output,
                "validation": validation_results,
                "evidence": [{"evidence_id": item["evidence_id"], "content_hash": item["content_hash"]} for item in evidence],
                "invariant": self.corpus.state_machine["invariant"],
                "standard_hash": self.corpus.standard_hash,
            })
            if not validation_passed:
                run = self.store.transition(tenant_id, run_id, "VALIDATION_FAILED", "authority-engine", {"probe_results": validation_results})
                await self._rollback_or_block(run, "Validation probes failed.")
                return

            run = self.store.transition(tenant_id, run_id, "VALIDATION_PASSED", "authority-engine")
            run = self.store.transition(tenant_id, run_id, "PROOF_GREEN", "authority-engine", {"probe_results": validation_results})
            run = self.store.transition(tenant_id, run_id, "EFFECTIVENESS_PENDING", "authority-engine")
            run = self.store.get_run(tenant_id, run_id)
            if run.plan.observation_delay_seconds > 0:
                self.store.schedule_effectiveness(tenant_id, run_id, run.plan.observation_delay_seconds)
                return
            await self._complete_effectiveness(run)
        except Exception as error:
            current = self.store.get_run(tenant_id, run_id)
            if not self.corpus.is_terminal(current.state):
                if current.state == "EFFECTIVENESS_PENDING":
                    self.store.transition(tenant_id, run_id, "EFFECTIVENESS_FAILED", "authority-engine", {"error": str(error)})
                elif self.corpus.allows_transition(current.state, "BLOCKED"):
                    self.store.transition(tenant_id, run_id, "BLOCKED", "authority-engine", {"error": str(error)})
                elif current.state == "ACTION_APPLIED":
                    failed = self.store.transition(tenant_id, run_id, "VALIDATION_FAILED", "authority-engine", {"error": str(error)})
                    await self._rollback_or_block(failed, str(error))
                    return
                elif current.state == "VALIDATION_PASSED":
                    failed = self.store.transition(tenant_id, run_id, "PROOF_FAILED", "authority-engine", {"error": str(error)})
                    await self._rollback_or_block(failed, str(error))
                    return
            self.store.release_run(tenant_id, run_id, "failed", str(error))

    async def rollback(self, tenant_id: str, run_id: str, reason: str, reclaim_running: bool = False) -> None:
        run = self.store.claim_run(tenant_id, run_id, reclaim_running=reclaim_running)
        if self._interrupt_if_kill_switch_active(run, "before_rollback"):
            return
        await self._rollback_or_block(run, reason)

    def _interrupt_if_kill_switch_active(
        self,
        run,
        phase: str,
        *,
        action_output: dict[str, Any] | None = None,
        action_external_effect: bool = False,
    ) -> bool:
        if not self.store.is_kill_switch_active(run.tenant_id):
            return False
        self.store.interrupt_run_for_kill_switch(
            run.tenant_id,
            run.run_id,
            phase,
            action_output=action_output,
            action_external_effect=action_external_effect,
        )
        return True

    async def _prepare(self, run):
        tenant_id, run_id = run.tenant_id, run.run_id
        if run.state == "TRIGGERED":
            run = self.store.transition(tenant_id, run_id, "QUALIFIED", "authority-engine", {"plan_hash": run.payload_hash})
        if run.state == "QUALIFIED":
            for request in run.plan.evidence:
                await self.tools.collect_evidence(tenant_id, run_id, request)
            run = self.store.transition(tenant_id, run_id, "OBSERVED", "authority-engine", {"evidence_count": len(run.plan.evidence)})
        if run.state == "OBSERVED":
            descriptor = self.corpus.loop_descriptors[run.loop_id]
            run = self.store.transition(tenant_id, run_id, "DIAGNOSED", "authority-engine", {"run_summary": descriptor["purpose"]["run_summary"]})
        if run.state == "DIAGNOSED":
            run = self.store.transition(tenant_id, run_id, "PRIORITIZED", "authority-engine", {"risk_tier": run.risk_tier})
        if run.state == "PRIORITIZED":
            run = self.store.transition(tenant_id, run_id, "PLANNED", "authority-engine", {"tool": run.plan.action.tool, "payload_hash": run.payload_hash})
        return run

    async def _run_probes(self, run, phase: str, probes, action_output: dict[str, Any], evidence: list[dict[str, Any]]) -> tuple[bool, list[dict[str, Any]]]:
        results = []
        all_passed = True
        for probe in probes:
            try:
                passed, detail = await self.tools.run_probe(probe, action_output, evidence)
            except ToolFailure as error:
                passed, detail = False, {"error": str(error), "code": error.code}
            self.store.save_probe(run.tenant_id, run.run_id, phase, probe.probe_id, passed, detail)
            results.append({"probe_id": probe.probe_id, "passed": passed, "detail": detail})
            all_passed = all_passed and passed
        return all_passed, results

    async def _complete_effectiveness(self, run) -> None:
        if self._interrupt_if_kill_switch_active(run, "before_effectiveness_probe"):
            return
        output = run.output or {}
        action_output = output.get("action")
        if not isinstance(action_output, dict):
            raise TerminalToolFailure("Durable action output is missing; effectiveness cannot be evaluated.")
        evidence = self.store.list_evidence(run.tenant_id, run.run_id)
        effectiveness_passed, effectiveness_results = await self._run_probes(run, "effectiveness", run.plan.effectiveness_probes, action_output, evidence)
        if effectiveness_passed:
            self.store.set_output(run.tenant_id, run.run_id, {**output, "effectiveness": effectiveness_results})
            self.store.transition(run.tenant_id, run.run_id, "EFFECTIVENESS_PROVEN", "authority-engine", {"probe_results": effectiveness_results})
            self.store.release_run(run.tenant_id, run.run_id, "completed")
        else:
            self.store.set_output(run.tenant_id, run.run_id, {**output, "effectiveness": effectiveness_results})
            self.store.transition(run.tenant_id, run.run_id, "EFFECTIVENESS_FAILED", "authority-engine", {"probe_results": effectiveness_results})
            self.store.release_run(run.tenant_id, run.run_id, "failed", "Effectiveness probes failed.")

    async def _fail_action(self, run, message: str) -> None:
        self.store.set_output(run.tenant_id, run.run_id, {
            "action_error": message,
            "invariant": self.corpus.state_machine["invariant"],
            "standard_hash": self.corpus.standard_hash,
        })
        if self.corpus.allows_transition("ACTION_IN_PROGRESS", "VALIDATION_FAILED"):
            failed = self.store.transition(run.tenant_id, run.run_id, "VALIDATION_FAILED", "authority-engine", {"tool_error": message})
            await self._rollback_or_block(failed, message)
        else:
            self.store.release_run(run.tenant_id, run.run_id, "failed", message)

    async def _rollback_or_block(self, run, reason: str) -> None:
        if self._interrupt_if_kill_switch_active(run, "rollback_blocked"):
            return
        if run.plan.rollback and self.corpus.allows_transition(run.state, "ROLLED_BACK"):
            try:
                result = await self.tools.execute_action(run.tenant_id, run.run_id, run.plan.rollback, run.plan.max_attempts)
                current_output = self.store.get_run(run.tenant_id, run.run_id).output or {}
                self.store.set_output(run.tenant_id, run.run_id, {**current_output, "rollback": {"status": "compensated", "reason": reason, "result": result}})
                self.store.transition(run.tenant_id, run.run_id, "ROLLED_BACK", "authority-engine", {"reason": reason, "rollback_result": result})
                self.store.release_run(run.tenant_id, run.run_id, "rolled_back", reason)
                return
            except (ToolFailure, Conflict) as error:
                reason = f"{reason} Rollback failed: {error}"
                current_output = self.store.get_run(run.tenant_id, run.run_id).output or {}
                self.store.set_output(run.tenant_id, run.run_id, {**current_output, "rollback": {"status": "failed", "reason": reason}})
        current = self.store.get_run(run.tenant_id, run.run_id)
        if "rollback" not in (current.output or {}):
            self.store.set_output(run.tenant_id, run.run_id, {**(current.output or {}), "rollback": {"status": "not_available", "reason": reason}})
            current = self.store.get_run(run.tenant_id, run.run_id)
        if self.corpus.allows_transition(current.state, "BLOCKED"):
            self.store.transition(run.tenant_id, run.run_id, "BLOCKED", "authority-engine", {"reason": reason})
        self.store.release_run(run.tenant_id, run.run_id, "failed", reason)
