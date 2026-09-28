#!/usr/bin/env python3
"""Validate, inventory, and deliberately synchronize the personal skill fleet.

The tool is safe by default: validation and registry generation never modify a
skill. Synchronization requires both ``sync`` and ``--apply`` and only writes
manifest-declared mirrors whose current digest is either the canonical digest
or a reviewed baseline digest recorded in the registry.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "skill-fleet/v2"
ALLOWED_FRONTMATTER = {"name", "description", "license", "allowed-tools", "metadata"}
LOOPS = {
    "agentic-assurance-loop", "agentic-product-loop", "codex-product-build-loop",
    "loop-fleet", "product-diligence", "product-lifecycle-loop", "product-loop",
    "product-vision",
}
LEGACY_ALIASES = {
    "product-diligence": ["Product Deligence Loop V4", "prompts"],
}
MANUAL_SKILLS = {
    "agent-release", "cloudflare", "deploy-provision", "devcontainer-spec", "mcp-builder",
    "migration-safety", "ship-release", "supabase-architect", "turnstile-spin",
}
MAX_NAME = 64
REQUIRED_LIFECYCLE_STEPS = {
    "registry-admission",
    "graph-orientation",
    "goal-and-requirement-admission",
    "delivery-engine-selection",
    "specialist-and-risk-routing",
    "recover-park-and-resume",
    "independent-verification-and-closure",
    "governed-release",
    "operate-and-learn",
    "fleet-change-quality",
}
REQUIRED_POLICY_TOPOLOGY = {
    "conductor": "product-lifecycle-loop",
    "delivery_engines": {"codex-product-build-loop", "product-loop", "agentic-product-loop"},
    "parallelizer": "loop-fleet",
    "assurance": "agentic-assurance-loop",
    "release_decider": "release-governor",
    "deployment_executor": "deploy-provision",
}


class FleetError(ValueError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_sha256(directory: Path) -> str:
    """Content-address a package without depending on mtime, separators, or order."""
    digest = hashlib.sha256()
    for path in sorted(item for item in directory.rglob("*") if item.is_file() and "__pycache__" not in item.parts):
        digest.update(path.relative_to(directory).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def source_file_drift(source: Path, mirror: Path) -> list[str]:
    """Return source-owned files absent or changed in a mirror; ignore mirror-only files."""
    drift: list[str] = []
    for path in sorted(item for item in source.rglob("*") if item.is_file() and "__pycache__" not in item.parts):
        relative = path.relative_to(source)
        target = mirror / relative
        if not target.is_file() or sha256(path) != sha256(target):
            drift.append(relative.as_posix())
    return drift


def load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise FleetError(f"{path}: invalid UTF-8") from exc


def parse_skill(path: Path) -> tuple[dict[str, Any], str]:
    text = load_text(path)
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if not match:
        raise FleetError(f"{path}: YAML frontmatter is required")
    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise FleetError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(frontmatter, dict):
        raise FleetError(f"{path}: frontmatter must be an object")
    return frontmatter, text[match.end():]


def valid_frontmatter(frontmatter: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    unexpected = sorted(set(frontmatter) - ALLOWED_FRONTMATTER)
    if unexpected:
        errors.append(f"{path}: unsupported frontmatter key(s): {', '.join(unexpected)}")
    name = frontmatter.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        errors.append(f"{path}: name must be lower-kebab-case")
    elif len(name) > MAX_NAME:
        errors.append(f"{path}: name exceeds {MAX_NAME} characters")
    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append(f"{path}: description is required")
    elif len(description.strip()) > 1024:
        errors.append(f"{path}: description exceeds 1024 characters")
    return errors


def referenced_paths(body: str) -> set[str]:
    result: set[str] = set()
    for match in re.finditer(r"\[[^\]\r\n]*\]\(([^)\s]+)(?:\s+[^)]*)?\)", body):
        target = match.group(1).split("#", 1)[0]
        if target.startswith(("references/", "assets/", "scripts/", "templates/")):
            result.add(target)
    return result


@dataclass(frozen=True)
class SkillRecord:
    skill_id: str
    canonical: Path
    mirrors: tuple[Path, ...]
    version: str
    owner: str
    test_class: str
    manual_prerequisite: str | None
    aliases: tuple[str, ...]
    reviewed_mirror_hashes: dict[str, str]
    reviewed_mirror_tree_hashes: dict[str, str]


def path_value(value: str, registry_path: Path) -> Path:
    expanded = value.replace("${WORKSPACE}", str(registry_path.parent.parent.resolve()))
    return Path(expanded).expanduser().resolve()


def validate_lifecycle_policy(payload: dict[str, Any], active_ids: set[str]) -> list[str]:
    """Validate the mandatory lifecycle contract stored with the fleet itself."""
    errors: list[str] = []
    policy = payload.get("lifecycle_policy")
    if not isinstance(policy, dict):
        return ["registry: lifecycle_policy is required"]
    if policy.get("version") not in {"1.0.0", "1.1.0"}:
        errors.append("registry: lifecycle_policy has unsupported version")
    artifacts = policy.get("artifacts")
    if not isinstance(artifacts, dict) or not all(
        isinstance(artifacts.get(key), str) and artifacts[key].strip()
        for key in ("map", "generator")
    ):
        errors.append("registry: lifecycle_policy must declare map and generator artifacts")
    topology = policy.get("topology")
    if not isinstance(topology, dict):
        return errors + ["registry: lifecycle_policy.topology is required"]
    for key, expected in REQUIRED_POLICY_TOPOLOGY.items():
        value = topology.get(key)
        if key == "delivery_engines":
            if not isinstance(value, list) or set(value) != expected:
                errors.append("registry: lifecycle_policy delivery engines must be the declared three engines")
            continue
        if value != expected:
            errors.append(f"registry: lifecycle_policy topology.{key} must be {expected}")
    if topology.get("exactly_one_delivery_engine") is not True:
        errors.append("registry: lifecycle_policy must require exactly one delivery engine")
    if topology.get("parallelization_requires_solo_engine_proof") is not True:
        errors.append("registry: lifecycle_policy must require solo-engine proof before parallelization")
    if topology.get("deployment_requires_go_and_authority") is not True:
        errors.append("registry: lifecycle_policy must require GO and authority before deployment")

    steps = policy.get("mandatory_steps")
    if not isinstance(steps, list):
        return errors + ["registry: lifecycle_policy.mandatory_steps is required"]
    seen_steps: set[str] = set()
    for step in steps:
        if not isinstance(step, dict):
            errors.append("registry: lifecycle_policy mandatory step must be an object")
            continue
        step_id = step.get("id")
        if not isinstance(step_id, str) or not step_id:
            errors.append("registry: lifecycle_policy mandatory step needs an id")
            continue
        if step_id in seen_steps:
            errors.append(f"registry: duplicate lifecycle mandatory step {step_id}")
        seen_steps.add(step_id)
        for field in ("applies_when", "required_evidence"):
            if not isinstance(step.get(field), str) or not step[field].strip():
                errors.append(f"registry: lifecycle step {step_id} needs {field}")
        skills = step.get("required_skills")
        if not isinstance(skills, list) or not skills or not all(isinstance(skill, str) for skill in skills):
            errors.append(f"registry: lifecycle step {step_id} needs required_skills")
        elif unknown := sorted(set(skills) - active_ids):
            errors.append(f"registry: lifecycle step {step_id} references unknown skills: {', '.join(unknown)}")
    required_steps = REQUIRED_LIFECYCLE_STEPS | ({"enterprise-ai-assurance"} if policy.get("version") == "1.1.0" else set())
    if policy.get("version") == "1.1.0":
        enterprise = policy.get("enterprise_assurance", {})
        if enterprise.get("skill") != "enterprise-ai-assurance-loop" or enterprise.get("required_owner_count") != 13:
            errors.append("registry: enterprise assurance requires one loop and thirteen owners")
        if enterprise.get("evaluator") != "skill-packages/enterprise-ai-assurance-loop/scripts/assurance.py":
            errors.append("registry: enterprise assurance evaluator is not the registered runtime")
        if enterprise.get("deployment_authority") is not False or enterprise.get("test_evidence_cannot_prove_enterprise") is not True:
            errors.append("registry: enterprise assurance must preserve production authority boundary")
        if enterprise.get("parent_completion_gate") != "skill-packages/product-lifecycle-loop/scripts/progress_state.py":
            errors.append("registry: enterprise assurance parent completion gate missing")
    missing_steps = sorted(required_steps - seen_steps)
    extra_steps = sorted(seen_steps - required_steps)
    if missing_steps:
        errors.append(f"registry: missing lifecycle mandatory step(s): {', '.join(missing_steps)}")
    if extra_steps:
        errors.append(f"registry: unknown lifecycle mandatory step(s): {', '.join(extra_steps)}")
    return errors


def records(registry_path: Path, payload: dict[str, Any] | None = None) -> list[SkillRecord]:
    payload = payload or json.loads(registry_path.read_text(encoding="utf-8"))
    if payload.get("schema") != SCHEMA:
        raise FleetError("registry: unsupported schema")
    seen: set[str] = set()
    result: list[SkillRecord] = []
    for item in payload.get("skills", []):
        skill_id = item.get("id")
        if not isinstance(skill_id, str) or skill_id in seen:
            raise FleetError("registry: duplicate or invalid skill id")
        seen.add(skill_id)
        test = item.get("test", {})
        test_class = test.get("class")
        if test_class not in {"static", "fixture", "manual-required"}:
            raise FleetError(f"registry: {skill_id} has invalid test class")
        prerequisite = test.get("prerequisite")
        if test_class == "manual-required" and not isinstance(prerequisite, str):
            raise FleetError(f"registry: {skill_id} needs a manual prerequisite")
        result.append(SkillRecord(
            skill_id, path_value(item["canonical"], registry_path),
            tuple(path_value(value, registry_path) for value in item.get("mirrors", [])),
            item.get("version", "1.0.0"), item.get("owner", "skill-fleet"), test_class,
            prerequisite, tuple(item.get("aliases", [])), item.get("reviewed_mirror_hashes", {}),
            item.get("reviewed_mirror_tree_hashes", {}),
        ))
    return result


def validate(registry_path: Path, repository_only: bool = False) -> list[str]:
    errors: list[str] = []
    identities: dict[str, str] = {}
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    records_for_validation = records(registry_path, payload)
    errors.extend(validate_lifecycle_policy(payload, {record.skill_id for record in records_for_validation}))
    workspace = registry_path.parent.parent.resolve()
    package_root = workspace / "skill-packages"
    if payload.get("pending_distribution_changes"):
        errors.append("registry: unreviewed distribution changes require explicit review")
    manifest_by_id = {item["id"]: item for item in payload["skills"]}
    declared_packages = {record.canonical.resolve() for record in records_for_validation}
    if package_root.is_dir():
        for entrypoint in package_root.glob("*/SKILL.md"):
            if entrypoint.parent.resolve() not in declared_packages:
                errors.append(f"undeclared workspace skill package: {entrypoint.parent.name}")
    for record in records_for_validation:
        if repository_only and not record.canonical.is_relative_to(package_root):
            continue
        canonical_file = record.canonical / "SKILL.md"
        if not canonical_file.is_file():
            errors.append(f"{record.skill_id}: canonical SKILL.md missing")
            continue
        try:
            frontmatter, body = parse_skill(canonical_file)
        except FleetError as exc:
            errors.append(str(exc))
            continue
        errors.extend(valid_frontmatter(frontmatter, canonical_file))
        declared = frontmatter.get("name")
        if declared != record.skill_id:
            errors.append(f"{record.skill_id}: declared id is {declared!r}")
        if declared in identities:
            errors.append(f"duplicate active identity {declared}: {identities[declared]} and {record.skill_id}")
        identities[declared] = record.skill_id
        for reference in referenced_paths(body):
            if not (record.canonical / reference).is_file():
                errors.append(f"{record.skill_id}: missing internal reference {reference}")
        canonical_hash = sha256(canonical_file)
        canonical_tree_hash = tree_sha256(record.canonical)
        manifest = manifest_by_id[record.skill_id]
        if manifest.get("canonical_sha256") and manifest["canonical_sha256"] != canonical_hash:
            errors.append(f"{record.skill_id}: canonical entrypoint hash drift")
        if manifest.get("canonical_tree_sha256") and manifest["canonical_tree_sha256"] != canonical_tree_hash:
            errors.append(f"{record.skill_id}: canonical package hash drift")
        for mirror in (() if repository_only else record.mirrors):
            mirror_file = mirror / "SKILL.md"
            if not mirror_file.is_file():
                errors.append(f"{record.skill_id}: declared mirror missing: {mirror}")
                continue
            mirror_hash = sha256(mirror_file)
            reviewed_hash = record.reviewed_mirror_hashes.get(str(mirror))
            if reviewed_hash != mirror_hash:
                errors.append(f"{record.skill_id}: mirror hash is not the reviewed registry value: {mirror}")
            mirror_tree_hash = tree_sha256(mirror)
            reviewed_tree_hash = record.reviewed_mirror_tree_hashes.get(str(mirror))
            if reviewed_tree_hash != mirror_tree_hash:
                errors.append(f"{record.skill_id}: mirror package hash is not the reviewed registry value: {mirror}")
            if mirror_hash != canonical_hash:
                errors.append(f"{record.skill_id}: mirror drift: {mirror}")
            elif source_file_drift(record.canonical, mirror):
                errors.append(f"{record.skill_id}: mirror package drift: {mirror}")
        if record.test_class == "fixture":
            if not any(record.canonical.rglob("test_*.py")) and not any(record.canonical.rglob("*.test.*")):
                errors.append(f"{record.skill_id}: fixture class declared without a test file")
    policy = payload.get("lifecycle_policy")
    if isinstance(policy, dict) and isinstance(policy.get("topology"), dict):
        conductor_id = policy["topology"].get("conductor")
        conductor = next((record for record in records_for_validation if record.skill_id == conductor_id), None)
        if conductor:
            binding = conductor.canonical / "fleet-binding.md"
            contract = conductor.canonical / "references" / "run-contract.md"
            if not binding.is_file() or "lifecycle_policy" not in load_text(binding):
                errors.append(f"{conductor_id}: fleet binding must require lifecycle_policy")
            if not contract.is_file() or "lifecycle_policy" not in load_text(contract):
                errors.append(f"{conductor_id}: run contract must record lifecycle_policy evidence")
    return errors


def discover(workspace: Path) -> dict[str, Any]:
    """Discover proposals without erasing policy, existing hashes or review decisions."""
    registry_path = workspace / "skill-fleet" / "registry.json"
    previous = json.loads(registry_path.read_text(encoding="utf-8-sig")) if registry_path.is_file() else {"schema": SCHEMA, "skills": []}
    result = copy.deepcopy(previous)
    existing = {record["id"]: record for record in result.get("skills", [])}
    discovered = _discover_candidates(workspace)
    changes = []
    for item in discovered["skills"]:
        skill_id = item["id"]
        if skill_id in existing:
            old = existing[skill_id]
            if path_value(old["canonical"], registry_path) != path_value(item["canonical"], registry_path):
                changes.append({"id": skill_id, "change": "canonical-source", "proposed": item["canonical"]})
            # Never silently bless changed mirrors, versions, test declarations or hashes.
        else:
            existing[skill_id] = item
            changes.append({"id": skill_id, "change": "new-skill"})
    result["skills"] = [existing[key] for key in sorted(existing)]
    if changes:
        result["pending_distribution_changes"] = changes
    return result


def _discover_candidates(workspace: Path) -> dict[str, Any]:
    codex = Path.home() / ".codex" / "skills"
    agents = Path.home() / ".agents" / "skills"
    packages = workspace / "skill-packages"
    skills: dict[str, dict[str, Any]] = {}
    candidates = sorted(codex.iterdir()) if codex.is_dir() else []
    candidates += sorted(packages.iterdir()) if packages.is_dir() else []
    for directory in candidates:
        file = directory / "SKILL.md"
        if not directory.is_dir() or not file.is_file() or directory.name == ".system":
            continue
        try:
            frontmatter, _ = parse_skill(file)
            skill_id = frontmatter.get("name")
        except FleetError:
            frontmatter = {}
            skill_id = directory.name
        if not isinstance(skill_id, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill_id):
            continue
        canonical = packages / skill_id if (packages / skill_id / "SKILL.md").is_file() else directory
        mirrors: list[Path] = []
        agent_match = agents / directory.name
        if agent_match.joinpath("SKILL.md").is_file() and agent_match.resolve() != canonical.resolve():
            mirrors.append(agent_match)
        if canonical.parent == packages:
            for candidate in (codex / skill_id, workspace / ".codex" / "skills" / skill_id):
                if candidate.joinpath("SKILL.md").is_file() and candidate.resolve() != canonical.resolve() and candidate not in mirrors:
                    mirrors.append(candidate)
        test_files = list(canonical.rglob("test_*.py")) + list(canonical.rglob("*.test.*"))
        tools = frontmatter.get("allowed-tools", [])
        tools = [tools] if isinstance(tools, str) else tools if isinstance(tools, list) else []
        side_effectful = any(str(tool).lower() in {"write", "bash", "shell", "computer", "browser"} for tool in tools)
        if skill_id in MANUAL_SKILLS:
            test = {
                "class": "manual-required",
                "prerequisite": "A named sandbox target and explicit authority for side-effecting execution.",
            }
        elif test_files:
            test = {"class": "fixture"}
        elif side_effectful:
            test = {
                "class": "manual-required",
                "prerequisite": "A named sandbox target and explicit authority for side-effecting execution.",
            }
        else:
            test = {"class": "static"}
        aliases = LEGACY_ALIASES.get(skill_id, [])
        if skill_id == "product-diligence":
            for alias in aliases:
                candidate = codex / alias
                if candidate.joinpath("SKILL.md").is_file() and candidate not in mirrors:
                    mirrors.append(candidate)
                candidate = agents / alias
                if candidate.joinpath("SKILL.md").is_file() and candidate not in mirrors:
                    mirrors.append(candidate)
        mirror_hashes = {str(path): sha256(path / "SKILL.md") for path in mirrors}
        mirror_tree_hashes = {str(path): tree_sha256(path) for path in mirrors}
        skills[skill_id] = {
            "id": skill_id,
            "canonical": "${WORKSPACE}/skill-packages/" + skill_id if canonical.parent == packages else str(canonical),
            "mirrors": [str(path) for path in sorted(set(mirrors))],
            "version": "1.0.0",
            "owner": "skill-fleet",
            "test": test,
            "aliases": aliases,
            "reviewed_mirror_hashes": mirror_hashes,
            "reviewed_mirror_tree_hashes": mirror_tree_hashes,
        }
    return {"schema": SCHEMA, "skills": [skills[key] for key in sorted(skills)]}


def sync(registry_path: Path, apply: bool) -> list[str]:
    messages: list[str] = []
    for record in records(registry_path):
        source = record.canonical / "SKILL.md"
        if not source.is_file():
            raise FleetError(f"{record.skill_id}: canonical missing")
        source_hash = sha256(source)
        for mirror_dir in record.mirrors:
            destination = mirror_dir / "SKILL.md"
            current = sha256(destination) if destination.is_file() else None
            approved = {source_hash, record.reviewed_mirror_hashes.get(str(mirror_dir))}
            if current not in approved:
                raise FleetError(f"{record.skill_id}: unreviewed mirror differs: {mirror_dir}")
            changed_files = source_file_drift(record.canonical, mirror_dir)
            if current == source_hash and not changed_files:
                continue
            messages.append(f"sync {record.skill_id}: {mirror_dir}")
            if apply:
                for relative in changed_files:
                    origin = record.canonical / relative
                    destination_file = mirror_dir / relative
                    backup = registry_path.parent / "backups" / record.skill_id / relative
                    if destination_file.is_file():
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(destination_file, backup)
                    destination_file.parent.mkdir(parents=True, exist_ok=True)
                    temporary = destination_file.with_name(f".{destination_file.name}.skill-fleet.tmp")
                    shutil.copy2(origin, temporary)
                    temporary.replace(destination_file)
    return messages


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build-registry")
    build.add_argument("--workspace", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("validate")
    check.add_argument("--registry", type=Path, required=True)
    check.add_argument("--repository-only", action="store_true", help="Portable source gate; installed personal mirrors require a separate local check")
    sync_parser = sub.add_parser("sync")
    sync_parser.add_argument("--registry", type=Path, required=True)
    sync_parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "build-registry":
            payload = discover(args.workspace.resolve())
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            print(f"registry written: {args.output} ({len(payload['skills'])} skills)")
            return 0
        if args.command == "validate":
            errors = validate(args.registry.resolve(), repository_only=args.repository_only)
            print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
            return 0 if not errors else 1
        messages = sync(args.registry.resolve(), args.apply)
        print(json.dumps({"status": "APPLIED" if args.apply else "DRY_RUN", "changes": messages}, indent=2))
        return 0
    except (FleetError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
