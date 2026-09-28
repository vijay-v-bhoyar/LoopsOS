#!/usr/bin/env python3
"""product-diligence pipeline driver.

Orchestration is a linear DAG with one fan-out (six lenses) and one fresh-context
step (challenge). That does not need a graph framework; this is a stdlib script
(the framework decision, item 15). It owns everything deterministic — state,
stage contracts, token scoping, fingerprint dedup, and the render gate — and
leaves exactly two steps to a model via a manual seam: the sweep (Phase 1) and
the challenge (Phase 3). Each emits a payload file; the operator (or a ~30-line
model adapter) runs it and drops the response back for ingest.

Token discipline (item 14): the six lenses carry no artifacts, only the register
(derive.py) — adding artifacts or lenses never grows per-lens context. The sweep
and challenge payloads DO carry artifacts, so this module bounds them three ways:
per-artifact truncation with a disclosed marker (never silent), a size warning
recommending grouped (chunked) sweeps for large artifact sets, and a challenge
payload that summarizes already-settled register rows by count instead of
re-embedding them every cycle (PIPELINE.md has the full rationale).

Commands:
  init --map map.json [--config cfg.json]      build manifest (Phase 0)
  admit                                         per-lens coverage vs floors
  status                                        state + staleness + next command, no model call
  sweep-groups                                  per-group size estimate for planning a chunked sweep
  sweep-payload [--group NAME]                  emit Phase 1 model payload (NAME or 'all')
  ingest-findings findings.json                 validate + fingerprint-dedup + append
  derive                                        compute verdicts + scorecard (Phase 2)
  challenge-payload                             emit Phase 3 model payload (settled rows summarized)
  ingest-challenges challenges.json             validate + append
  reconcile                                     auto-accept unresolved + re-derive (Phase 4)
  check [--verbose]                             run the P1-P10 gate (terse by default)
  render [--verbose]                            gate on green, write scorecard/register/lenses .md
  rerun --map map.json                          diff-mode re-run (Phase 0 diff)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import derive as D

HERE = Path(__file__).resolve().parent
ROOT = HERE
STATE = Path(".diligence")

# --- size budgets (rough heuristic: 4 chars/token, stated as an approximation
# everywhere it's surfaced, never presented as an exact count) ---------------
CHARS_PER_TOKEN_EST = 4
MAX_ARTIFACT_CHARS = 40_000       # ~10K tokens per artifact before truncation
SWEEP_WARN_CHARS = 60_000         # ~15K tokens total before recommending --group

def estimate_tokens(chars: int) -> int:
    return chars // CHARS_PER_TOKEN_EST


# Sweep chunking. A grouping concern belongs here, not in rules.json — rules.json
# is the verdict-derivation source of truth (item ownership stays crisp); this is
# purely about bounding one payload's size. Groups may overlap on shared layers
# (e.g. L11 policy touches both security and product framing); fingerprint dedup
# on ingest (impact_class + citation target, not group) makes overlap harmless.
SURFACE_GROUPS = {
    "model_evolution": {
        "title": "Model evolution and measured product improvement",
        "layers": ["L10", "L11", "L12", "L18", "L19", "L20"],
        "vectors": [f"E-{i:02d}" for i in range(1, 9)] + ["S-11"],
        "controls": ["MC-5", "MC-6", "MC-7"],
        "artifacts": ["A-03", "A-05", "A-10", "A-11", "A-15", "A-17", "A-19"],
    },
    "security_and_data": {
        "title": "Security, identity, tenancy & data",
        "layers": ["L06", "L07", "L08", "L09", "L13", "L14", "L15"],
        "vectors": ["V-01", "V-02", "V-03", "V-04", "V-05", "V-06", "V-07", "V-10", "V-15"],
        "controls": ["MC-1", "MC-2", "MC-3", "MC-4", "MC-6"],
        "artifacts": ["A-04", "A-06", "A-07", "A-08", "A-09", "A-10", "A-11", "A-16", "A-21"],
    },
    "product_and_strategy": {
        "title": "Product, UX, orchestration depth & strategic positioning",
        "layers": ["L01", "L02", "L03", "L10", "L11"],
        "vectors": ["S-01", "S-02", "S-03", "S-04", "S-05", "S-06", "S-07", "S-08", "S-09", "S-10", "S-11"],
        "controls": [],
        "artifacts": ["A-01", "A-02", "A-03", "A-09", "A-10", "A-19", "A-20"],
    },
    "ops_and_release": {
        "title": "API, execution, observability, autonomy controls & release",
        "layers": ["L04", "L05", "L12", "L16", "L17", "L18", "L19", "L20"],
        "vectors": ["V-08", "V-09", "V-11", "V-12", "V-13", "V-14"],
        "controls": ["MC-5", "MC-7"],
        "artifacts": ["A-05", "A-10", "A-12", "A-13", "A-14", "A-15", "A-16", "A-17", "A-18"],
    },
}


# --- helpers -----------------------------------------------------------------

def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def rules_path() -> Path:
    return ROOT / "rules.json"


def load_manifest() -> dict:
    return json.loads((STATE / "manifest.json").read_text(encoding="utf-8"))


def _config(path: str | None) -> dict:
    config = json.loads(Path(path).read_text(encoding="utf-8")) if path else {}
    ref = config.get("model_evolution")
    if ref and path:
        ref = dict(ref)
        resolved = (Path(path).resolve().parent / ref["path"]).resolve()
        ref["path"] = resolved.relative_to(STATE.resolve()).as_posix()
        config["model_evolution"] = ref
    return config


def _review_binding() -> dict:
    return {"manifest": sha256_file(STATE / "manifest.json"),
            "register": sha256_file(STATE / "register.jsonl"),
            "rules": sha256_file(rules_path()),
            "sweep_prompt": sha256_file(ROOT / "sweep.md"),
            "challenge_prompt": sha256_file(ROOT / "challenge.md")}


def _clear_views() -> None:
    for name in ("verdicts.jsonl", "scorecard.json", "scorecard.md", "register.md", "lenses.md", "challenge-receipt.json"):
        (STATE / name).unlink(missing_ok=True)


def next_id(prefix: str, existing: set[str]) -> str:
    n = 1
    while f"{prefix}-{n:02d}" in existing:
        n += 1
    return f"{prefix}-{n:02d}"


TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".ts", ".tsx",
                 ".js", ".sql", ".toml", ".ini", ".cfg", ".env", ".sh"}


# --- fingerprint (INV-1: dedup at write) -------------------------------------

def citation_key(cite: str) -> str:
    """Normalize a citation to its target: artifact id + path without line range."""
    if ":" not in cite:
        return cite.strip().lower()
    art, tail = cite.split(":", 1)
    tail = re.sub(r"#L\d+(-L?\d+)?$", "", tail)  # strip line range from code cites
    return f"{art.strip()}:{tail.strip()}".lower()


def fingerprint(row: dict) -> str:
    surface = (row.get("surface") or ["?"])[0]
    impact = (row.get("impact_class") or "?")
    cites = row.get("citations") or [""]
    key = f"{surface}|{impact}|{citation_key(cites[0])}"
    return "sha256:" + sha256_text(key)


# --- Phase 0: init -----------------------------------------------------------

def cmd_init(args) -> int:
    mapping = json.loads(Path(args.map).read_text(encoding="utf-8"))
    config = _config(args.config)
    if (STATE / "manifest.json").exists():
        raise ValueError("Existing diligence state: use rerun; init cannot overwrite history")
    STATE.mkdir(exist_ok=True)
    (STATE / "payloads").mkdir(exist_ok=True)

    artifacts = {}
    for aid, path in mapping.items():
        p = Path(path).resolve()
        if not p.exists():
            print(f"ERROR: artifact {aid} path not found: {path}", file=sys.stderr)
            return 2
        artifacts[aid] = {"path": str(p), "sha256": sha256_file(p)}

    manifest = {
        "schema_version": 2,
        "run": "run-001",
        "assessed_at": datetime.now(timezone.utc).isoformat(),
        "rules_sha256": sha256_file(rules_path()),
        "prompt_hashes": {n: sha256_file(ROOT / n) for n in ("sweep.md", "challenge.md")},
        "subject": config.get("subject"),
        "model_evolution": config.get("model_evolution"),
        "pending_revalidation": [],
        "artifacts": artifacts,
        "params": {
            "owner_roster": config.get("owner_roster", []),
            "release_calendar": config.get("release_calendar"),
            "valuation": config.get("valuation"),
        },
        "model_pins": config.get("model_pins", {}),
        "prior_manifest_sha256": None,
    }
    (STATE / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for f in ("register.jsonl", "verdicts.jsonl", "challenges.jsonl"):
        (STATE / f).touch(exist_ok=True)
    print(f"Initialized {len(artifacts)} artifacts. Model pins: {manifest['model_pins'] or 'NONE (required before render)'}")
    return 0


# --- Phase 0: admit ----------------------------------------------------------

def cmd_admit(args) -> int:
    rules = json.loads(rules_path().read_text(encoding="utf-8"))
    present = set(load_manifest().get("artifacts", {}).keys())
    print(f"{'Lens':<6} {'floor':<7} {'coverage':<9} note")
    for dim in ["D1", "D2", "D3", "D4", "D5", "D6"]:
        ok, cov = D.floor_and_coverage(dim, present, rules)
        note = "" if ok else D._skip_note(dim, present, rules)
        print(f"{dim:<6} {'OK' if ok else 'SKIP':<7} {cov:<9} {note}")
    return 0


# --- Phase 1: sweep ----------------------------------------------------------

def _artifact_block(artifacts: dict, only: set[str] | None = None,
                     max_chars: int = MAX_ARTIFACT_CHARS) -> str:
    parts = []
    for aid, meta in sorted(artifacts.items()):
        if only is not None and aid not in only:
            continue
        p = Path(meta["path"])
        if sha256_file(p) != meta["sha256"]:
            raise ValueError(f"{aid}: artifact changed; use rerun before creating a payload")
        header = f"\n----- {aid} : {p.name} (sha256 {meta['sha256'][:12]}) -----"
        if p.suffix.lower() in TEXT_SUFFIXES:
            try:
                body = p.read_text(encoding="utf-8", errors="replace")
            except Exception as e:  # noqa: BLE001 - surface as text, never crash the payload
                body = f"[unreadable as text: {e}]"
            if max_chars and len(body) > max_chars:
                omitted = len(body) - max_chars
                body = (
                    body[:max_chars]
                    + f"\n\n[... TRUNCATED: {omitted} more characters "
                      f"(~{estimate_tokens(omitted)} tokens est.) omitted here. This artifact "
                      f"is too large for one sweep call — findings citing content past this "
                      f"point cannot be produced from this payload. Pre-excerpt the relevant "
                      f"sections into a smaller file and remap it, or accept partial coverage "
                      f"and note the gap as `unknown` with this artifact cited.]"
                )
            parts.append(f"{header}\n{body}")
        else:
            parts.append(f"{header}\n[binary/non-text artifact; read from {p} before the sweep]")
    return "\n".join(parts)


def cmd_sweep_groups(args) -> int:
    """Per-group size estimate for planning a chunked sweep — no model call, no state
    write. Reports RAW artifact sizes (before per-artifact truncation): a raw
    oversized artifact is the actionable signal. Pre-excerpting it once benefits
    every group that cites it, whereas reporting only post-truncation sizes would
    hide which specific artifact was actually the problem."""
    manifest = load_manifest()
    present = set(manifest["artifacts"].keys())

    def text_size(aid: str) -> int:
        p = Path(manifest["artifacts"][aid]["path"])
        return p.stat().st_size if p.suffix.lower() in TEXT_SUFFIXES else 0

    sizes = {a: text_size(a) for a in present}
    oversized = {a: s for a, s in sizes.items() if s > MAX_ARTIFACT_CHARS}

    total = sum(sizes.values())
    rec = "single call is fine" if total <= SWEEP_WARN_CHARS else "OVER threshold — use --group"
    print(f"{'ALL (single call)':<20} raw ~{estimate_tokens(total):>7} tokens est.  {rec}")
    for name, g in SURFACE_GROUPS.items():
        ids = sorted((set(g["artifacts"]) & present) | ({a for a in present if a not in {f"A-{i:02d}" for i in range(1, 22)}} if name == "model_evolution" else set()))
        size = sum(sizes[a] for a in ids)
        hits = [a for a in ids if a in oversized]
        flag = f"  [oversized: {', '.join(hits)}]" if hits else ""
        print(f"{name:<20} raw ~{estimate_tokens(size):>7} tokens est.  artifacts={ids or 'none present'}{flag}")

    if oversized:
        cap_tok = estimate_tokens(MAX_ARTIFACT_CHARS)
        print(f"\nOversized (> ~{cap_tok} tokens est.), truncated to ~{cap_tok} tokens per sweep call "
              f"regardless of grouping — pre-excerpt these once and every group above improves:")
        for a, s in sorted(oversized.items()):
            print(f"  {a}: raw ~{estimate_tokens(s)} tokens est.")
    return 0


def cmd_sweep_payload(args) -> int:
    manifest = load_manifest()
    rules = json.loads(rules_path().read_text(encoding="utf-8"))
    present = set(manifest["artifacts"].keys())
    admitted = {d for d in ["D1", "D2", "D3", "D4", "D5", "D6"]
                if D.floor_and_coverage(d, present, rules)[0]}
    template = (ROOT / "sweep.md").read_text(encoding="utf-8")

    group = getattr(args, "group", None) or "all"
    if group != "all" and group not in SURFACE_GROUPS:
        print(f"ERROR: unknown group '{group}'. Choose from: {', '.join(SURFACE_GROUPS)}, or 'all'.",
              file=sys.stderr)
        return 2

    if group == "all":
        artifact_ids, scope_note, out_name = None, "", "sweep.md"
    else:
        g = SURFACE_GROUPS[group]
        artifact_ids = set(g["artifacts"]) & present
        if group == "model_evolution":
            artifact_ids |= present - {f"A-{i:02d}" for i in range(1, 22)}
        scope_note = (
            f"\n\n## Scope for this call: {g['title']}\n"
            f"This is one of several chunked sweep calls. Cover ONLY this surface in this "
            f"call — other groups cover the rest in separate calls; do not force-fit findings "
            f"outside this scope, and do not re-derive verdicts (that is Phase 2, not this step).\n"
            f"Layers: {', '.join(g['layers'])}\n"
            f"Vectors: {', '.join(g['vectors'])}\n"
            f"Controls: {', '.join(g['controls']) or 'none in this group'}\n"
        )
        out_name = f"sweep-{group}.md"

    payload = (
        template
        + "\n\n## Admitted lenses (only produce findings for surfaces these cover)\n"
        + ", ".join(sorted(admitted))
        + scope_note
        + "\n\n## Supplied artifacts\n"
        + _artifact_block(manifest["artifacts"], only=artifact_ids)
    )
    out = STATE / "payloads" / out_name
    out.write_text(payload, encoding="utf-8")
    size = len(payload)
    print(f"Wrote {out} ({size} chars, ~{estimate_tokens(size)} tokens est.). "
          f"Run it against the pinned sweep model, save the JSON findings array, "
          f"then: orchestrate ingest-findings <file>")
    if group == "all" and size > SWEEP_WARN_CHARS:
        print(f"WARNING: payload is large (~{estimate_tokens(size)} tokens est., threshold "
              f"~{estimate_tokens(SWEEP_WARN_CHARS)}). Run `orchestrate sweep-groups` for a "
              f"per-group breakdown, then sweep each with --group <name> instead of one call.",
              file=sys.stderr)
    return 0


# --- Phase 1: ingest ---------------------------------------------------------

REQUIRED_FINDING_FIELDS = ("type", "title", "surface", "dimensions", "evidence_mode", "verifiability")


def _load_json_array_or_die(path: Path, stage: str) -> list:
    """Parse a model-response JSON array with an actionable error, not a raw traceback —
    truncated/fenced output is the realistic failure mode a large single-call sweep risks."""
    raw = path.read_text(encoding="utf-8").strip()
    if raw.startswith("```"):
        raw = re.sub(r'^```[a-zA-Z]*\n', '', raw)
        raw = re.sub(r'\n?```$', '', raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: {path} is not valid JSON ({e}).", file=sys.stderr)
        print(f"This usually means the {stage} model response was truncated (a real risk "
              f"with a large single-call sweep — see `orchestrate sweep-groups`) or the file "
              f"has stray text around the JSON array. Fix the file and re-run, or re-sweep with "
              f"--group <name> for a smaller, less truncation-prone call.", file=sys.stderr)
        sys.exit(2)
    if not isinstance(data, list):
        print(f"ERROR: {path} must be a JSON array of objects, got {type(data).__name__}.",
              file=sys.stderr)
        sys.exit(2)
    return data


def cmd_ingest_findings(args) -> int:
    incoming = _load_json_array_or_die(Path(args.file), "sweep")
    register = D.load_jsonl(STATE / "register.jsonl")
    manifest = load_manifest()
    pending = set(manifest.get("pending_revalidation", []))
    by_fp = {r.get("fingerprint"): r for r in register}
    ids = {r["id"] for r in register}

    # Validate the complete batch before changing any state.
    for row in incoming:
        if not isinstance(row, dict) or any(f not in row for f in REQUIRED_FINDING_FIELDS):
            raise ValueError("Malformed finding: required fields absent")
        if row.get("type") not in {"risk", "strength", "unknown"}:
            raise ValueError("Unsupported finding type")
        if row["type"] != "unknown" and not row.get("citations"):
            raise ValueError("A risk or strength needs current artifact citations")
        for citation in row.get("citations", []):
            if not isinstance(citation, str) or ":" not in citation or citation.split(":", 1)[0] not in manifest["artifacts"] or not citation.split(":", 1)[1].strip():
                raise ValueError("Finding cites an absent artifact or empty locator")
        target = row.get("revalidates")
        if target is not None and target not in pending:
            raise ValueError("revalidates must name a pending finding")
        if row.get("status", "open") != "open":
            raise ValueError("Sweep ingestion cannot close or accept a risk; supply closure proof separately")

    added = merged = 0
    for row in incoming:
        missing = [f for f in REQUIRED_FINDING_FIELDS if f not in row]
        if missing:
            print(f"SKIP malformed finding {row.get('title','?')!r}: missing {missing}", file=sys.stderr)
            continue
        row.setdefault("status", "open")
        row.setdefault("citations", [])
        row.setdefault("owner", "Owner unknown")
        row["fingerprint"] = fingerprint(row)

        target = row.pop("revalidates", None)
        if target:
            existing = next(r for r in register if r["id"] == target)
            previous = dict(existing)
            by_fp.pop(existing.get("fingerprint"), None)
            row["id"] = target
            row["history"] = [*existing.get("history", []),
                              {"run": manifest["run"], "event": "revalidated", "previous": previous}]
            existing.clear()
            existing.update(row)
            by_fp[row["fingerprint"]] = existing
            pending.remove(target)
            merged += 1
            continue

        existing = by_fp.get(row["fingerprint"])
        if existing:  # dedup at write: extend surfaces/dimensions, never a 2nd row
            if existing["id"] in pending:
                raise ValueError(f"Explicit revalidates:{existing['id']} required for stale evidence")
            existing["surface"] = sorted(set(existing.get("surface", [])) | set(row.get("surface", [])))
            existing["dimensions"] = sorted(set(existing.get("dimensions", [])) | set(row.get("dimensions", [])))
            existing.setdefault("history", []).append({"run": load_manifest()["run"], "event": "merged-duplicate"})
            merged += 1
            continue

        row["id"] = next_id("R" if row["type"] == "risk" else
                                            ("S" if row["type"] == "strength" else "U"), ids)
        ids.add(row["id"])
        row.setdefault("history", [{"run": load_manifest()["run"], "event": "created"}])
        register.append(row)
        by_fp[row["fingerprint"]] = row
        added += 1

    _write_jsonl(STATE / "register.jsonl", register)
    manifest["pending_revalidation"] = sorted(pending)
    (STATE / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _clear_views()
    print(f"Ingested: {added} new rows, {merged} merged into existing (fingerprint dedup).")

    # Fingerprint dedup only catches exact restatements. A reworded duplicate that
    # cites the same target with the same impact class escapes it (demonstrated:
    # a tenant-leak restated under a different primary surface). Auto-merging on
    # citation alone would wrongly collapse distinct issues sharing one doc section,
    # so surface these as operator-confirmed merge candidates instead.
    for a, b in _semantic_dup_candidates(register):
        print(f"  POSSIBLE DUPLICATE: {a} ~ {b} (same impact_class + citation target). "
              f"Confirm and merge by hand if they are the same defect.", file=sys.stderr)
    return 0


def _semantic_dup_candidates(register: list[dict]) -> list[tuple[str, str]]:
    seen: dict[tuple[str, str], str] = {}
    pairs = []
    for r in register:
        if r.get("type") != "risk":
            continue
        impact = r.get("impact_class")
        for c in r.get("citations", []):
            key = (impact, citation_key(c))
            prior = seen.get(key)
            if prior and prior != r["id"]:
                pairs.append((prior, r["id"]))
            seen.setdefault(key, r["id"])
    return sorted(set(pairs))


# --- Phase 2: derive ---------------------------------------------------------

def cmd_derive(args) -> int:
    return subprocess.call([sys.executable, "-B", str(HERE / "derive.py"),
                            "--dir", str(STATE), "--rules", str(rules_path()), "--print"])


# --- Phase 3: challenge ------------------------------------------------------

def _settled_summary(register: list[dict]) -> tuple[str, str]:
    """Split the register into what the challenger needs to see (live rows: every
    strength/unknown, plus risks still open or pending proof) versus what it doesn't
    (risk rows already closed-with-proof or accepted-with-expiry). Lifecycle status
    is a risk-row concept — strength/unknown rows carry `status` only for schema
    uniformity and are never filtered here, matching the SKILL.md data contract.
    Settled rows already passed their proof gate; re-litigating them every cycle
    burns tokens without giving the challenger anything new to attack, so they are
    summarized by count instead of re-embedded (bounds payload growth as the
    register accumulates across many re-runs)."""
    live, settled = [], []
    for r in register:
        if r.get("type") == "risk" and r.get("status") in {"closed", "accepted"} and not D.is_open_risk(r):
            settled.append(r)
        else:
            live.append(r)
    text = "\n".join(json.dumps(r) for r in live)
    if settled:
        n_closed = sum(1 for r in settled if r["status"] == "closed")
        n_accepted = len(settled) - n_closed
        text += (f"\n// {len(settled)} risk rows omitted as already settled "
                 f"({n_closed} closed with executed proof, {n_accepted} accepted with "
                 f"owner+expiry). Full history is in register.md if you need to challenge "
                 f"how one of these was settled — that is a valid 'unsupported' or 'excused' "
                 f"target, just name the row ID from register.md rather than assuming.")
    return text, f"{len(live)} live rows, {len(settled)} settled rows omitted from payload"


def cmd_challenge_payload(args) -> int:
    manifest = load_manifest()
    template = (ROOT / "challenge.md").read_text(encoding="utf-8")
    register = D.load_jsonl(STATE / "register.jsonl")
    register_text, summary_line = _settled_summary(register)
    verdicts = (STATE / "verdicts.jsonl").read_text(encoding="utf-8")
    payload = (
        template
        + "\n\n## Verdict records to challenge\n```jsonl\n" + verdicts + "\n```"
        + "\n\n## Register (the evidence — " + summary_line + ")\n```jsonl\n" + register_text + "\n```"
        + "\n\n## Supplied artifacts\n" + _artifact_block(manifest["artifacts"])
    )
    out = STATE / "payloads" / "challenge.md"
    out.write_text(payload, encoding="utf-8")
    pins = manifest.get("model_pins", {})
    size = len(payload)
    print(f"Wrote {out} ({size} chars, ~{estimate_tokens(size)} tokens est.; {summary_line}). "
          f"Run against a DIFFERENT model pin than the sweep "
          f"(sweep={pins.get('sweep','?')}, challenge={pins.get('challenge','?')}) "
          f"for de-correlation, then: orchestrate ingest-challenges <file>")
    return 0


def cmd_ingest_challenges(args) -> int:
    incoming = _load_json_array_or_die(Path(args.file), "challenge")
    existing = D.load_jsonl(STATE / "challenges.jsonl")
    ids = {c["id"] for c in existing}
    for c in incoming:
        c["id"] = c.get("id") or next_id("C", ids)
        ids.add(c["id"])
        existing.append(c)
    _write_jsonl(STATE / "challenges.jsonl", existing)
    (STATE / "challenge-receipt.json").write_text(json.dumps({
        "binding": _review_binding(), "response_sha256": sha256_file(Path(args.file)),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "independence_verified": False}, indent=2), encoding="utf-8")
    print(f"Ingested {len(incoming)} challenges.")
    return 0


# --- Phase 4: reconcile ------------------------------------------------------

def cmd_reconcile(args) -> int:
    challenges = D.load_jsonl(STATE / "challenges.jsonl")
    auto = 0
    for c in challenges:
        res = c.get("resolution")
        if not res or res.get("kind") not in {"upheld", "revised", "accepted"}:
            c["resolution"] = {"kind": "accepted", "reason": "auto: unresolved challenge fails closed"}
            auto += 1
    _write_jsonl(STATE / "challenges.jsonl", challenges)
    print(f"Reconciled: {auto} unresolved challenges auto-accepted (fail closed). Re-deriving.")
    if auto:
        print("NOTE: 'revised' resolutions require the operator to edit the cited register "
              "rows; auto-accept only downgrades verdicts, it does not rewrite findings.")
    return cmd_derive(args)


# --- gate + render -----------------------------------------------------------

def cmd_check(args) -> int:
    cmd = [sys.executable, "-B", str(HERE / "diligence_check.py"), "--dir", str(STATE), "--rules", str(rules_path())]
    if getattr(args, "verbose", False):
        cmd.append("--verbose")
    return subprocess.call(cmd)


def cmd_render(args) -> int:
    if load_manifest().get("pending_revalidation"):
        raise ValueError("Revalidate all pending findings before render")
    receipt = STATE / "challenge-receipt.json"
    if not receipt.exists() or json.loads(receipt.read_text(encoding="utf-8")).get("binding") != _review_binding():
        raise ValueError("Fresh challenge ingestion required for this manifest, register, rules and prompts")
    rc = cmd_derive(args)  # freshen verdicts + scorecard from the current register
    if rc:
        return rc
    rc = cmd_check(args)
    if rc != 0:
        print("\nRefusing to render: checker is RED (INV-14). Re-run with --verbose for full detail.",
              file=sys.stderr)
        return rc
    sc = json.loads((STATE / "scorecard.json").read_text(encoding="utf-8"))
    register = D.load_jsonl(STATE / "register.jsonl")
    rules = json.loads(rules_path().read_text(encoding="utf-8"))
    _render_scorecard(sc)
    _render_register(register)
    _render_lenses(sc, register, rules)
    print(f"Rendered {STATE/'scorecard.md'}, {STATE/'register.md'}, {STATE/'lenses.md'}")
    return 0


# --- status: re-entry without conversational memory --------------------------

def cmd_status(args) -> int:
    """Cheap, model-free state report. Reuses derive.py's own rederivation (the
    same function P4 uses) to detect staleness rather than tracking a second
    'is this current' signal — one source of truth. Exists so a fresh session
    (or a fresh subagent with no memory of prior turns) can run one command and
    know exactly what to do next, instead of the operator/agent having to hold
    the phase sequence in its own context across a long or interrupted run."""
    if not (STATE / "manifest.json").exists():
        print("No .diligence/ state found here. Start with: orchestrate init --map map.json --config config.json")
        return 0

    manifest = load_manifest()
    errors = D.manifest_integrity_errors(manifest, STATE, rules_path())
    if errors:
        print("Evidence needs refresh: " + "; ".join(errors))
        return 2
    if manifest.get("pending_revalidation"):
        print("Pending revalidation: " + ", ".join(manifest["pending_revalidation"]))
    rules = json.loads(rules_path().read_text(encoding="utf-8"))
    register = D.load_jsonl(STATE / "register.jsonl")
    challenges = D.load_jsonl(STATE / "challenges.jsonl")
    stored_verdicts = D.load_jsonl(STATE / "verdicts.jsonl")
    present = set(manifest.get("artifacts", {}).keys())

    print(f"Run: {manifest.get('run')}  |  Artifacts: {len(present)}  "
          f"|  Model pins: {manifest.get('model_pins') or 'NONE SET (required before render)'}")

    n_open = sum(1 for r in register if r.get("status") == "open")
    n_settled = sum(1 for r in register if r.get("status") in {"closed", "accepted"})
    print(f"Register: {len(register)} rows ({n_open} open, {n_settled} settled)")

    unresolved = sum(1 for c in challenges if (c.get("resolution") or {}).get("kind") not in
                     {"upheld", "revised", "accepted"})
    print(f"Challenges: {len(challenges)} ({unresolved} unresolved -> auto-accept on reconcile)")

    stale = False
    if stored_verdicts:
        derived = D.derive_all(register, rules, manifest, challenges, base_dir=STATE)["verdicts"]
        dmap = {v["lens"]: (v.get("verdict"), v.get("rule")) for v in derived}
        smap = {v["lens"]: (v.get("verdict"), v.get("rule")) for v in stored_verdicts}
        stale = any(smap.get(lens) != dv for lens, dv in dmap.items())
    print(f"Verdicts: {'STALE (register changed since last derive)' if stale else 'current' if stored_verdicts else 'not yet computed'}")

    if not register:
        nxt = "sweep-payload"
    elif not stored_verdicts or stale:
        nxt = "derive"
    elif not (STATE / "challenge-receipt.json").exists():
        nxt = "challenge-payload"
    elif unresolved:
        nxt = "reconcile"
    else:
        nxt = "render"
    print(f"Next: orchestrate {nxt}")
    if nxt == "render" and (STATE / "scorecard.json").exists() and not stale:
        print("  (scorecard already rendered this cycle; re-run render only after further changes, "
              "or `orchestrate rerun --map map.json` to start a new diff-mode cycle)")

    if nxt == "sweep-payload":
        total = sum(Path(m["path"]).stat().st_size for a, m in manifest["artifacts"].items()
                    if Path(m["path"]).suffix.lower() in TEXT_SUFFIXES)
        hint = "single call is fine" if total <= SWEEP_WARN_CHARS else "run `sweep-groups` first, use --group"
        print(f"  Estimated sweep payload: ~{estimate_tokens(total)} tokens est. ({hint})")
    return 0


def _render_scorecard(sc: dict) -> None:
    lines = ["# Executive scorecard\n",
             f"Run: {load_manifest().get('run')} | Manifest SHA256: {sha256_file(STATE / 'manifest.json')}\n",
             "Historical snapshot: revalidate changed or expired evidence before use.\n",
             "| Dimension | Verdict | Score | Confidence | Top blocker |",
             "|---|---|---|---|---|"]
    for row in sc["scorecard"]:
        score = row["score"] if row["score"] is not None else "–"
        conf = row["confidence"] or "–"
        blk = row["top_blocker"] or "–"
        lines.append(f"| {row['dimension']} | {row['verdict']} | {score} | {conf} | {blk} |")
    lines.append(f"\n_Valuation mode: {'on' if sc.get('valuation_mode') else 'off (posture only)'}._")
    evolution = sc.get("evolution", {})
    lines += ["\n## Model evolution", f"Capability assessment: {evolution.get('status', 'EVIDENCE_MISSING')}",
              "This report does not authorize model promotion or deployment.",
              "```json", json.dumps(evolution, indent=2), "```"]
    (STATE / "scorecard.md").write_text("\n".join(lines), encoding="utf-8")


def _render_register(register: list[dict]) -> None:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, None: 4}
    risks = sorted([r for r in register if r.get("type") == "risk"],
                   key=lambda r: (order.get(r.get("severity"), 4), r["id"]))
    lines = ["# Master risk register\n",
             "| ID | Title | Surface | Severity | Evidence | Status | Citations |",
             "|---|---|---|---|---|---|---|"]
    for r in risks:
        lines.append(f"| {r['id']} | {r['title']} | {','.join(r.get('surface',[]))} | "
                     f"{r.get('severity')} | {r.get('evidence_mode')} | {r.get('status')} | "
                     f"{'; '.join(r.get('citations',[]))} |")
    (STATE / "register.md").write_text("\n".join(lines), encoding="utf-8")


def _render_lenses(sc: dict, register: list[dict], rules: dict) -> None:
    lines = ["# Layer maturity (D2)\n",
             "| Layer | Grade |", "|---|---|"]
    for layer, grade in sc["layer_grades"].items():
        lines.append(f"| {layer} | {grade} |")
    cap = rules["d3_render_cap"]
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, None: 4}
    top = sorted([r for r in register if D.is_open_risk(r)],
                 key=lambda r: (order.get(r.get("severity"), 4), r["id"]))[:cap]
    lines += [f"\n# Red team — top {cap} open failure modes (D3)\n",
              "| ID | Failure mode | Severity | Surface | Proof required |",
              "|---|---|---|---|---|"]
    for r in top:
        proof = (r.get("proof") or {}).get("type") or "unproven — see finding"
        lines.append(f"| {r['id']} | {r['title']} | {r.get('severity')} | "
                     f"{','.join(r.get('surface',[]))} | {proof} |")
    (STATE / "lenses.md").write_text("\n".join(lines), encoding="utf-8")


# --- diff-mode rerun (Phase 0 diff) ------------------------------------------

def cmd_rerun(args) -> int:
    prior = load_manifest()
    prior_hash = sha256_text(json.dumps(prior, sort_keys=True))
    mapping = json.loads(Path(args.map).read_text(encoding="utf-8"))
    changed = []
    new_artifacts = {}
    for aid, path in mapping.items():
        path = Path(path).resolve()
        h = sha256_file(path)
        new_artifacts[aid] = {"path": str(path), "sha256": h}
        if prior["artifacts"].get(aid, {}).get("sha256") != h:
            changed.append(aid)

    changed.extend(sorted(set(prior["artifacts"]) - set(new_artifacts)))
    config = _config(getattr(args, "config", None))
    archive = STATE / "history" / f"{prior['run']}-{prior_hash[:16]}"
    archive.mkdir(parents=True, exist_ok=True)
    for old in STATE.iterdir():
        if old.is_file():
            dest = archive / old.name
            if dest.exists() and dest.read_bytes() != old.read_bytes():
                raise ValueError("History collision; existing snapshot cannot be overwritten")
            dest.write_bytes(old.read_bytes())
    run_no = int(prior["run"].split("-")[1]) + 1
    manifest = dict(prior)
    manifest["run"] = f"run-{run_no:03d}"
    manifest["artifacts"] = new_artifacts
    manifest["prior_manifest_sha256"] = prior_hash
    manifest["assessed_at"] = datetime.now(timezone.utc).isoformat()
    manifest["rules_sha256"] = sha256_file(rules_path())
    manifest["prompt_hashes"] = {n: sha256_file(ROOT / n) for n in ("sweep.md", "challenge.md")}
    if config:
        for name in ("subject", "model_evolution", "model_pins"):
            if name in config:
                manifest[name] = config[name]
        params = dict(prior.get("params", {}))
        for name in ("owner_roster", "release_calendar", "valuation"):
            if name in config:
                params[name] = config[name]
        manifest["params"] = params

    register = D.load_jsonl(STATE / "register.jsonl")
    contract_changed = any(prior.get(k) != manifest.get(k) for k in
                           ("subject", "model_evolution", "model_pins", "params", "rules_sha256", "prompt_hashes"))
    affected = [r["id"] for r in register] if changed or contract_changed else prior.get("pending_revalidation", [])
    manifest["pending_revalidation"] = sorted(set(affected))
    (STATE / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _clear_views()
    _write_jsonl(STATE / "challenges.jsonl", [])
    print(f"Re-run {manifest['run']} (chained to {prior_hash[:12]}). "
          f"Changed artifacts: {changed or 'none'}.")
    print(f"Rows re-entering the sweep ({len(affected)}): {affected}")
    print("Next: orchestrate sweep-payload  (scope the sweep to the surfaces of the affected rows).")
    return 0


# --- io ----------------------------------------------------------------------


def cmd_evolution_check(args) -> int:
    import model_evolution
    result = model_evolution.evaluate(load_manifest(), base_dir=STATE)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "QUALIFIED" else 2

def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="product-diligence pipeline driver")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("--map", required=True); p.add_argument("--config")
    sub.add_parser("admit")
    sub.add_parser("status")
    sub.add_parser("sweep-groups")
    p = sub.add_parser("sweep-payload"); p.add_argument("--group", default=None,
        help="one of security_and_data, product_and_strategy, ops_and_release; default 'all' (single call)")
    p = sub.add_parser("ingest-findings"); p.add_argument("file")
    sub.add_parser("derive")
    sub.add_parser("challenge-payload")
    p = sub.add_parser("ingest-challenges"); p.add_argument("file")
    sub.add_parser("reconcile")
    p = sub.add_parser("check"); p.add_argument("--verbose", action="store_true",
        help="show all P1-P10 checks, not just failures, with full untruncated detail")
    p = sub.add_parser("render"); p.add_argument("--verbose", action="store_true")
    p = sub.add_parser("rerun"); p.add_argument("--map", required=True); p.add_argument("--config")
    sub.add_parser("evolution-check")
    args = ap.parse_args()

    dispatch = {
        "init": cmd_init, "admit": cmd_admit, "status": cmd_status,
        "sweep-groups": cmd_sweep_groups, "sweep-payload": cmd_sweep_payload,
        "ingest-findings": cmd_ingest_findings, "derive": cmd_derive,
        "challenge-payload": cmd_challenge_payload, "ingest-challenges": cmd_ingest_challenges,
        "reconcile": cmd_reconcile, "check": cmd_check, "render": cmd_render, "rerun": cmd_rerun,
    }
    dispatch["evolution-check"] = cmd_evolution_check
    try:
        if args.cmd not in {"init", "rerun", "status"}:
            errors = D.manifest_integrity_errors(load_manifest(), STATE, rules_path())
            if errors:
                raise ValueError("Evidence invalid: " + "; ".join(errors))
        return dispatch[args.cmd](args)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
