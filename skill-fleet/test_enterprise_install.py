import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import fleet
import install_enterprise as installer


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "skill-packages/enterprise-test"
        self.source.mkdir(parents=True)
        (self.source / "SKILL.md").write_text("new", encoding="utf-8")
        self.target = self.root / ".codex/skills/enterprise-test"
        self.target.mkdir(parents=True)
        (self.target / "SKILL.md").write_text("old", encoding="utf-8")
        (self.target / "local-note.txt").write_text("preserve", encoding="utf-8")
        self.registry = self.root / "skill-fleet/registry.json"
        self.registry.parent.mkdir()
        self.registry.write_text(json.dumps({"skills": [{"id": "enterprise-test", "mirrors": [],
            "reviewed_mirror_hashes": {}, "reviewed_mirror_tree_hashes": {}}]}), encoding="utf-8")
        self.manifest = self.root / "manifest.json"
        self.payload = {"registry_sha256": fleet.sha256(self.registry), "entries": [{
            "id": "enterprise-test", "source": str(self.source), "target": str(self.target),
            "source_tree_sha256": fleet.tree_sha256(self.source), "before_tree_sha256": fleet.tree_sha256(self.target)}]}
        self.manifest.write_text(json.dumps(self.payload), encoding="utf-8")
        self.sha = fleet.sha256(self.manifest)
        for name, value in (("ROOT", self.root), ("REGISTRY", self.registry)):
            patcher = patch.object(installer, name, value); patcher.start(); self.addCleanup(patcher.stop)
        for patcher in (patch.object(installer, "ids", return_value=["enterprise-test"]), patch.object(Path, "home", return_value=self.root)):
            patcher.start(); self.addCleanup(patcher.stop)

    def test_install_preserves_local_files_and_records_reviewed_hashes(self):
        result = installer.apply(self.manifest, self.sha)
        self.assertEqual(result["status"], "INSTALLED")
        self.assertEqual((self.target / "SKILL.md").read_text(), "new")
        self.assertEqual((self.target / "local-note.txt").read_text(), "preserve")
        record = json.loads(self.registry.read_text())["skills"][0]
        self.assertEqual(record["reviewed_mirror_tree_hashes"][str(self.target)], fleet.tree_sha256(self.target))

    def test_installed_drift_blocks_before_mutation(self):
        (self.target / "local-note.txt").write_text("edited", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Destination changed"):
            installer.apply(self.manifest, self.sha)
        self.assertEqual((self.target / "SKILL.md").read_text(), "old")

    def test_source_drift_blocks_before_mutation(self):
        (self.source / "SKILL.md").write_text("unreviewed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Source changed"):
            installer.apply(self.manifest, self.sha)

    def test_registry_change_blocks_stale_manifest(self):
        self.registry.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "registry changed"):
            installer.apply(self.manifest, self.sha)

    def test_failed_stage_swap_restores_original(self):
        original_replace = installer.os.replace
        def fail_stage(src, dst):
            if ".stage-" in str(src): raise OSError("injected rename failure")
            return original_replace(src, dst)
        before = self.registry.read_bytes()
        with patch.object(installer.os, "replace", side_effect=fail_stage):
            with self.assertRaisesRegex(OSError, "injected"):
                installer.apply(self.manifest, self.sha)
        self.assertEqual((self.target / "SKILL.md").read_text(), "old")
        self.assertEqual(self.registry.read_bytes(), before)


if __name__ == "__main__": unittest.main()
