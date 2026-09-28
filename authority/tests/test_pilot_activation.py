from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
import shutil

import yaml

from scripts.verify_pilot_activation import MAX_PILOT_LOOPS, main, pilot_activation_report


class PilotActivationVerifierTests(unittest.TestCase):
    def test_cli_writes_a_non_secret_report_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "pilot-report.json"
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(["--playbook-id", "", "--output", str(output)])

            self.assertEqual(exit_code, 1)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["verdict"], "NO_GO")
            self.assertEqual(report["playbook_id"], "")

    def test_missing_playbook_fails_closed(self) -> None:
        report = pilot_activation_report("")

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertIn("Select one real pilot", report["failures"][0])
        self.assertEqual(len(report["available_playbooks"]), 6)
        self.assertEqual(report["available_playbooks"][0]["playbook_id"], "pilot-sdlc-governance-os")
        self.assertEqual(report["available_playbooks"][0]["loop_count"], 11)

    def test_duplicate_registry_ids_fail_closed(self) -> None:
        registries = (
            ("runtime/pilot_playbooks.yaml", "playbooks"),
            ("runtime/loops.catalog.yaml", "loops"),
            ("owners/OWNER_REGISTRY.yaml", "owners"),
            ("evidence/EVIDENCE_LOCATION_REGISTRY.yaml", "locations"),
            ("runtime/metric_packs.yaml", "metric_packs"),
            ("evals/GOLDEN_TASKS.yaml", "golden_tasks"),
            ("probes/PROBE_REGISTRY.yaml", "probes"),
        )
        for relative_path, key in registries:
            with self.subTest(registry=relative_path):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    _write_bound_activation_inputs(root)
                    document = yaml.safe_load((root / relative_path).read_text(encoding="utf-8"))
                    document[key].append(dict(document[key][0]))
                    _write_yaml(root / relative_path, document)

                    report = pilot_activation_report("pilot-demo", root)

                self.assertEqual(report["verdict"], "NO_GO")
                failed_checks = {check["name"] for check in report["checks"] if not check["passed"]}
                self.assertIn("activation_registries_have_unique_ids", failed_checks)
                self.assertTrue(any(relative_path in failure for failure in report["failures"]))

    def test_current_first_playbook_reports_unresolved_activation_inputs(self) -> None:
        report = pilot_activation_report("pilot-sdlc-governance-os")

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertIn("selected_loops_have_named_owners", {check["name"] for check in report["checks"] if not check["passed"]})
        self.assertIn("selected_loops_have_authoritative_evidence", {check["name"] for check in report["checks"] if not check["passed"]})
        self.assertIn("selected_loops_have_metric_targets", {check["name"] for check in report["checks"] if not check["passed"]})
        self.assertIn("selected_loops_have_real_golden_fixtures", {check["name"] for check in report["checks"] if not check["passed"]})
        self.assertEqual(report["activation_contract"]["owner_registry"]["path"], "owners/OWNER_REGISTRY.yaml")
        self.assertEqual(report["activation_contract"]["evidence_registry"]["path"], "evidence/EVIDENCE_LOCATION_REGISTRY.yaml")
        self.assertEqual(len(report["selected_loop_requirements"]), 11)
        requirements = {item["loop_id"]: item for item in report["selected_loop_requirements"]}
        self.assertEqual(requirements["loop-006-requirements-quality-loop"]["descriptor_status"], "DRAFT")
        self.assertIn("policy_owner", requirements["loop-006-requirements-quality-loop"]["missing_owner_fields"])
        self.assertIn("target_value", requirements["loop-006-requirements-quality-loop"]["missing_metric_fields"])

    def test_malformed_loop_id_fails_closed(self) -> None:
        source_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative_path in (
                "runtime/loops.catalog.yaml",
                "owners/OWNER_REGISTRY.yaml",
                "evidence/EVIDENCE_LOCATION_REGISTRY.yaml",
                "runtime/metric_packs.yaml",
                "evals/GOLDEN_TASKS.yaml",
                "probes/PROBE_REGISTRY.yaml",
            ):
                destination = root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_root / relative_path, destination)
            _write_yaml(
                root / "runtime/pilot_playbooks.yaml",
                {"playbooks": [{"playbook_id": "pilot-malformed", "loops": [{"loop_id": "not-a-string"}]}]},
            )

            report = pilot_activation_report("pilot-malformed", root)

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertTrue(any("non-string loop ID" in failure for failure in report["failures"]))

    def test_descriptor_identity_must_match_selected_loop(self) -> None:
        source_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative_path in (
                "owners/OWNER_REGISTRY.yaml",
                "evidence/EVIDENCE_LOCATION_REGISTRY.yaml",
                "runtime/metric_packs.yaml",
                "evals/GOLDEN_TASKS.yaml",
                "probes/PROBE_REGISTRY.yaml",
            ):
                destination = root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_root / relative_path, destination)
            _write_yaml(
                root / "runtime/pilot_playbooks.yaml",
                {"playbooks": [{"playbook_id": "pilot-mismatch", "loops": ["loop-selected"]}]},
            )
            _write_yaml(
                root / "runtime/loops.catalog.yaml",
                {
                    "loops": [
                        {
                            "loop_id": "loop-selected",
                            "descriptor_path": "runtime/loop-descriptors/mismatch.yaml",
                        }
                    ]
                },
            )
            _write_yaml(
                root / "runtime/loop-descriptors/mismatch.yaml",
                {
                    "loop_id": "loop-other",
                    "status": "PILOT",
                    "authority": {"policy_owner_ref": "owner-category-01"},
                    "evidence": {"primary_location_ref": "evidence-category-01"},
                },
            )

            report = pilot_activation_report("pilot-mismatch", root)

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertTrue(any("descriptor loop_id is loop-other" in failure for failure in report["failures"]))

    def test_bound_fixture_can_reach_go(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "runtime/loop-descriptors").mkdir(parents=True)
            (root / "owners").mkdir()
            (root / "evidence").mkdir()
            (root / "evals").mkdir()
            (root / "probes").mkdir()

            _write_yaml(
                root / "runtime/pilot_playbooks.yaml",
                {
                    "playbooks": [
                        {
                            "playbook_id": "pilot-demo",
                            "pilot_scope": "one bounded test scope",
                            "loops": ["loop-001-demo"],
                        }
                    ]
                },
            )
            _write_yaml(root / "runtime/loops.catalog.yaml", {"loops": [{"loop_id": "loop-001-demo", "descriptor_path": "runtime/loop-descriptors/demo.yaml"}]})
            _write_yaml(
                root / "runtime/loop-descriptors/demo.yaml",
                {
                    "loop_id": "loop-001-demo",
                    "status": "PILOT",
                    "authority": {"policy_owner_ref": "owner-category-01"},
                    "evidence": {"primary_location_ref": "evidence-category-01"},
                },
            )
            _write_yaml(
                root / "owners/OWNER_REGISTRY.yaml",
                {
                    "owners": [
                        {
                            "owner_ref": "owner-category-01",
                            "status": "PILOT",
                            **{field: f"named-{field}" for field in ("policy_owner", "gate_owner", "risk_owner", "executor_owner", "validator_owner", "backup_owner")},
                        }
                    ]
                },
            )
            _write_yaml(
                root / "evidence/EVIDENCE_LOCATION_REGISTRY.yaml",
                {
                    "locations": [
                        {
                            "evidence_ref": "evidence-category-01",
                            "status": "PILOT",
                            "authoritative_location": "https://evidence.example/loop-001",
                            "freshness_policy": "freshness-R1",
                            "retention_policy": "retention-R1",
                        }
                    ]
                },
            )
            _write_yaml(
                root / "runtime/metric_packs.yaml",
                {
                    "metric_packs": [
                        {
                            "loop_id": "loop-001-demo",
                            "primary_metric": {"target_value": 0.9, "observation_window": "window-R1"},
                        }
                    ]
                },
            )
            _write_yaml(
                root / "evals/GOLDEN_TASKS.yaml",
                {
                    "golden_tasks": [
                        {
                            "loop_id": "loop-001-demo",
                            "fixture_ref": "fixtures/demo.json",
                            "tasks": [{"task_id": "demo", "fixture_ref": "fixtures/demo.json"}],
                        }
                    ]
                },
            )
            _write_yaml(
                root / "probes/PROBE_REGISTRY.yaml",
                {"probes": [{"probe_id": "demo-probe", "loop_ids": ["loop-001-demo"], "adapter": "scripts/demo_probe.py"}]},
            )
            (root / "fixtures/demo.json").parent.mkdir(parents=True, exist_ok=True)
            (root / "fixtures/demo.json").write_text(
                '{"fixture_kind": "approved_golden_fixture", "approval_ref": "test-approval", "case": "demo"}\n',
                encoding="utf-8",
            )
            (root / "scripts/demo_probe.py").parent.mkdir(parents=True, exist_ok=True)
            (root / "scripts/demo_probe.py").write_text("def run():\n    return True\n", encoding="utf-8")

            report = pilot_activation_report("pilot-demo", root)

        self.assertEqual(report["verdict"], "GO")
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["selected_loop_requirements"][0]["missing_owner_fields"], [])
        self.assertEqual(report["selected_loop_requirements"][0]["missing_evidence_fields"], [])
        self.assertEqual(report["selected_loop_requirements"][0]["missing_metric_fields"], [])

    def test_fixture_reference_must_resolve_to_repo_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_bound_activation_inputs(root, fixture_ref="fixtures/missing.json")

            report = pilot_activation_report("pilot-demo", root)

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertTrue(any("fixture_ref must resolve to a repository file" in failure for failure in report["failures"]))

    def test_bounded_contract_fixture_does_not_count_as_real_golden_fixture(self) -> None:
        report = pilot_activation_report("pilot-sdlc-governance-os")

        real_fixture_check = next(
            check for check in report["checks"] if check["name"] == "selected_loops_have_real_golden_fixtures"
        )
        bound_fixture_check = next(
            check for check in report["checks"] if check["name"] == "selected_loops_have_fixture_bound_golden_tasks"
        )

        self.assertFalse(real_fixture_check["passed"])
        self.assertTrue(bound_fixture_check["passed"])
        self.assertIn("approved_golden_fixture", real_fixture_check["detail"])

    def test_fixture_reference_cannot_escape_repo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_bound_activation_inputs(root, fixture_ref="../outside.json")

            report = pilot_activation_report("pilot-demo", root)

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertTrue(any("fixture_ref must resolve to a repository file" in failure for failure in report["failures"]))

    def test_probe_adapter_must_resolve_to_repo_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_bound_activation_inputs(root, adapter="../outside_probe.py")

            report = pilot_activation_report("pilot-demo", root)

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertTrue(any("adapter must resolve to a repository file" in failure for failure in report["failures"]))

    def test_probe_adapter_requires_run_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_bound_activation_inputs(root)
            (root / "scripts/demo_probe.py").write_text("PLACEHOLDER = True\n", encoding="utf-8")

            report = pilot_activation_report("pilot-demo", root)

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertTrue(any("adapter must define a top-level run" in failure for failure in report["failures"]))

    def test_evidence_location_must_be_safe_https_without_credentials_or_query(self) -> None:
        for location in (
            "http://evidence.example/loop-001",
            "https://localhost/loop-001",
            "https://localhost./loop-001",
            "https://service.localhost/loop-001",
            "https://127.0.0.1/loop-001",
            "https://user:password@evidence.example/loop-001",
            "https://evidence.example/loop-001?token=secret",
        ):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _write_bound_activation_inputs(root, authoritative_location=location)

                report = pilot_activation_report("pilot-demo", root)

            self.assertEqual(report["verdict"], "NO_GO")
            self.assertTrue(any("safe HTTPS URL" in failure for failure in report["failures"]))

    def test_metric_target_requires_numeric_rate_and_observation_window(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_bound_activation_inputs(root, target_value="TBD", observation_window="")

            report = pilot_activation_report("pilot-demo", root)

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertTrue(any("finite numeric rate" in failure for failure in report["failures"]))
        self.assertTrue(any("observation window is not assigned" in failure for failure in report["failures"]))

    def test_malformed_golden_tasks_fail_closed_with_structured_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_bound_activation_inputs(root)
            golden = yaml.safe_load((root / "evals/GOLDEN_TASKS.yaml").read_text(encoding="utf-8"))
            golden["golden_tasks"][0]["tasks"] = {"fixture_ref": "fixtures/demo.json"}
            _write_yaml(root / "evals/GOLDEN_TASKS.yaml", golden)

            report = pilot_activation_report("pilot-demo", root)

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertTrue(any("non-empty tasks list" in failure for failure in report["failures"]))

    def test_pilot_scope_requires_declaration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_bound_activation_inputs(root)
            playbooks = yaml.safe_load((root / "runtime/pilot_playbooks.yaml").read_text(encoding="utf-8"))
            playbooks["playbooks"][0].pop("pilot_scope")
            _write_yaml(root / "runtime/pilot_playbooks.yaml", playbooks)

            report = pilot_activation_report("pilot-demo", root)

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertTrue(any("bounded pilot_scope" in failure for failure in report["failures"]))

    def test_pilot_scope_rejects_duplicate_loop_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_bound_activation_inputs(root)
            _write_yaml(
                root / "runtime/pilot_playbooks.yaml",
                {
                    "playbooks": [
                        {
                            "playbook_id": "pilot-demo",
                            "pilot_scope": "one bounded test scope",
                            "loops": ["loop-001-demo", "loop-001-demo"],
                        }
                    ]
                },
            )

            report = pilot_activation_report("pilot-demo", root)

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertTrue(any("repeats loop ID" in failure for failure in report["failures"]))

    def test_pilot_scope_rejects_more_than_bounded_loop_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_bound_activation_inputs(root)
            playbooks = yaml.safe_load((root / "runtime/pilot_playbooks.yaml").read_text(encoding="utf-8"))
            playbooks["playbooks"][0]["loops"] = [f"loop-{index}" for index in range(MAX_PILOT_LOOPS + 1)]
            _write_yaml(root / "runtime/pilot_playbooks.yaml", playbooks)

            report = pilot_activation_report("pilot-demo", root)

        self.assertEqual(report["verdict"], "NO_GO")
        self.assertTrue(any("maximum bounded pilot size" in failure for failure in report["failures"]))


def _write_yaml(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def _write_bound_activation_inputs(
    root: Path,
    fixture_ref: str = "fixtures/demo.json",
    adapter: str = "scripts/demo_probe.py",
    authoritative_location: str = "https://evidence.example/loop-001",
    target_value: object = 0.9,
    observation_window: str = "window-R1",
) -> None:
    root.joinpath("runtime/loop-descriptors").mkdir(parents=True)
    for relative_path in ("owners", "evidence", "evals", "probes"):
        root.joinpath(relative_path).mkdir()
    _write_yaml(
        root / "runtime/pilot_playbooks.yaml",
        {
            "playbooks": [
                {
                    "playbook_id": "pilot-demo",
                    "pilot_scope": "one bounded test scope",
                    "loops": ["loop-001-demo"],
                }
            ]
        },
    )
    _write_yaml(root / "runtime/loops.catalog.yaml", {"loops": [{"loop_id": "loop-001-demo", "descriptor_path": "runtime/loop-descriptors/demo.yaml"}]})
    _write_yaml(
        root / "runtime/loop-descriptors/demo.yaml",
        {
            "loop_id": "loop-001-demo",
            "status": "PILOT",
            "authority": {"policy_owner_ref": "owner-category-01"},
            "evidence": {"primary_location_ref": "evidence-category-01"},
        },
    )
    _write_yaml(
        root / "owners/OWNER_REGISTRY.yaml",
        {
            "owners": [
                {
                    "owner_ref": "owner-category-01",
                    "status": "PILOT",
                    **{field: f"named-{field}" for field in ("policy_owner", "gate_owner", "risk_owner", "executor_owner", "validator_owner", "backup_owner")},
                }
            ]
        },
    )
    _write_yaml(
        root / "evidence/EVIDENCE_LOCATION_REGISTRY.yaml",
        {
            "locations": [
                {
                    "evidence_ref": "evidence-category-01",
                    "status": "PILOT",
                    "authoritative_location": authoritative_location,
                    "freshness_policy": "freshness-R1",
                    "retention_policy": "retention-R1",
                }
            ]
        },
    )
    _write_yaml(
        root / "runtime/metric_packs.yaml",
        {
            "metric_packs": [
                {
                    "loop_id": "loop-001-demo",
                    "primary_metric": {"target_value": target_value, "observation_window": observation_window},
                }
            ]
        },
    )
    _write_yaml(
        root / "evals/GOLDEN_TASKS.yaml",
        {"golden_tasks": [{"loop_id": "loop-001-demo", "fixture_ref": fixture_ref, "tasks": [{"task_id": "demo", "fixture_ref": fixture_ref}]}]},
    )
    _write_yaml(root / "probes/PROBE_REGISTRY.yaml", {"probes": [{"probe_id": "demo-probe", "loop_ids": ["loop-001-demo"], "adapter": adapter}]})
    root.joinpath("fixtures").mkdir()
    root.joinpath("fixtures/demo.json").write_text('{"case": "demo"}\n', encoding="utf-8")
    root.joinpath("scripts").mkdir()
    root.joinpath("scripts/demo_probe.py").write_text("def run():\n    return True\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
