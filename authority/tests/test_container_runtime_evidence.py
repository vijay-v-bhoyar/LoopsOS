from __future__ import annotations

import json
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.verify_container_runtime import verify_runtime


REPO_ROOT = Path(__file__).resolve().parents[2]


class ContainerRuntimeEvidenceTests(unittest.TestCase):
    def test_ci_loads_and_exercises_both_release_images(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "loopos-ui.yml").read_text(encoding="utf-8")

        self.assertGreaterEqual(workflow.count("--load"), 2)
        self.assertIn("scripts/verify_container_runtime.py", workflow)
        self.assertIn(".release-evidence/container-runtime-smoke.json", workflow)

    def test_runtime_verifier_enforces_hardened_container_boundaries(self) -> None:
        verifier = (REPO_ROOT / "scripts" / "verify_container_runtime.py").read_text(encoding="utf-8")

        for required_flag in [
            "--read-only",
            "--security-opt",
            "no-new-privileges",
            "--cap-drop",
            "ALL",
            "--tmpfs",
        ]:
            self.assertIn(required_flag, verifier)
        self.assertIn("runtime_uid", verifier)
        self.assertIn("/api/health/live", verifier)
        self.assertIn("/api/health/ready", verifier)
        self.assertIn("content-security-policy", verifier)
        self.assertIn("x-content-type-options", verifier)
        self.assertIn("finally:", verifier)
        self.assertIn("docker\", \"rm\", \"--force", verifier)

    def test_missing_docker_emits_a_fail_closed_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "runtime.json"
            with patch(
                "scripts.verify_container_runtime.subprocess.run",
                side_effect=FileNotFoundError("docker is unavailable"),
            ), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = verify_runtime("loopos-ui:test", "loopos-authority:test", output)
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(result, 1)
        self.assertFalse(report["verified"])
        self.assertIn("could not be executed", report["error"])


if __name__ == "__main__":
    unittest.main()
