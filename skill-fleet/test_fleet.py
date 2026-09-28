import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fleet


def skill(path: Path, name: str = "example", body: str = "# Example\n") -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(
        f"\ufeff---\nname: {name}\ndescription: Example skill\n---\n{body}", encoding="utf-8"
    )


class FleetTests(unittest.TestCase):
    def registry(self, root: Path, canonical: Path, mirrors=(), test_class="static") -> Path:
        registry = root / "registry.json"
        policy_skills = {
            "registry-admission": ["example"],
            "graph-orientation": ["example"],
            "goal-and-requirement-admission": ["example"],
            "delivery-engine-selection": ["example"],
            "specialist-and-risk-routing": ["example"],
            "recover-park-and-resume": ["example"],
            "independent-verification-and-closure": ["example"],
            "governed-release": ["example"],
            "operate-and-learn": ["example"],
            "fleet-change-quality": ["example"],
        }
        policy = {
            "version": "1.0.0",
            "artifacts": {"map": "reports/map.md", "generator": "skill-fleet/generate.py"},
            "topology": {
                "conductor": "product-lifecycle-loop",
                "delivery_engines": ["codex-product-build-loop", "product-loop", "agentic-product-loop"],
                "exactly_one_delivery_engine": True,
                "parallelizer": "loop-fleet",
                "parallelization_requires_solo_engine_proof": True,
                "assurance": "agentic-assurance-loop",
                "release_decider": "release-governor",
                "deployment_executor": "deploy-provision",
                "deployment_requires_go_and_authority": True,
            },
            "mandatory_steps": [
                {"id": step_id, "applies_when": "a lifecycle run reaches this boundary",
                 "required_skills": skills, "required_evidence": "a durable local receipt"}
                for step_id, skills in policy_skills.items()
            ],
        }
        registry.write_text(json.dumps({"schema": fleet.SCHEMA, "lifecycle_policy": policy, "skills": [{
            "id": "example", "canonical": str(canonical), "mirrors": [str(x) for x in mirrors],
            "version": "1.0.0", "owner": "test", "test": {"class": test_class}, "aliases": [],
            "reviewed_mirror_hashes": {}, "reviewed_mirror_tree_hashes": {},
        }]}), encoding="utf-8")
        return registry

    def test_bom_is_valid_utf8_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); canonical = root / "canonical"; skill(canonical)
            self.assertEqual(fleet.validate(self.registry(root, canonical)), [])

    def test_missing_link_and_mirror_drift_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); canonical = root / "canonical"; mirror = root / "mirror"
            skill(canonical, body="[missing](references/nope.md)"); skill(mirror, body="# different\n")
            errors = fleet.validate(self.registry(root, canonical, [mirror]))
            self.assertTrue(any("missing internal reference" in error for error in errors))
            self.assertTrue(any("mirror drift" in error for error in errors))

    def test_unreviewed_mirror_tree_change_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); canonical = root / "canonical"; mirror = root / "mirror"
            skill(canonical); skill(mirror)
            registry = self.registry(root, canonical, [mirror])
            payload = json.loads(registry.read_text(encoding="utf-8"))
            payload["skills"][0]["reviewed_mirror_hashes"] = {str(mirror): fleet.sha256(mirror / "SKILL.md")}
            payload["skills"][0]["reviewed_mirror_tree_hashes"] = {str(mirror): fleet.tree_sha256(mirror)}
            registry.write_text(json.dumps(payload), encoding="utf-8")
            (mirror / "unreviewed.txt").write_text("changed", encoding="utf-8")
            errors = fleet.validate(registry)
            self.assertTrue(any("mirror package hash is not the reviewed" in error for error in errors))

    def test_fixture_requires_test_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); canonical = root / "canonical"; skill(canonical)
            errors = fleet.validate(self.registry(root, canonical, test_class="fixture"))
            self.assertTrue(any("fixture class" in error for error in errors))

    def test_sync_preserves_mirror_only_files_and_backs_up_replaced_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); canonical = root / "canonical"; mirror = root / "mirror"
            skill(canonical, body="# old\n"); skill(mirror, body="# mirror\n")
            (mirror / "local-only.txt").write_text("keep", encoding="utf-8")
            registry = self.registry(root, canonical, [mirror])
            payload = json.loads(registry.read_text(encoding="utf-8"))
            payload["skills"][0]["reviewed_mirror_hashes"] = {str(mirror): fleet.sha256(mirror / "SKILL.md")}
            payload["skills"][0]["reviewed_mirror_tree_hashes"] = {str(mirror): fleet.tree_sha256(mirror)}
            registry.write_text(json.dumps(payload), encoding="utf-8")
            skill(canonical, body="# canonical\n")
            fleet.sync(registry, apply=True)
            self.assertEqual((mirror / "SKILL.md").read_bytes(), (canonical / "SKILL.md").read_bytes())
            self.assertEqual((mirror / "local-only.txt").read_text(encoding="utf-8"), "keep")
            self.assertTrue((root / "backups" / "example" / "SKILL.md").is_file())

    def test_lifecycle_policy_rejects_missing_step_and_unsafe_topology(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); canonical = root / "canonical"; skill(canonical)
            registry = self.registry(root, canonical)
            payload = json.loads(registry.read_text(encoding="utf-8"))
            policy = payload["lifecycle_policy"]
            policy["mandatory_steps"] = policy["mandatory_steps"][1:]
            policy["topology"]["exactly_one_delivery_engine"] = False
            registry.write_text(json.dumps(payload), encoding="utf-8")
            errors = fleet.validate(registry)
            self.assertTrue(any("missing lifecycle mandatory step" in error for error in errors))
            self.assertTrue(any("exactly one delivery engine" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
