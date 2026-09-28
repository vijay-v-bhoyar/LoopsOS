"""Capture a deterministic, local-only subject snapshot for governed runs.

The snapshot is an integrity reference for the current checkout. It does not
attest to a deployment, provider, database, identity, or organizational review.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = {".py", ".ts", ".tsx", ".mjs", ".json", ".yaml", ".yml", ".sql", ".md"}
SOURCE_FOLDERS = (
    "authority/loopos_authority",
    "authority/tests",
    "ui/src",
    "ui/e2e",
    "ui/scripts",
    "scripts",
    "runtime",
    "schemas",
    "evals",
    "security",
    "supabase/migrations",
    ".github/workflows",
    "skill-packages/codex-product-build-loop",
)
SOURCE_FILES = (
    "ui/package.json",
    "ui/package-lock.json",
    "authority/requirements.txt",
    "requirements.txt",
    "ui/vite.config.ts",
    "ui/playwright.config.ts",
    "skill-fleet/registry.json",
    "authority/.env.example",
    "authority/README.md",
    "authority/RELEASE_REVIEW.md",
    "authority/AGGREGATE_EFFECT_BUDGET.md",
    "authority/CONNECTOR_EGRESS.md",
    "authority/AUDIT_ANCHOR_SECURITY.md",
    "ui/README.md",
    "ui/LLM_GATEWAY_ATTESTATION.md",
    "docs/data-deletion-boundary.md",
)


def _git(command: list[str]) -> str:
    return subprocess.check_output(command, cwd=ROOT, text=True).strip()


def _paths() -> list[Path]:
    paths: set[Path] = set()
    for folder in SOURCE_FOLDERS:
        root = ROOT / folder
        if not root.is_dir():
            continue
        paths.update(
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in SUFFIXES and "__pycache__" not in path.parts
        )
    paths.update(ROOT / relative for relative in SOURCE_FILES if (ROOT / relative).is_file())
    return sorted(paths)


def capture(output: Path) -> dict[str, object]:
    manifest = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in _paths()
    ]
    manifest_digest = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    subject: dict[str, object] = {
        "schema_version": 1,
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "git_head": _git(["git", "rev-parse", "HEAD"]),
        "branch": _git(["git", "branch", "--show-current"]),
        "working_tree": "existing modified checkout; these hashes, not HEAD alone, identify inspected content",
        "scope": "local evaluation and isolated API; no production endpoint",
        "capture_source": "scripts/capture_subject_snapshot.py",
        "files": manifest,
        "manifest_sha256": manifest_digest,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(subject, indent=2) + "\n", encoding="utf-8")
    return subject


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a local-only subject snapshot.")
    parser.add_argument("--output", type=Path, required=True, help="Destination JSON path.")
    args = parser.parse_args()
    subject = capture(args.output)
    print(json.dumps({"output": str(args.output), "files": len(subject["files"]), "manifest_sha256": subject["manifest_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
