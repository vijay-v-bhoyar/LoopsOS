#!/usr/bin/env python3
"""Normalize the known non-standard canonical skill frontmatter without touching bodies."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

ALLOWED = {"name", "description", "license", "allowed-tools", "metadata"}
INVALID_DESCRIPTION_REPLACEMENTS = {
    "idea-add-moat": "Turn a product idea into a defensible product wedge through scoped moat design and re-evaluation.",
    "supabase-architect": "Design and implement a secure Supabase architecture for an AI application after reviewed approval.",
}
NORMALIZE = {"gstack", "last30days", "cloudflare", "turnstile-spin"}


def split(text: str) -> tuple[str, str]:
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if not match:
        raise ValueError("frontmatter missing")
    return match.group(1), text[match.end():]


def repaired(skill: Path) -> str | None:
    text = skill.read_text(encoding="utf-8-sig")
    raw, body = split(text)
    name_match = re.search(r"(?m)^name:\s*([^\r\n]+)$", raw)
    if not name_match:
        raise ValueError("name missing")
    name = name_match.group(1).strip().strip('"\'')
    if name in INVALID_DESCRIPTION_REPLACEMENTS:
        try:
            parsed = yaml.safe_load(raw)
            if isinstance(parsed, dict) and parsed.get("description") == INVALID_DESCRIPTION_REPLACEMENTS[name]:
                return None
        except yaml.YAMLError:
            pass
        header = {
            "name": name,
            "description": INVALID_DESCRIPTION_REPLACEMENTS[name],
        }
        return "---\n" + yaml.safe_dump(header, allow_unicode=True, sort_keys=False).strip() + "\n---\n" + body
    if name not in NORMALIZE:
        return None
    data: dict[str, Any] = yaml.safe_load(raw)
    metadata = data.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ValueError("metadata is not an object")
    changed = False
    for key in list(data):
        if key not in ALLOWED:
            metadata[key] = data.pop(key)
            changed = True
    if not changed:
        return None
    data["metadata"] = metadata
    return "---\n" + yaml.safe_dump(data, allow_unicode=True, sort_keys=False).strip() + "\n---\n" + body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    changes = []
    for directory in args.root.iterdir():
        skill = directory / "SKILL.md"
        if not skill.is_file():
            continue
        replacement = repaired(skill)
        if replacement is not None:
            changes.append(str(skill))
            if args.apply:
                skill.write_text(replacement, encoding="utf-8", newline="\n")
    print(json.dumps({"status": "APPLIED" if args.apply else "DRY_RUN", "changes": changes}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
