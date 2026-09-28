"""Closed JSON Schema contracts; never resolve remote schemas from evidence."""
from __future__ import annotations

from jsonschema import Draft202012Validator
from .common import PACKAGE, AssuranceError, encoded, read


def validate(kind, value):
    # Names are selected by program code, not by imported evidence.
    if kind not in {"subject", "profile", "trust", "envelope", "evidence", "risk", "review", "waiver", "operation", "help", "schedule"}:
        raise AssuranceError("unknown contract")
    encoded(value)  # Reject nonfinite numbers even if callers bypass JSON input.
    schema = read(PACKAGE / "schemas" / (kind + ".schema.json"))
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: str(e.path))
    if errors:
        error = errors[0]
        raise AssuranceError(f"{kind} at {'/'.join(map(str, error.path))}: {error.message}")
    return value
