#!/usr/bin/env python3
"""Portable enterprise assurance CLI. No provider calls, arbitrary scripts or deployment."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from enterprise_assurance.common import AssuranceError, PACKAGE, bundle_digest, digest, read
from enterprise_assurance.engine import Engine
from enterprise_assurance.operations import export_pack, help_receipt, register_schedule, request_help, tick


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["identity", "plan", "continue", "run", "ingest", "risk", "challenge", "waiver", "decide", "resume", "operate", "inspect", "export", "help-request", "help-receipt", "schedule", "tick"])
    parser.add_argument("--state", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--trust", type=Path, help="Operator-protected trust/revocation configuration")
    parser.add_argument("--trust-sha", help="Canonical JSON digest obtained through an independently trusted channel")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--subject", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--parent-goal")
    parser.add_argument("--parent-run")
    parser.add_argument("--criterion", action="append")
    parser.add_argument("--engine", choices=["codex-product-build-loop", "product-loop", "agentic-product-loop"])
    parser.add_argument("--blob-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "identity":
            result = {"version": "1.0.0", "verifier_sha": bundle_digest(), "authority": "none"}
        else:
            if not args.state or not args.trust or not args.trust_sha:
                raise AssuranceError("--state, --trust and --trust-sha are required; evidence cannot provide its own trust root")
            engine = Engine(args.state, read(args.trust), args.trust_sha)
            if args.command != "tick" and not args.run_id: raise AssuranceError("--run-id required")
            if args.command == "plan":
                if not all((args.subject, args.profile, args.parent_goal, args.criterion, args.engine)):
                    raise AssuranceError("plan needs subject, profile, parent goal, criteria and one delivery engine")
                result = engine.admit(args.run_id, read(args.subject), read(args.profile), args.parent_goal, args.criterion, args.engine)
            elif args.command == "continue":
                if not all((args.parent_run, args.subject, args.profile, args.input)):
                    raise AssuranceError("continue needs --parent-run, --subject, --profile and signed --input migration")
                result = engine.continue_run(args.parent_run, args.run_id, read(args.subject), read(args.profile), read(args.input))
            elif args.command == "run":
                # Fixed repository test invocation only. This cannot create product evidence.
                engine.plan(args.run_id)
                env = dict(os.environ); env["PYTHONDONTWRITEBYTECODE"] = "1"
                completed = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(PACKAGE / "tests"), "-p", "test_*.py"],
                                           capture_output=True, text=True, timeout=120, env=env, shell=False)
                result = {"status": "PASS" if completed.returncode == 0 else "FAIL", "scope": "assurance-platform-fixtures",
                          "exit_code": completed.returncode, "output": completed.stdout + completed.stderr,
                          "verifier_sha": bundle_digest(), "authority": "none", "product_evidence_created": False}
            elif args.command == "ingest":
                if not args.input or not args.blob_dir: raise AssuranceError("ingest needs --input and content-addressed --blob-dir")
                envelope = read(args.input); hashes = envelope["body"]["payload"]["raw_manifest"].values()
                import re
                blobs = {}
                for sha in hashes:
                    if not re.fullmatch("[0-9a-f]{64}", sha): raise AssuranceError("unsafe blob path")
                    path = args.blob_dir / sha
                    if path.is_symlink() or path.stat().st_size > 16_000_000: raise AssuranceError("unsafe blob file")
                    blobs[sha] = path.read_bytes()
                result = engine.ingest(args.run_id, envelope, blobs)
            elif args.command in {"risk", "challenge", "waiver", "resume", "operate", "help-request", "help-receipt", "schedule"}:
                if not args.input: raise AssuranceError("--input required")
                item = read(args.input)
                if args.command in {"resume", "operate"}:
                    if args.command == "resume" and item["body"]["payload"]["action"] != "RESUME": raise AssuranceError("resume requires signed RESUME")
                    result = engine.operate(args.run_id, item)
                elif args.command == "help-request": result = request_help(engine, args.run_id, item)
                elif args.command == "help-receipt": result = help_receipt(engine, args.run_id, item)
                elif args.command == "schedule": result = register_schedule(engine, args.run_id, item)
                else: result = getattr(engine, {"risk": "record_risk"}.get(args.command, args.command))(args.run_id, item)
            elif args.command == "decide": result = engine.decide(args.run_id)
            elif args.command == "inspect": result = engine.inspect(args.run_id)
            elif args.command == "tick": result = tick(engine)
            else:
                if not args.output: raise AssuranceError("export needs --output")
                result = export_pack(engine, args.run_id, args.output)
        print(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False))
        return 1 if result.get("status") == "FAIL" or result.get("decision") in {"NO_GO", "ESCALATE"} else 0
    except (AssuranceError, OSError, KeyError, TypeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "INVALID_OR_BLOCKED", "error": str(exc), "authority": "none"}))
        return 2


if __name__ == "__main__": raise SystemExit(main())
