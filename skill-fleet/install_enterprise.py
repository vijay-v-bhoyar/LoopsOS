"""Prepare and apply a digest-pinned distribution of the approved enterprise skills.

Preflight every source and destination before writing. Each package is staged,
verified and renamed into place; an unsuccessful batch restores original trees.
Only the 14 enterprise packages and existing lifecycle mirrors are in scope.
No deletion, network, provider or release operations occur.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import uuid

import fleet

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "skill-fleet/registry.json"


def ids():
    owners = json.loads((ROOT / "skill-packages/enterprise-ai-assurance-loop/catalog/owners.json").read_text(encoding="utf-8"))
    return ["enterprise-ai-assurance-loop"] + [o["skill"] for o in owners]


def safe_tree(path):
    if path.is_symlink() or path.is_junction():
        raise ValueError(f"Linked package forbidden: {path}")
    for child in path.rglob("*"):
        if child.is_symlink() or child.is_junction():
            raise ValueError(f"Linked package asset forbidden: {child}")


def prepare(path):
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {r["id"]: r for r in registry["skills"]}
    entries = []
    for skill_id in ids() + ["product-lifecycle-loop"]:
        record = records[skill_id]
        source = fleet.path_value(record["canonical"], REGISTRY)
        safe_tree(source)
        source_hash = fleet.tree_sha256(source)
        if record.get("canonical_tree_sha256", source_hash) != source_hash:
            raise ValueError(f"Unregistered source drift: {skill_id}")
        targets = record["mirrors"] if skill_id == "product-lifecycle-loop" else [
            str(Path.home() / root / "skills" / skill_id) for root in (".codex", ".agents")]
        for value in targets:
            target = Path(value).resolve()
            safe_tree(target)
            before = fleet.tree_sha256(target) if target.exists() else None
            reviewed = record.get("reviewed_mirror_tree_hashes", {}).get(str(target))
            if before is not None and before != reviewed:
                raise ValueError(f"Unreviewed installed tree: {target}")
            if str(target) in record["mirrors"] and not fleet.source_file_drift(source, target):
                continue
            entries.append({"id": skill_id, "source": str(source), "target": str(target),
                            "source_tree_sha256": source_hash, "before_tree_sha256": before})
    manifest = {"schema": "enterprise-distribution/v1", "registry_sha256": fleet.sha256(REGISTRY), "entries": entries}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"manifest": str(path), "sha256": fleet.sha256(path), "targets": len(entries)}


def preflight(manifest, expected_sha, manifest_path):
    if fleet.sha256(manifest_path) != expected_sha or manifest["registry_sha256"] != fleet.sha256(REGISTRY):
        raise ValueError("Manifest or registry changed after review")
    approved_ids = set(ids()) | {"product-lifecycle-loop"}
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {r["id"]: r for r in registry["skills"]}
    seen = set()
    for entry in manifest["entries"]:
        skill_id = entry["id"]
        if skill_id not in approved_ids:
            raise ValueError("Out of scope skill")
        source, target = Path(entry["source"]), Path(entry["target"])
        if source.resolve() != (ROOT / "skill-packages" / skill_id).resolve():
            raise ValueError("Source escapes approved package root")
        targets = records[skill_id]["mirrors"] if skill_id == "product-lifecycle-loop" else [
            str(Path.home() / root / "skills" / skill_id) for root in (".codex", ".agents")]
        if target.resolve() not in [Path(t).resolve() for t in targets] or str(target.resolve()) in seen:
            raise ValueError("Undeclared or duplicate destination")
        seen.add(str(target.resolve()))
        safe_tree(source); safe_tree(target)
        # Reject links at any ancestor, not just within the selected package.
        for ancestor in target.parents:
            if ancestor.is_symlink() or ancestor.is_junction():
                raise ValueError("Destination ancestor is linked")
        if fleet.tree_sha256(source) != entry["source_tree_sha256"]:
            raise ValueError("Source changed after review")
        actual = fleet.tree_sha256(target) if target.exists() else None
        if actual != entry["before_tree_sha256"]:
            raise ValueError("Destination changed after review")
    return registry


def apply(path, expected_sha):
    manifest = json.loads(path.read_text(encoding="utf-8"))
    registry = preflight(manifest, expected_sha, path)
    original = REGISTRY.read_bytes()
    batch = uuid.uuid4().hex
    archive = ROOT / "skill-fleet/backups" / ("enterprise-" + batch)
    archive.mkdir(parents=True)
    (archive / "registry.json").write_bytes(original)
    staged, swapped = [], []
    try:
        for n, entry in enumerate(manifest["entries"]):
            source, target = Path(entry["source"]), Path(entry["target"])
            stage = target.with_name("." + target.name + ".stage-" + batch)
            if target.exists():
                shutil.copytree(target, stage, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                stage.mkdir(parents=True)
            for asset in source.rglob("*"):
                if asset.is_file() and "__pycache__" not in asset.parts:
                    dest = stage / asset.relative_to(source)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(asset, dest)
            if fleet.source_file_drift(source, stage):
                raise ValueError("Staging parity failed")
            staged.append((entry, stage, archive / str(n)))
        # Recheck the entire batch immediately before the first mutation.
        preflight(manifest, expected_sha, path)
        for entry, stage, backup in staged:
            target = Path(entry["target"])
            # Each rename uses resolved, preflighted paths; no recursive deletion.
            if target.exists(): os.replace(target, backup)
            try:
                os.replace(stage, target)
            except BaseException:
                if backup.exists(): os.replace(backup, target)
                raise
            swapped.append((entry, backup))
        updated = copy.deepcopy(registry)
        records = {r["id"]: r for r in updated["skills"]}
        for entry, _ in swapped:
            record = records[entry["id"]]; target = Path(entry["target"])
            if fleet.source_file_drift(Path(entry["source"]), target):
                raise ValueError("Installed parity failed")
            if str(target) not in record["mirrors"]: record["mirrors"].append(str(target))
            record["reviewed_mirror_hashes"][str(target)] = fleet.sha256(target / "SKILL.md")
            record["reviewed_mirror_tree_hashes"][str(target)] = fleet.tree_sha256(target)
        temporary = REGISTRY.with_suffix(".enterprise.tmp")
        temporary.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, REGISTRY)
    except BaseException:
        for n, (entry, backup) in enumerate(reversed(swapped)):
            target = Path(entry["target"])
            os.replace(target, archive / ("failed-new-" + str(n)))
            if backup.exists(): os.replace(backup, target)
        REGISTRY.write_bytes(original)
        raise
    receipt = {"status": "INSTALLED", "targets": len(swapped), "manifest_sha256": expected_sha,
               "registry_sha256": fleet.sha256(REGISTRY), "backup": str(archive), "authority": "local distribution only"}
    (archive / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "apply"])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sha256")
    args = parser.parse_args()
    if args.command == "apply" and not args.sha256: parser.error("apply requires reviewed --sha256")
    print(json.dumps(prepare(args.manifest) if args.command == "prepare" else apply(args.manifest, args.sha256), indent=2))
