"""Strict JSON, portable content identities and atomic local artifacts."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import time
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2]


class AssuranceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AssuranceError(message)


def _pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def loads(text):
    try:
        return json.loads(text, object_pairs_hook=_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(AssuranceError("nonfinite JSON")))
    except (ValueError, TypeError) as exc:
        raise AssuranceError(f"invalid JSON: {exc}") from exc


def read(path):
    path = Path(path)
    require(path.stat().st_size <= 16_000_000, "JSON document exceeds size limit")
    try:
        return loads(path.read_text(encoding="utf-8-sig"))
    except UnicodeError as exc:
        raise AssuranceError("invalid UTF-8") from exc


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".assurance-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", value), "invalid identifier")
    return value


def finite(value, minimum=0):
    require(type(value) in (int, float) and math.isfinite(value) and value >= minimum, "invalid finite quantity")
    return value


def now():
    return int(time.time())


def bundle_digest():
    """Pins the verifier, schemas and catalog, excluding tests and mutable state."""
    manifest = {}
    for root in (PACKAGE / "scripts", PACKAGE / "schemas", PACKAGE / "catalog", PACKAGE / "tests"):
        for path in sorted(root.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                manifest[path.relative_to(PACKAGE).as_posix()] = file_digest(path)
    return digest(manifest)
