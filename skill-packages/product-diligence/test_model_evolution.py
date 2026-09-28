"""Real-byte evidence and adversarial regressions for the bounded evolution gate."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import model_evolution as gate


class EvolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = datetime(2026, 9, 19, 12, tzinfo=timezone.utc)
        self.subject = {"product": "example", "revision": "commit-one", "environment": "staging", "configuration": "config-one"}
        self.window = {"observed_at": "2026-09-19T10:00:00Z", "expires_at": "2026-09-20T10:00:00Z"}
        self.controls = {}
        for name, keys in gate.CONTROL_CHECKS.items():
            proof = {"kind": "model-evolution/control-proof@1", "subject": self.subject,
                     **self.window, "control": name, "owner": "named-owner", "covered_tasks": ["support"],
                     "checks": dict.fromkeys(keys, True)}
            self.controls[name] = {"owner": "named-owner", "evidence": self.write(f"{name}.json", proof)}
        configuration = self.write("task-configuration.json", {"temperature": 0, "tools": []})
        champion = {"provider": "provider-a", "id": "model-a", "version": "snapshot-a", "version_mutable": False, "configuration_sha256": configuration["sha256"], "capabilities": ["json", "tools"]}
        self.task = {
            "id": "support", "champion": champion, "configuration": configuration,
            "required_capabilities": ["json", "tools"],
            "thresholds": {"min_samples": 100, "quality_noninferiority_margin": 0.01,
                           "min_quality_uplift": 0.02, "min_cost_improvement_fraction": 0.15,
                           "min_latency_improvement_fraction": 0.15, "max_cost_per_task": 0.10,
                           "max_latency_p95_ms": 500, "min_confidence_level": 0.95,
                           "min_product_outcome_improvement": 0},
            "evaluation_protocol": {name: self.write(f"{name}.txt", f"actual {name} artifact") for name in ("dataset", "scorer", "configuration")},
            "product_outcome": {"metric": "successful_resolution_rate", "direction": "higher"},
        }
        self.challenger = {**champion, "id": "model-b", "version": "snapshot-b"}
        self.report = {
            "kind": "model-evolution/paired-evaluation@1", "subject": self.subject, **self.window,
            "candidate_id": "candidate-one", "task": "support", "champion": champion,
            "challenger": self.challenger,
            **{f"{name}_sha256": receipt["sha256"] for name, receipt in self.task["evaluation_protocol"].items()},
            "paired": True, "trace": self.write("trace.jsonl", '{"task":"support","result":"recorded"}\n'),
            "sample_count": 200, "confidence_level": 0.95, "confidence_method": "paired bootstrap",
            "checks": dict.fromkeys(gate.CANDIDATE_CHECKS, True),
            "quality": {"champion_mean": 0.8, "challenger_mean": 0.85, "delta_lower_bound": 0.03, "delta_upper_bound": 0.07},
            "cost": {"champion_per_task": 0.08, "challenger_per_task": 0.06},
            "latency": {"champion_p95_ms": 400, "challenger_p95_ms": 300},
            "product_outcome": {"metric": "successful_resolution_rate", "champion": 0.60, "challenger": 0.65},
        }
        self.candidate = {"id": "candidate-one", "task": "support", "model": self.challenger,
                          "configuration": configuration, "evaluation": self.write("evaluation.json", self.report)}
        self.config = {"schema": gate.SCHEMA, "subject": self.subject, **self.window,
                       "controls": self.controls, "refresh": {
                           "owner": "named-owner", "cadence_hours": 24,
                           "last_reviewed_at": "2026-09-19T11:00:00Z", "next_review_at": "2026-09-20T10:00:00Z",
                           "official_sources": [{"provider": "provider-a", "url": "https://provider.example/models",
                                                 **self.window, "artifact": self.write("provider-source.txt", "captured provider page")}],
                       }, "tasks": [self.task], "candidates": [self.candidate]}

    def write(self, name, value):
        data = value.encode() if isinstance(value, str) else json.dumps(value).encode()
        (self.root / name).write_bytes(data)
        return {"path": name, "sha256": hashlib.sha256(data).hexdigest()}

    def evaluate(self):
        receipt = self.write("evolution.json", self.config)
        return gate.evaluate({"subject": self.subject, "model_evolution": receipt}, self.root, self.now)

    def candidate_status(self, expected="NOT_READY", reason=None):
        self.candidate["evaluation"] = self.write("evaluation.json", self.report)
        result = self.evaluate()
        self.assertEqual("QUALIFIED", result["status"], result)
        decision = result["candidate_decisions"][0]
        self.assertEqual(expected, decision["status"], decision)
        self.assertFalse(decision["execution_authorized"])
        if reason:
            self.assertIn(reason, " ".join(decision["reasons"]))
        return result

    def test_actual_receipts_qualify_capability_and_candidate_without_authority(self):
        result = self.evaluate()
        self.assertEqual("QUALIFIED", result["status"], result)
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["capability_only"])
        self.assertEqual(3, len(result["candidate_decisions"][0]["improvement_paths"]))

    def test_empty_candidates_still_prove_current_upgrade_capability(self):
        self.config["candidates"] = []
        result = self.evaluate()
        self.assertEqual("QUALIFIED", result["status"], result)
        self.assertTrue(result["capability_only"])

    def test_missing_config_is_unknown(self):
        result = gate.evaluate({"subject": self.subject}, self.root, self.now)
        self.assertEqual("EVIDENCE_MISSING", result["status"])

    def test_subject_mismatch_fails(self):
        receipt = self.write("evolution.json", self.config)
        result = gate.evaluate({"subject": {**self.subject, "revision": "other"}, "model_evolution": receipt}, self.root, self.now)
        self.assertEqual("NOT_READY", result["status"])
        self.assertIn("subject mismatch", result["reasons"][0])

    def test_actual_tamper_is_detected(self):
        (self.root / "policy_enforcement.json").write_text("changed", encoding="utf-8")
        result = self.evaluate()
        self.assertEqual("NOT_READY", result["status"])
        self.assertIn("hash mismatch", result["reasons"][0])

    def test_config_tamper_is_detected(self):
        receipt = self.write("evolution.json", self.config)
        (self.root / "evolution.json").write_text("{}", encoding="utf-8")
        result = gate.evaluate({"subject": self.subject, "model_evolution": receipt}, self.root, self.now)
        self.assertEqual("NOT_READY", result["status"])

    def test_missing_control_receipt_remains_unknown(self):
        (self.root / "fallback_recovery.json").unlink()
        self.assertEqual("EVIDENCE_MISSING", self.evaluate()["status"])

    def test_all_control_checks_are_required(self):
        for control, checks in gate.CONTROL_CHECKS.items():
            filename = f"{control}.json"
            saved = (self.root / filename).read_bytes()
            for key in checks:
                with self.subTest(control=control, check=key):
                    proof = json.loads(saved)
                    proof["checks"][key] = False
                    self.controls[control]["evidence"] = self.write(filename, proof)
                    self.assertEqual("NOT_READY", self.evaluate()["status"])
            self.controls[control]["evidence"] = self.write(filename, json.loads(saved))

    def test_expiry_and_future_dates_fail(self):
        for key, value in (("expires_at", "2026-09-19T12:00:00Z"), ("observed_at", "2026-09-20T12:00:00Z")):
            with self.subTest(key=key):
                config = copy.deepcopy(self.config)
                self.config[key] = value
                self.assertEqual("NOT_READY", self.evaluate()["status"])
                self.config = config

    def test_overdue_refresh_and_unbounded_cadence_fail(self):
        self.config["refresh"]["next_review_at"] = "2026-09-19T11:00:00Z"
        self.assertEqual("NOT_READY", self.evaluate()["status"])
        self.config["refresh"]["next_review_at"] = "2026-09-30T11:00:00Z"
        self.assertEqual("NOT_READY", self.evaluate()["status"])

    def test_moving_alias_does_not_qualify(self):
        self.task["champion"]["version"] = "latest"
        self.assertEqual("NOT_READY", self.evaluate()["status"])

    def test_provider_mutability_must_be_explicit(self):
        self.task["champion"]["version_mutable"] = True
        self.assertEqual("NOT_READY", self.evaluate()["status"])
        self.task["champion"].pop("version_mutable")
        self.assertEqual("EVIDENCE_MISSING", self.evaluate()["status"])

    def test_control_proof_must_cover_all_declared_tasks(self):
        proof = json.loads((self.root / "policy_enforcement.json").read_bytes())
        proof["covered_tasks"] = ["different-task"]
        self.controls["policy_enforcement"]["evidence"] = self.write("policy_enforcement.json", proof)
        result = self.evaluate()
        self.assertEqual("NOT_READY", result["status"])
        self.assertIn("declared tasks", result["reasons"][0])

    def test_metadata_change_alone_is_not_a_challenger(self):
        self.candidate["model"] = {**self.task["champion"], "capabilities": ["tools", "json"]}
        self.candidate_status(reason="equals champion")

    def test_every_threshold_must_be_supplied(self):
        for key in list(self.task["thresholds"]):
            with self.subTest(key=key):
                value = self.task["thresholds"].pop(key)
                self.assertEqual("EVIDENCE_MISSING", self.evaluate()["status"])
                self.task["thresholds"][key] = value

    def test_nonfinite_and_bool_thresholds_rejected(self):
        for value in (math.nan, math.inf, True, -1):
            with self.subTest(value=value):
                self.task["thresholds"]["max_cost_per_task"] = value
                self.assertEqual("NOT_READY", self.evaluate()["status"])

    def test_paired_protocol_change_rejected(self):
        for key in ("dataset_sha256", "scorer_sha256", "configuration_sha256"):
            with self.subTest(key=key):
                saved = self.report[key]
                self.report[key] = "0" * 64
                self.candidate_status(reason="mismatch")
                self.report[key] = saved

    def test_trace_bytes_are_required(self):
        (self.root / "trace.jsonl").unlink()
        self.candidate_status("EVIDENCE_MISSING")

    def test_evaluation_subject_and_model_must_match(self):
        self.report["subject"] = {**self.subject, "configuration": "different"}
        self.candidate_status(reason="subject mismatch")
        self.report["subject"] = self.subject
        self.report["challenger"] = {**self.challenger, "version": "other"}
        self.candidate_status(reason="pins differ")

    def test_candidate_expiry_rejected_without_invalidating_capability(self):
        self.report["expires_at"] = "2026-09-18T12:00:00Z"
        result = self.candidate_status(reason="expired")
        self.assertTrue(result["capability_only"])

    def test_small_sample_or_false_paired_rejected(self):
        self.report["sample_count"] = 2
        self.candidate_status(reason="insufficient samples")
        self.report["sample_count"] = 200
        self.report["paired"] = False
        self.candidate_status(reason="paired comparison")

    def test_all_candidate_checks_are_hard_gates(self):
        for check in gate.CANDIDATE_CHECKS:
            with self.subTest(check=check):
                self.report["checks"][check] = False
                self.candidate_status(reason=check)
                self.report["checks"][check] = True

    def test_cheap_candidate_cannot_mask_quality_regression(self):
        self.report["quality"] = {"champion_mean": 0.8, "challenger_mean": 0.7, "delta_lower_bound": -0.15, "delta_upper_bound": -0.05}
        self.candidate_status(reason="noninferiority")

    def test_cost_only_improvement_requires_quality_noninferiority(self):
        self.report["quality"] = {"champion_mean": 0.8, "challenger_mean": 0.8, "delta_lower_bound": -0.005, "delta_upper_bound": 0.005}
        self.report["latency"]["challenger_p95_ms"] = 400
        result = self.candidate_status("QUALIFIED")
        self.assertEqual(["cost_improvement_with_quality_noninferiority"], result["candidate_decisions"][0]["improvement_paths"])

    def test_no_uplift_retains_champion(self):
        self.report["quality"] = {"champion_mean": 0.8, "challenger_mean": 0.8, "delta_lower_bound": -0.005, "delta_upper_bound": 0.005}
        self.report["cost"]["challenger_per_task"] = 0.08
        self.report["latency"]["challenger_p95_ms"] = 400
        self.candidate_status(reason="no required improvement")

    def test_cost_and_latency_caps_are_hard(self):
        for field, key, value in (("cost", "challenger_per_task", 0.2), ("latency", "challenger_p95_ms", 900)):
            with self.subTest(field=field):
                saved = self.report[field][key]
                self.report[field][key] = value
                self.candidate_status(reason="limit exceeded")
                self.report[field][key] = saved

    def test_measured_product_outcome_regression_blocks(self):
        self.report["product_outcome"]["challenger"] = 0.4
        self.candidate_status(reason="product outcome regressed")

    def test_impossible_quality_interval_rejected(self):
        self.report["quality"]["delta_lower_bound"] = 0.06
        self.candidate_status(reason="inconsistent quality interval")

    def test_duplicate_candidate_ids_and_tasks_rejected(self):
        self.config["candidates"].append(copy.deepcopy(self.candidate))
        self.assertEqual("NOT_READY", self.evaluate()["status"])
        self.config["candidates"].pop()
        self.config["tasks"].append(copy.deepcopy(self.task))
        self.assertEqual("NOT_READY", self.evaluate()["status"])

    def test_escaping_receipt_paths_rejected_before_read(self):
        self.controls["task_routing"]["evidence"]["path"] = "../outside.json"
        result = self.evaluate()
        self.assertEqual("NOT_READY", result["status"])
        self.assertIn("escapes", result["reasons"][0])

    def test_duplicate_json_keys_rejected(self):
        receipt = self.write("evolution.json", '{"schema":"a","schema":"b"}')
        result = gate.evaluate({"subject": self.subject, "model_evolution": receipt}, self.root, self.now)
        self.assertEqual("NOT_READY", result["status"])
        self.assertIn("duplicate JSON key", result["reasons"][0])

    def test_timezone_required(self):
        receipt = self.write("evolution.json", self.config)
        result = gate.evaluate({"subject": self.subject, "model_evolution": receipt}, self.root, datetime(2026, 9, 19))
        self.assertEqual("NOT_READY", result["status"])


if __name__ == "__main__":
    unittest.main()
