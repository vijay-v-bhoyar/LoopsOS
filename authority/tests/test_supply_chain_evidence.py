from __future__ import annotations

import hashlib
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.verify_oci_attestations import EvidenceError, verify_oci_archive


REPO_ROOT = Path(__file__).resolve().parents[2]


class SupplyChainEvidenceTests(unittest.TestCase):
    def _archive(self, root: Path, *, include_sbom: bool = True) -> Path:
        layout = root / "layout"
        blobs = layout / "blobs" / "sha256"
        blobs.mkdir(parents=True)

        def blob(value: dict[str, object]) -> str:
            content = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
            digest = hashlib.sha256(content).hexdigest()
            (blobs / digest).write_bytes(content)
            return f"sha256:{digest}"

        config_digest = blob({"architecture": "amd64", "os": "linux"})
        image_digest = blob({
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "config": {
                "mediaType": "application/vnd.oci.image.config.v1+json",
                "digest": config_digest,
                "size": 1,
            },
            "layers": [],
        })
        statements = [
            {
                "_type": "https://in-toto.io/Statement/v0.1",
                "predicateType": "https://slsa.dev/provenance/v1",
                "subject": [{"name": "pkg:docker/loopos", "digest": {"sha256": image_digest.split(":", 1)[1]}}],
                "predicate": {"buildDefinition": {}, "runDetails": {}},
            }
        ]
        if include_sbom:
            statements.append({
                "_type": "https://in-toto.io/Statement/v0.1",
                "predicateType": "https://spdx.dev/Document",
                "subject": [{"name": "pkg:docker/loopos", "digest": {"sha256": image_digest.split(":", 1)[1]}}],
                "predicate": {"spdxVersion": "SPDX-2.3", "packages": []},
            })
        layers = []
        for statement in statements:
            statement_digest = blob(statement)
            layers.append({
                "mediaType": "application/vnd.in-toto+json",
                "digest": statement_digest,
                "size": 1,
            })
        attestation_config = blob({"architecture": "unknown", "os": "unknown"})
        attestation_digest = blob({
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "config": {
                "mediaType": "application/vnd.oci.image.config.v1+json",
                "digest": attestation_config,
                "size": 1,
            },
            "layers": layers,
        })
        manifest_list = {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "manifests": [
                {
                    "mediaType": "application/vnd.oci.image.manifest.v1+json",
                    "digest": image_digest,
                    "size": 1,
                    "platform": {"architecture": "amd64", "os": "linux"},
                },
                {
                    "mediaType": "application/vnd.oci.image.manifest.v1+json",
                    "digest": attestation_digest,
                    "size": 1,
                    "platform": {"architecture": "unknown", "os": "unknown"},
                    "annotations": {
                        "vnd.docker.reference.digest": image_digest,
                        "vnd.docker.reference.type": "attestation-manifest",
                    },
                },
            ],
        }
        manifest_list_digest = blob(manifest_list)
        index = {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "manifests": [
                {
                    "mediaType": "application/vnd.oci.image.index.v1+json",
                    "digest": manifest_list_digest,
                    "size": 1,
                }
            ],
        }
        (layout / "index.json").write_text(json.dumps(index), encoding="utf-8")
        (layout / "oci-layout").write_text('{"imageLayoutVersion":"1.0.0"}', encoding="utf-8")
        archive = root / "loopos.oci.tar"
        with tarfile.open(archive, "w") as output:
            for path in layout.rglob("*"):
                if path.is_file():
                    output.add(path, arcname=path.relative_to(layout))
        return archive

    def test_verifies_embedded_sbom_and_provenance_attestations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive = self._archive(Path(temporary_directory))
            sbom_output = Path(temporary_directory) / "loopos.sbom.spdx.json"
            report = verify_oci_archive(archive, sbom_output=sbom_output)
            sbom = json.loads(sbom_output.read_text(encoding="utf-8"))

        self.assertTrue(report["verified"])
        self.assertTrue(report["image_digest"].startswith("sha256:"))
        self.assertTrue(report["config_digest"].startswith("sha256:"))
        self.assertEqual(report["sbom_file"], "loopos.sbom.spdx.json")
        self.assertEqual(sbom["spdxVersion"], "SPDX-2.3")
        self.assertEqual(report["sbom_predicate"], "https://spdx.dev/Document")
        self.assertEqual(report["provenance_predicate"], "https://slsa.dev/provenance/v1")
        self.assertEqual(len(report["archive_sha256"]), 64)

    def test_rejects_an_oci_archive_without_an_sbom(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive = self._archive(Path(temporary_directory), include_sbom=False)

            with self.assertRaisesRegex(EvidenceError, "SBOM"):
                verify_oci_archive(archive)

    def test_ci_builds_and_retains_attested_oci_archives(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "loopos-ui.yml").read_text(encoding="utf-8")

        self.assertIn("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", workflow)
        self.assertIn("actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97", workflow)
        self.assertIn("actions/setup-node@820762786026740c76f36085b0efc47a31fe5020", workflow)
        self.assertIn("docker/setup-buildx-action@4d04d5d9486b7bd6fa91e7baf45bbb4f8b9deedd", workflow)
        self.assertGreaterEqual(workflow.count("--provenance=mode=max"), 2)
        self.assertGreaterEqual(workflow.count("--sbom=true"), 2)
        self.assertIn("type=oci,dest=.release-evidence/loopos-ui.oci.tar", workflow)
        self.assertIn("type=oci,dest=.release-evidence/loopos-authority.oci.tar", workflow)
        self.assertIn("scripts/verify_oci_attestations.py", workflow)
        self.assertEqual(workflow.count("anchore/scan-action@e1165082ffb1fe366ebaf02d8526e7c4989ea9d2"), 2)
        self.assertEqual(workflow.count("sbom: .release-evidence/"), 2)
        self.assertNotIn("image: oci-archive:", workflow)
        self.assertEqual(workflow.count("severity-cutoff: high"), 2)
        self.assertIn(".release-evidence/loopos-ui.vulnerabilities.json", workflow)
        self.assertIn(".release-evidence/loopos-authority.vulnerabilities.json", workflow)
        self.assertIn("actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a", workflow)
        self.assertIn("if: always()", workflow)
        self.assertIn("include-hidden-files: true", workflow)
        self.assertIn("vex: security/authority-python-3.14.6.openvex.json", workflow)
        self.assertIn("cp security/authority-python-3.14.6.openvex.json .release-evidence/", workflow)

    def test_authority_vex_is_narrow_and_fixed_by_the_pinned_runtime(self) -> None:
        vex = json.loads(
            (REPO_ROOT / "security" / "authority-python-3.14.6.openvex.json").read_text(encoding="utf-8")
        )
        statements = vex["statements"]

        self.assertEqual(
            {statement["vulnerability"]["name"] for statement in statements},
            {"CVE-2026-11940", "CVE-2026-11972", "CVE-2026-15308"},
        )
        self.assertTrue(all(statement["status"] == "fixed" for statement in statements))
        self.assertTrue(
            all(
                statement["products"] == [{"@id": "pkg:generic/python@3.14.6"}]
                for statement in statements
            )
        )

    def test_ui_runtime_base_is_current_and_digest_pinned(self) -> None:
        dockerfile = (REPO_ROOT / "ui" / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn(
            "nginxinc/nginx-unprivileged:1.31.3-alpine3.24-slim"
            "@sha256:22f839c5fb4007dc24d203a170a9e03fc185d660bfefc34ac6823a7aef085cbc",
            dockerfile,
        )
        self.assertNotIn("nginx-unprivileged:1.27", dockerfile)

    def test_authority_runtime_base_is_current_and_digest_pinned(self) -> None:
        dockerfile = (REPO_ROOT / "authority" / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn(
            "python:3.14.6-alpine3.24"
            "@sha256:26730869004e2b9c4b9ad09cab8625e81d256d1ce97e72df5520e806b1709f92",
            dockerfile,
        )
        self.assertIn("apk upgrade --no-cache", dockerfile)
        self.assertIn("python -c \"import fastapi, httpx, jwt, psycopg", dockerfile)
        self.assertNotIn("python:3.12-slim", dockerfile)


if __name__ == "__main__":
    unittest.main()
