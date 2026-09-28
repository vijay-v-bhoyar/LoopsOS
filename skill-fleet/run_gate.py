"""Portable fleet source gate and actual safe-local suite execution receipt."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import fleet

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parents[1]


def run(output, installed=False):
    registry = ROOT / "skill-fleet/registry.json"
    registry_before = fleet.sha256(registry)
    gate_before = {p.name: fleet.sha256(p) for p in sorted((ROOT / "skill-fleet").glob("*.py"))}
    errors = fleet.validate(registry, repository_only=not installed)
    records = [r for r in fleet.records(registry) if r.canonical.is_relative_to(ROOT / "skill-packages")]
    before = {r.skill_id: fleet.tree_sha256(r.canonical) for r in records}
    results = []
    directories = {ROOT / "skill-fleet"}
    for record in records:
        if record.test_class == "fixture":
            directories.update(p.parent for p in record.canonical.rglob("test_*.py"))
    environment = dict(os.environ); environment["PYTHONDONTWRITEBYTECODE"] = "1"
    # Admission is fail closed. Do not execute newly discovered or hash-drifted scripts.
    if not errors:
        for directory in sorted(directories):
            command = [sys.executable, "-m", "unittest", "discover", "-s", str(directory), "-p", "test_*.py"]
            started = time.monotonic()
            try:
                completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                           timeout=180, shell=False, env=environment)
                text = completed.stdout + completed.stderr
                result = {"directory": directory.relative_to(ROOT).as_posix(), "exit_code": completed.returncode,
                          "seconds": round(time.monotonic() - started, 3), "output": text,
                          "output_sha256": hashlib.sha256(text.encode()).hexdigest()}
            except subprocess.TimeoutExpired:
                result = {"directory": directory.relative_to(ROOT).as_posix(), "exit_code": 124, "error": "suite timeout"}
            results.append(result)
    after = {r.skill_id: fleet.tree_sha256(r.canonical) for r in records}
    if before != after: errors.append("source changed during fixture execution")
    if registry_before != fleet.sha256(registry): errors.append("registry changed during fixture execution")
    if gate_before != {p.name: fleet.sha256(p) for p in sorted((ROOT / "skill-fleet").glob("*.py"))}:
        errors.append("gate or fleet tests changed during fixture execution")
    receipt = {"schema": "fleet-local-receipt/v1", "scope": "installed-and-repository" if installed else "portable-repository-only",
        "status": "PASS" if not errors and results and all(r["exit_code"] == 0 for r in results) else "FAIL",
        "registry_sha256": registry_before, "gate_files": gate_before, "packages": before, "suites": results, "errors": errors,
        "authority": "none", "signer_scope": "ephemeral-local-test-only; organizational authentication not established"}
    key = Ed25519PrivateKey.generate()
    encoded = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    signed = {"receipt": receipt, "signature": base64.b64encode(key.sign(encoded)).decode(),
              "public_key": base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(signed, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "suites": len(results), "errors": errors,
                      "failed": [r["directory"] for r in results if r["exit_code"]], "receipt": str(output)}, indent=2))
    return receipt["status"] == "PASS"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True); parser.add_argument("--installed", action="store_true")
    args = parser.parse_args(); raise SystemExit(0 if run(args.output, args.installed) else 1)
