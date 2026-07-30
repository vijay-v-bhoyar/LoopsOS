from __future__ import annotations

import json
import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import scripts.verify_container_runtime as runtime_verifier
from scripts.verify_container_runtime import verify_runtime


REPO_ROOT = Path(__file__).resolve().parents[2]


class ContainerRuntimeEvidenceTests(unittest.TestCase):
    def test_ci_loads_and_exercises_both_release_images(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "loopos-ui.yml").read_text(encoding="utf-8")

        self.assertGreaterEqual(workflow.count("--load"), 2)
        self.assertIn("scripts/verify_container_runtime.py", workflow)
        self.assertIn("--oci-manifest .release-evidence/manifest.json", workflow)
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
        self.assertIn("release_config_digest", verifier)
        self.assertIn("authority_release_identity", verifier)
        self.assertIn("ui_release_identity", verifier)
        self.assertIn("/api/health/live", verifier)
        self.assertIn("/api/health/ready", verifier)
        self.assertIn("content-security-policy", verifier)
        self.assertIn("x-content-type-options", verifier)
        self.assertIn("finally:", verifier)
        self.assertIn("docker\", \"rm\", \"--force", verifier)

    def test_authority_tmpfs_uses_the_image_numeric_identity(self) -> None:
        resolve_identity = getattr(runtime_verifier, "_image_uid_gid", None)
        self.assertIsNotNone(resolve_identity)
        if resolve_identity is None:
            return

        with patch(
            "scripts.verify_container_runtime._run",
            return_value=subprocess.CompletedProcess([], 0, "101\n102\n", ""),
        ) as run:
            uid, gid = resolve_identity("loopos-authority:test")

        self.assertEqual((uid, gid), (101, 102))
        run.assert_called_once_with([
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "sh",
            "loopos-authority:test",
            "-c",
            "id -u; id -g",
        ])

        verifier = (REPO_ROOT / "scripts" / "verify_container_runtime.py").read_text(encoding="utf-8")
        self.assertIn("uid={authority_uid},gid={authority_gid},mode=0700", verifier)

    def test_internal_network_is_probed_without_publishing_a_host_port(self) -> None:
        resolve_address = getattr(runtime_verifier, "_container_address", None)
        self.assertIsNotNone(resolve_address)
        if resolve_address is None:
            return

        inspection = {
            "NetworkSettings": {
                "Networks": {
                    "loopos-smoke-test": {
                        "IPAddress": "172.18.0.3",
                    },
                },
            },
        }
        self.assertEqual(resolve_address(inspection, "loopos-smoke-test"), "172.18.0.3")

        verifier = (REPO_ROOT / "scripts" / "verify_container_runtime.py").read_text(encoding="utf-8")
        self.assertNotIn("\"--publish\"", verifier)
        self.assertIn('base_url = f"http://{ui_address}:8080"', verifier)

    def test_missing_docker_emits_a_fail_closed_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "runtime.json"
            manifest = Path(temporary_directory) / "manifest.json"
            manifest.write_text(
                json.dumps({
                    "verified": True,
                    "artifacts": [
                        {"archive": "loopos-ui.oci.tar", "config_digest": f"sha256:{'1' * 64}"},
                        {"archive": "loopos-authority.oci.tar", "config_digest": f"sha256:{'2' * 64}"},
                    ],
                }),
                encoding="utf-8",
            )
            with patch(
                "scripts.verify_container_runtime.subprocess.run",
                side_effect=FileNotFoundError("docker is unavailable"),
            ), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = verify_runtime("loopos-ui:test", "loopos-authority:test", manifest, output)
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(result, 1)
        self.assertFalse(report["verified"])
        self.assertIn("could not be executed", report["error"])


if __name__ == "__main__":
    unittest.main()
