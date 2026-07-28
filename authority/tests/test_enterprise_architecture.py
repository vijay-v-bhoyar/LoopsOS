from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


class EnterpriseArchitectureContractTests(unittest.TestCase):
    def load_descriptor(self, filename: str) -> dict:
        return yaml.safe_load((REPO_ROOT / "runtime" / "loop-descriptors" / filename).read_text(encoding="utf-8"))

    def test_loop_descriptor_schema_requires_enterprise_runtime_fields(self) -> None:
        schema = json.loads((REPO_ROOT / "schemas" / "loop-descriptor.schema.json").read_text(encoding="utf-8"))
        required = set(schema["required"])

        for field in [
            "runtime_layers",
            "tool_policy",
            "sandbox",
            "egress",
            "identity",
            "secrets",
            "observability",
            "durability",
            "recovery",
            "kill_switch",
        ]:
            self.assertIn(field, required)

    def test_representative_descriptors_declare_enterprise_runtime_contracts(self) -> None:
        for filename in [
            "001-product-discovery-loop.yaml",
            "036-release-readiness-loop.yaml",
            "069-tool-execution-validation-loop.yaml",
            "097-catastrophic-failure-and-containment-loop.yaml",
        ]:
            descriptor = self.load_descriptor(filename)
            self.assertEqual(descriptor["runtime_layers"]["durable_execution"], "restate_default_temporal_compatible")
            self.assertTrue(descriptor["tool_policy"]["policy_decision_ref_required"])
            self.assertEqual(descriptor["sandbox"]["filesystem"], "read_only_default")
            self.assertTrue(descriptor["sandbox"]["metadata_endpoint_blocked"])
            self.assertEqual(descriptor["egress"]["default_policy"], "deny")
            self.assertTrue(descriptor["egress"]["private_network_block"])
            self.assertEqual(descriptor["identity"]["authorization_model"], "RBAC_ABAC")
            self.assertEqual(descriptor["secrets"]["source"], "KMS")
            self.assertTrue(descriptor["observability"]["redaction_proof_required"])
            self.assertTrue(descriptor["durability"]["retry_budget"]["reconciliation_before_retry"])
            self.assertTrue(descriptor["recovery"]["compensation_required_for_external_effect"])
            self.assertIn("global", descriptor["kill_switch"]["scopes"])

    def test_high_risk_agent_and_governance_loops_use_stronger_sandbox_profile(self) -> None:
        for filename in [
            "066-agent-goal-achievement-loop.yaml",
            "073-agent-state-consistency-and-idempotency-loop.yaml",
            "080-agent-identity-and-credential-governance-loop.yaml",
            "089-audit-logging-and-forensic-readiness-loop.yaml",
            "100-human-oversight-approval-and-calibration-loop.yaml",
            "104-compliance-evidence-loop.yaml",
        ]:
            descriptor = self.load_descriptor(filename)
            self.assertEqual(descriptor["sandbox"]["profile_ref"], "sandbox-e2b-firecracker-production")
            self.assertIn("security_privileged", descriptor["tool_policy"]["allowed_action_classes"])

    def test_architecture_stack_declares_all_deployment_profiles(self) -> None:
        stack = yaml.safe_load((REPO_ROOT / "runtime" / "architecture_stack.yaml").read_text(encoding="utf-8"))
        profiles = stack["required_layers"]["cloud_deployment_profiles"]

        self.assertIn("local_dev", profiles)
        self.assertIn("azure_governed", profiles)
        self.assertIn("aws_infrastructure", profiles)
        self.assertIn("gcp_native", profiles)
        self.assertEqual(stack["required_layers"]["durable_execution"]["recommended_default"], "Restate")
        self.assertEqual(stack["required_layers"]["durable_execution"]["enterprise_history_option"], "Temporal")

    def test_control_coverage_schema_and_profiles_support_sparse_statuses(self) -> None:
        schema = json.loads((REPO_ROOT / "schemas" / "control-coverage.schema.json").read_text(encoding="utf-8"))
        self.assertIn("control_mappings", schema["required"])
        statuses = set(schema["properties"]["control_mappings"]["items"]["properties"]["status"]["enum"])
        self.assertEqual(statuses, {"applicable", "conditional", "delegated", "not_applicable", "blocked_until_proven"})

        applicability = yaml.safe_load((REPO_ROOT / "runtime" / "control-applicability.yaml").read_text(encoding="utf-8"))
        first_profile = applicability["profiles"][0]
        self.assertIn("control_mappings", first_profile)
        self.assertEqual({item["status"] for item in first_profile["control_mappings"]}, statuses)


if __name__ == "__main__":
    unittest.main()
