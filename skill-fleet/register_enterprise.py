"""Reviewable, idempotent registry upgrade for the approved 14 enterprise packages.

Does not install files or overwrite existing reviewed mirror baselines. Run only
after inspecting the changed source and tests; registration is an explicit act.
"""
import copy
import json
from pathlib import Path
import fleet

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "skill-fleet" / "registry.json"


def register():
    original = json.loads(REGISTRY.read_text(encoding="utf-8"))
    backup = REGISTRY.parent / "history" / "registry-before-enterprise-v1.json"
    if not backup.exists():
        backup.parent.mkdir(exist_ok=True); backup.write_bytes(REGISTRY.read_bytes())
    payload = copy.deepcopy(original)
    items = {item["id"]: item for item in payload["skills"]}
    catalog = json.loads((ROOT / "skill-packages/enterprise-ai-assurance-loop/catalog/owners.json").read_text(encoding="utf-8"))
    new_ids = ["enterprise-ai-assurance-loop"] + [o["skill"] for o in catalog]
    for skill_id in new_ids:
        source = ROOT / "skill-packages" / skill_id
        item = items.setdefault(skill_id, {"id": skill_id, "mirrors": [], "version": "1.0.0",
            "owner": "enterprise-ai-assurance", "test": {"class": "fixture"}, "aliases": [],
            "reviewed_mirror_hashes": {}, "reviewed_mirror_tree_hashes": {}})
        item["canonical"] = "${WORKSPACE}/skill-packages/" + skill_id
        item["canonical_sha256"] = fleet.sha256(source / "SKILL.md")
        item["canonical_tree_sha256"] = fleet.tree_sha256(source)
        item["execution"] = {"automatic_test_scope": "synthetic-local", "side_effects": ["local-temporary-files"],
            "external_execution": "requires named target, authorized collector and organization-controlled evidence"}
    # Normalize only existing repository package paths; preserve standalone sources.
    for item in items.values():
        candidate = ROOT / "skill-packages" / item["id"]
        old = fleet.path_value(item["canonical"], REGISTRY)
        if candidate.is_dir() and old == candidate.resolve():
            item["canonical"] = "${WORKSPACE}/skill-packages/" + item["id"]
    policy = payload["lifecycle_policy"]
    conductor = items["product-lifecycle-loop"]
    conductor["version"] = "1.1.0"
    conductor["canonical_sha256"] = fleet.sha256(ROOT / "skill-packages/product-lifecycle-loop/SKILL.md")
    conductor["canonical_tree_sha256"] = fleet.tree_sha256(ROOT / "skill-packages/product-lifecycle-loop")
    policy["version"] = "1.1.0"
    policy["enterprise_assurance"] = {"skill": "enterprise-ai-assurance-loop", "required_owner_count": 13,
        "evaluator": "skill-packages/enterprise-ai-assurance-loop/scripts/assurance.py",
        "parent_completion_gate": "skill-packages/product-lifecycle-loop/scripts/progress_state.py",
        "test_evidence_cannot_prove_enterprise": True, "deployment_authority": False,
        "compatibility": "Version 1.0.0 non-enterprise runs remain readable; current revocation and security floors still apply."}
    if not any(step["id"] == "enterprise-ai-assurance" for step in policy["mandatory_steps"]):
        policy["mandatory_steps"].insert(7, {"id": "enterprise-ai-assurance",
            "applies_when": "Enterprise AI assurance is requested or required by the product risk profile, including enterprise readiness and material model/autonomy changes.",
            "required_skills": new_ids,
            "required_evidence": "One subject/profile/verifier-bound run; thirteen applicability dispositions; raw signed owner evidence; persistent known-unaddressed risks; authenticated independent challenge; scoped current decision; one delivery engine; no implicit deployment authority."})
    payload["skills"] = [items[key] for key in sorted(items)]
    REGISTRY.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {"skills": len(items), "added_enterprise_packages": len(new_ids), "policy_version": policy["version"], "registry_sha256": fleet.sha256(REGISTRY)}


if __name__ == "__main__": print(json.dumps(register(), indent=2))
