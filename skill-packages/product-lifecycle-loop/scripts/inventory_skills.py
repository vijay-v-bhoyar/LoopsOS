#!/usr/bin/env python3
"""Inventory SKILL.md files without executing them; uses only Python's stdlib.

Example:
    python inventory_skills.py --root personal=/path/to/skills --name product-loop

The metadata reader supports common YAML scalar forms, not all YAML. Unsupported
or missing metadata is reported explicitly. Discovery does not establish that a
skill is installed, enabled, trustworthy, or callable in the current session.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any


REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
FIELD = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:[ \t]+(.*)|[ \t]*)$")
BLOCK = re.compile(r"^[|>](?:[+-]?[1-9]?|[1-9][+-]?)$")


def _scalar(raw: str) -> str:
    """Read a conservative YAML string scalar and reject unsupported syntax."""
    raw = raw.strip()
    if not raw or raw.startswith("#"):
        raise ValueError("empty scalar")
    if raw.startswith('"'):
        try:
            value, end = json.JSONDecoder().raw_decode(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid or unsupported double-quoted scalar") from exc
        tail = raw[end:].strip()
        if not isinstance(value, str) or (tail and not tail.startswith("#")):
            raise ValueError("invalid quoted scalar or trailing content")
        return value
    if raw.startswith("'"):
        match = re.fullmatch(r"'((?:[^']|'')*)'(?:\s+#.*)?", raw)
        if match is None:
            raise ValueError("invalid or unsupported single-quoted scalar")
        return match.group(1).replace("''", "'")
    value = re.split(r"\s+#", raw, maxsplit=1)[0].rstrip()
    if (
        not value
        or value[0] in "[{|>&*!%@`"
        or value.startswith(("- ", "? ", ": "))
        or ": " in value
        or value.lower() in {"null", "~", "true", "false", "yes", "no", "on", "off"}
        or re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value)
    ):
        raise ValueError("expected a string; unsupported YAML scalar form")
    return value


def parse_metadata(content: str) -> dict[str, Any]:
    """Extract declared name/description; never derive a name from a folder."""
    result: dict[str, Any] = {"name": None, "description": None, "errors": []}
    lines = content.removeprefix("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        result["errors"].append("missing opening frontmatter delimiter")
        return result
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        result["errors"].append("missing closing frontmatter delimiter")
        return result
    seen: set[str] = set()
    i = 1
    while i < end:
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#") or line[0].isspace():
            i += 1
            continue
        match = FIELD.fullmatch(line)
        if match is None:
            result["errors"].append(f"unrecognized frontmatter line {i + 1}")
            i += 1
            continue
        key, raw = match.group(1), match.group(2) or ""
        i += 1
        continuation: list[str] = []
        while i < end and (not lines[i].strip() or lines[i][0].isspace()):
            continuation.append(lines[i])
            i += 1
        if key not in {"name", "description"}:
            continue
        if key in seen:
            result[key] = None
            result["errors"].append(f"duplicate {key} field")
            continue
        seen.add(key)
        try:
            # Comments after a block marker are valid, but indentation indicators
            # are deliberately not interpreted; unsupported forms are explicit.
            marker = re.split(r"\s+#", raw.strip(), maxsplit=1)[0]
            if BLOCK.fullmatch(marker):
                if key == "name" or re.search(r"[1-9]", marker):
                    raise ValueError("unsupported block scalar for name or explicit indentation")
                nonblank = [s for s in continuation if s.strip()]
                if not nonblank:
                    raise ValueError("empty block scalar")
                indent = min(len(s) - len(s.lstrip()) for s in nonblank)
                pieces = [s[indent:] if s.strip() else "" for s in continuation]
                # Best-effort folded text preserves paragraph breaks.
                if marker.startswith(">"):
                    paragraphs = "\n".join(pieces).strip("\n").split("\n\n")
                    value = "\n\n".join(" ".join(p.splitlines()) for p in paragraphs)
                else:
                    value = "\n".join(pieces).strip("\n")
            else:
                value = _scalar(raw)
                extra = [s.strip() for s in continuation if s.strip() and not s.lstrip().startswith("#")]
                if extra:
                    if key == "name" or raw.strip().startswith(("'", '"')):
                        raise ValueError("unsupported multiline name or quoted scalar")
                    value = " ".join([value, *extra])
            if not value.strip():
                raise ValueError("empty string")
            result[key] = value
        except ValueError as exc:
            result["errors"].append(f"{key}: {exc}")
    for key in ("name", "description"):
        if key not in seen:
            result["errors"].append(f"missing {key} field")
    return result


def _linked(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & REPARSE_POINT)


def _path_key(path: Path) -> str:
    return os.path.normcase(str(path))


def inventory(roots: list[tuple[str, str]], names: list[str] | None = None) -> dict[str, Any]:
    """Return deterministic inventory; duplicate root memberships are retained."""
    report: dict[str, Any] = {
        "schema_version": 1,
        "metadata_parser": "best-effort YAML string scalars; not a full YAML validator",
        "roots": [],
        "skills": [],
        "duplicate_names": [],
        "resolutions": [],
        "errors": [],
        "stats": {},
    }
    by_path: dict[str, dict[str, Any]] = {}
    root_keys: set[tuple[str, str]] = set()

    def error(path: Path, operation: str, message: str, severity: str = "error") -> None:
        entry = {"path": str(path), "operation": operation, "message": message, "severity": severity}
        if entry not in report["errors"]:
            report["errors"].append(entry)

    for category, supplied in roots:
        root = Path(os.path.abspath(Path(supplied).expanduser()))
        root_key = (category, _path_key(root))
        if root_key in root_keys:
            continue
        root_keys.add(root_key)
        report["roots"].append({"category": category, "path": str(root)})
        try:
            root_info = root.lstat()
            if _linked(root_info):
                error(root, "skip_link", "linked or reparse-point root was not followed")
                continue
            if not stat.S_ISDIR(root_info.st_mode):
                error(root, "scan_root", "root is not a directory")
                continue
            boundary = root.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            error(root, "scan_root", str(exc))
            continue

        pending = [root]
        visited: set[str] = set()
        while pending:
            directory = pending.pop()
            try:
                if _linked(directory.lstat()):
                    error(directory, "skip_link", "directory link was not followed", "warning")
                    continue
                resolved_directory = directory.resolve(strict=True)
                if not resolved_directory.is_relative_to(boundary):
                    error(directory, "scan_directory", "resolved directory is outside its root")
                    continue
                directory_key = _path_key(resolved_directory)
                if directory_key in visited:
                    continue
                visited.add(directory_key)
                with os.scandir(directory) as iterator:
                    entries = sorted(iterator, key=lambda entry: (entry.name.casefold(), entry.name))
            except (OSError, RuntimeError) as exc:
                error(directory, "scan_directory", str(exc))
                continue
            child_directories: list[Path] = []
            for entry in entries:
                path = Path(entry.path)
                try:
                    info = entry.stat(follow_symlinks=False)
                    if _linked(info):
                        error(path, "skip_link", "link or reparse point was not followed", "warning")
                        continue
                    if stat.S_ISDIR(info.st_mode):
                        child_directories.append(path)
                        continue
                    if not stat.S_ISREG(info.st_mode) or entry.name != "SKILL.md":
                        continue
                    canonical = path.resolve(strict=True)
                    if not canonical.is_relative_to(boundary):
                        error(path, "read_file", "resolved file is outside its root")
                        continue
                    path_key = _path_key(canonical)
                    if path_key not in by_path:
                        record: dict[str, Any] = {
                            "path": str(canonical), "paths": [], "categories": [], "sources": [],
                            "name": None, "description": None, "sha256": None,
                            "metadata_status": "ERROR", "metadata_errors": [],
                        }
                        by_path[path_key] = record
                        try:
                            raw = path.read_bytes()
                            record["sha256"] = hashlib.sha256(raw).hexdigest()
                            metadata = parse_metadata(raw.decode("utf-8-sig"))
                            record["name"] = metadata["name"]
                            record["description"] = metadata["description"]
                            record["metadata_errors"] = metadata["errors"]
                            record["metadata_status"] = "ERROR" if metadata["errors"] else "OK"
                        except UnicodeDecodeError as exc:
                            record["metadata_errors"] = [f"invalid UTF-8: {exc}"]
                        except OSError as exc:
                            error(path, "read_file", str(exc))
                            record["metadata_errors"] = ["file could not be read"]
                    record = by_path[path_key]
                    source = {"category": category, "root": str(root), "path": str(path)}
                    if source not in record["sources"]:
                        record["sources"].append(source)
                    if str(path) not in record["paths"]:
                        record["paths"].append(str(path))
                    if category not in record["categories"]:
                        record["categories"].append(category)
                except (OSError, RuntimeError) as exc:
                    error(path, "inspect_entry", str(exc))
            pending.extend(reversed(child_directories))

    report["skills"] = sorted(by_path.values(), key=lambda skill: _path_key(Path(skill["path"])))
    by_name: dict[str, list[dict[str, Any]]] = {}
    for skill in report["skills"]:
        skill["paths"].sort()
        skill["categories"].sort()
        skill["sources"].sort(key=lambda source: (source["category"], source["root"], source["path"]))
        if skill["name"] is not None:
            by_name.setdefault(skill["name"], []).append(skill)
    for name, copies in sorted(by_name.items()):
        if len(copies) > 1:
            report["duplicate_names"].append({
                "name": name,
                "status": "IDENTICAL" if len({copy["sha256"] for copy in copies}) == 1 else "DRIFTED",
                "paths": [copy["path"] for copy in copies],
                "sha256": sorted({copy["sha256"] for copy in copies}),
            })
    for name in dict.fromkeys(names or []):
        copies = by_name.get(name, [])
        status = "MISSING" if not copies else (
            "MATCH" if len({copy["sha256"] for copy in copies}) == 1 else "AMBIGUOUS"
        )
        report["resolutions"].append({
            "name": name,
            "status": status,
            "copies": [{key: copy[key] for key in ("path", "categories", "sha256", "metadata_status")}
                       for copy in copies],
        })
    report["stats"] = {
        "roots": len(report["roots"]),
        "files": len(report["skills"]),
        "declared_names": len(by_name),
        "metadata_errors": sum(skill["metadata_status"] == "ERROR" for skill in report["skills"]),
        "duplicate_names": len(report["duplicate_names"]),
        "drifted_names": sum(group["status"] == "DRIFTED" for group in report["duplicate_names"]),
        "scan_errors": sum(entry["severity"] == "error" for entry in report["errors"]),
        "warnings": sum(entry["severity"] == "warning" for entry in report["errors"]),
    }
    return report


def _root_argument(value: str) -> tuple[str, str]:
    category, separator, path = value.partition("=")
    if not separator or not category.strip() or not path.strip():
        raise argparse.ArgumentTypeError("use CATEGORY=PATH, for example personal=/path/to/skills")
    return category.strip(), path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=_root_argument, action="append", metavar="CATEGORY=PATH",
                        help="root directory and provenance category; repeat to scan multiple roots")
    parser.add_argument("--name", action="append", default=[], help="exact declared name to resolve; repeatable")
    parser.add_argument("--output", type=Path, help="write UTF-8 JSON to this path instead of stdout")
    args = parser.parse_args(argv)
    if not args.root:
        parser.error("at least one --root CATEGORY=PATH is required; no directories are scanned by default")
    report = inventory(args.root, args.name)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    try:
        if args.output:
            args.output.write_text(serialized, encoding="utf-8")
        else:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            sys.stdout.write(serialized)
    except (OSError, UnicodeError) as exc:
        print(f"inventory output failed: {exc}", file=sys.stderr)
        return 1
    # Missing/ambiguous names and metadata problems are findings, not release
    # gates. Only operational scan failures cause a nonzero result here.
    return 1 if report["stats"]["scan_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
