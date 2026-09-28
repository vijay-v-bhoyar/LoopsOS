#!/usr/bin/env python3
"""Non-mutating readiness guard for the Agentic Product Loop skill."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


EXPECTED_REFERENCE_SHA256 = (
    "94C691B89E0CC5987D3BBE03DCECAF80F2E62A29E80411E2D8DF90F9A0259AEB"
)

EXPECTED_ADAPTER_SHA256 = "E1FEE0004FBAE6DD12302FDCF53CB6E1FB0F05B154F2F6D3EB03777B6E254468"


def local_admission(adapter_path: str, config_path: str, config_sha256: str) -> dict[str, Any]:
    reference = Path(__file__).resolve().parents[1] / "references" / "PRODUCT-LOOP-FINAL-v13.md"
    if file_sha256(reference) != EXPECTED_REFERENCE_SHA256:
        raise ValueError("skill-reference-hash-mismatch")
    adapter = Path(adapter_path).resolve()
    if file_sha256(adapter) != EXPECTED_ADAPTER_SHA256:
        raise ValueError("cycle-adapter-hash-mismatch")
    spec = importlib.util.spec_from_file_location("verified_product_cycle_adapter", adapter)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.admission(module.load_config(config_path, config_sha256))

CORE_OWNER_SKILLS = [
    "product-loop",
    "product-backlog",
    "code-map",
    "product-evals",
    "security-review",
    "release-governor",
    "deploy-provision",
    "agent-release",
    "agent-oversight",
    "agent-security",
    "devcontainer-spec",
    "prompt-ops",
]

LOOP_FILES = [
    "VISION.md",
    "INBOX.md",
    "BACKLOG.md",
    "COMMANDS.md",
    "MAP.md",
    "LOOP_LOG.md",
    "DECISIONS.md",
    "METRICS.md",
    "SKILLS.md",
]


def run_git(repo: Path, *args: str) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError:
        return 127, "", "git executable not found"
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def installed_skill_names() -> set[str]:
    roots = [
        Path.home() / ".codex" / "skills",
        Path.home() / ".codex" / "skills" / ".system",
    ]
    names: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if child.is_dir() and (child / "SKILL.md").is_file():
                names.add(child.name)
    return names


def read_holds(loop_dir: Path) -> dict[str, Any] | None:
    hold_file = loop_dir / "run" / "HOLDS.json"
    if not hold_file.is_file():
        return None
    try:
        return json.loads(hold_file.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive diagnostic only
        return {"parse_error": str(exc)}


def assess(repo_arg: str) -> dict[str, Any]:
    repo = Path(repo_arg).expanduser().resolve()
    result: dict[str, Any] = {
        "repo": str(repo),
        "exists": repo.exists(),
        "is_dir": repo.is_dir(),
        "status": "blocked",
        "warnings": [],
        "blockers": [],
        "loop_files": {},
    }

    if not repo.exists() or not repo.is_dir():
        result["blockers"].append("repo-not-found")
        return result

    code, root_out, root_err = run_git(repo, "rev-parse", "--show-toplevel")
    result["git"] = {
        "available": code != 127,
        "is_repo": code == 0,
        "root": root_out if code == 0 else None,
        "error": root_err if code != 0 else None,
    }
    if code != 0:
        result["warnings"].append("not-a-git-repo")
        result["blockers"].append("not-a-git-repo")
        git_root = repo
    else:
        git_root = Path(root_out).resolve()

    code, porcelain, _ = run_git(git_root, "status", "--porcelain")
    dirty_entries = porcelain.splitlines() if code == 0 and porcelain else []
    result["git"]["dirty_entries"] = len(dirty_entries)
    result["git"]["dirty"] = bool(dirty_entries)
    if dirty_entries:
        result["warnings"].append("dirty-worktree")

    loop_dir = git_root / ".loop"
    result["loop_dir"] = str(loop_dir)
    result["loop_dir_exists"] = loop_dir.is_dir()
    for name in LOOP_FILES:
        path = loop_dir / name
        result["loop_files"][name] = path.is_file()

    stop_file = loop_dir / "STOP"
    result["stop_present"] = stop_file.exists()
    if stop_file.exists():
        result["blockers"].append("stop-present")

    if not result["loop_files"]["VISION.md"]:
        result["warnings"].append("init-required")

    holds = read_holds(loop_dir)
    result["holds"] = holds
    if holds:
        result["warnings"].append("holds-present")

    installed = installed_skill_names()
    missing_core = [name for name in CORE_OWNER_SKILLS if name not in installed]
    result["core_owner_skills"] = {
        "required": CORE_OWNER_SKILLS,
        "missing": missing_core,
    }
    if missing_core:
        result["blockers"].append("missing-core-owner-skills")

    reference = Path(__file__).resolve().parents[1] / "references" / "PRODUCT-LOOP-FINAL-v13.md"
    ref_hash = file_sha256(reference)
    result["skill_reference"] = {
        "path": str(reference),
        "sha256": ref_hash,
        "expected_sha256": EXPECTED_REFERENCE_SHA256,
        "ok": ref_hash == EXPECTED_REFERENCE_SHA256,
    }
    if ref_hash != EXPECTED_REFERENCE_SHA256:
        result["blockers"].append("skill-reference-hash-mismatch")

    if result["blockers"]:
        result["status"] = "blocked"
    elif not result["loop_files"]["VISION.md"]:
        result["status"] = "init_required"
    elif holds:
        result["status"] = "hold_review_required"
    else:
        result["status"] = "ready"

    return result


def print_text(report: dict[str, Any]) -> None:
    print(f"Repo: {report['repo']}")
    print(f"Status: {report['status']}")
    if report.get("blockers"):
        print("Blockers:")
        for item in report["blockers"]:
            print(f"  - {item}")
    if report.get("warnings"):
        print("Warnings:")
        for item in report["warnings"]:
            print(f"  - {item}")
    missing = report.get("core_owner_skills", {}).get("missing", [])
    if missing:
        print("Missing core owner skills:")
        for item in missing:
            print(f"  - {item}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="Target repository path")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--adapter", help="Exact product-loop cycle_adapter.py path for local admission")
    parser.add_argument("--config")
    parser.add_argument("--config-sha256")
    args = parser.parse_args(argv)

    if args.adapter or args.config or args.config_sha256:
        try:
            if not all([args.adapter, args.config, args.config_sha256]):
                raise ValueError("adapter-config-and-full-config-hash-required")
            report = local_admission(args.adapter, args.config, args.config_sha256)
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0
        except (ValueError, OSError, TypeError, subprocess.SubprocessError) as exc:
            print(json.dumps({"status": "BLOCKED", "reason": str(exc), "release": "BLOCKED_LEGACY_COMPATIBILITY"}))
            return 2

    report = assess(args.repo)
    report["discovery_status"] = report["status"]
    report["status"] = "DISCOVERY_ONLY"
    report["admission"] = "NOT_EVALUATED"
    report["release"] = "BLOCKED_LEGACY_COMPATIBILITY"
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text(report)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
