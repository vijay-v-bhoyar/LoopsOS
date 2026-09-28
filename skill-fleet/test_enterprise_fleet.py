import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parent))
import fleet
import test_fleet as fixtures
from test_fleet import skill


class EnterpriseFleetTests(unittest.TestCase):
    def test_discovery_preserves_policy_and_reviewed_baselines(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); package = root / "skill-packages/new-owner"; skill(package, "new-owner")
            registry_dir = root / "skill-fleet"; registry_dir.mkdir()
            original = {"schema": fleet.SCHEMA, "lifecycle_policy": {"version": "custom-preserve"}, "skills": []}
            (registry_dir / "registry.json").write_text(json.dumps(original), encoding="utf-8")
            with patch.object(Path, "home", return_value=root / "absent-home"):
                found = fleet.discover(root)
            self.assertEqual(found["lifecycle_policy"], original["lifecycle_policy"])
            self.assertEqual(found["skills"][0]["id"], "new-owner")
            self.assertTrue(found["pending_distribution_changes"])

    def test_discovery_never_blesses_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); package = root / "skill-packages/example"; skill(package)
            registry_dir = root / "skill-fleet"; registry_dir.mkdir()
            original = {"schema": fleet.SCHEMA, "lifecycle_policy": {"version": "1.0.0"}, "skills": [{"id": "example",
                "canonical": "${WORKSPACE}/skill-packages/example", "reviewed_mirror_hashes": {"mirror": "old"}, "canonical_sha256": "old"}]}
            (registry_dir / "registry.json").write_text(json.dumps(original), encoding="utf-8")
            with patch.object(Path, "home", return_value=root / "absent-home"):
                found = fleet.discover(root)
            self.assertEqual(found["skills"][0]["canonical_sha256"], "old")
            self.assertEqual(found["skills"][0]["reviewed_mirror_hashes"], {"mirror": "old"})

    def test_source_hash_drift_is_not_hidden_by_missing_mirror(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); canonical = root / "canonical"; skill(canonical)
            registry = fixtures.FleetTests().registry(root, canonical)
            payload = json.loads(registry.read_text(encoding="utf-8")); payload["skills"][0]["canonical_sha256"] = "0" * 64
            registry.write_text(json.dumps(payload), encoding="utf-8")
            self.assertTrue(any("canonical entrypoint hash drift" in e for e in fleet.validate(registry)))

    def test_invalid_utf8_and_yaml_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); canonical = root / "canonical"; skill(canonical)
            registry = fixtures.FleetTests().registry(root, canonical)
            for malformed in (b'\xff', b'---\nname: [\ndescription: broken\n---\n'):
                (canonical / "SKILL.md").write_bytes(malformed)
                self.assertTrue(fleet.validate(registry))


if __name__ == "__main__": unittest.main()
