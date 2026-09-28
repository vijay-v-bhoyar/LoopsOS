#!/usr/bin/env python3
"""product-diligence render gate: checks P1-P11.

Exit 0 = green (scorecard may render). Exit 1 = red (render blocked, INV-14).
Every check prints PASS/FAIL with the offending ids so failures are actionable.
Stdlib only. Imports derive.py so P4 re-derivation uses the one authoritative
implementation rather than a second copy of the rule tables.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import derive as D


# Enumerated field domains (mirrors the SKILL.md data contract).
TYPES = {"risk", "strength", "unknown"}
SEVERITIES = {"critical", "high", "medium", "low", None}
EVIDENCE_MODES = {"cited-exploit", "cited-absent-control", "cited-strength", "asserted", "missing"}
VERIFIABILITY = {"design", "test-report", "live-probe-only"}
STATUSES = {"open", "fixed-pending-proof", "closed", "accepted"}
PROOF_TYPES = {"probe", "test-report", "manual-attestation"}

CITATION_RE = re.compile(r"^A-[A-Za-z0-9]+:.+$|^MOAT:.+$")
# Anti-hallucination scan patterns (advisory but blocking on clear hits, P7).
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|"
                     r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|"
                     r"Q[1-4]\s*\d{4})\b")
MONEY_RE = re.compile(r"(\$\s?\d|\b\d+(?:\.\d+)?\s?(?:USD|dollars|million|billion|[MB])\b)")
ALLOWED_PLAN_TOKENS = {"now", "next", "later", "30/60/90"}


DETAIL_CAP = 200  # chars shown per failing check in terse mode


class Report:
    """Terse by default: on a large register a single failing check (e.g. P7 with
    many flagged owner fields) can produce pages of detail text. Printing all of
    that by default would bloat the transcript of whatever is orchestrating this
    loop over a long, multi-cycle session — exactly the kind of context growth
    this skill exists to catch in the *reviewed* product. --verbose restores full
    per-check detail and shows PASS lines too; terse mode still shows every FAIL,
    just capped, so nothing is hidden — only abbreviated."""

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.failed = False
        self.results: list[tuple[str, bool, str]] = []

    def check(self, pid: str, ok: bool, detail: str = "") -> None:
        if not ok:
            self.failed = True
        self.results.append((pid, ok, detail))

    def dump(self) -> None:
        n_pass = sum(1 for _, ok, _ in self.results if ok)
        n_total = len(self.results)
        print(f"{'RED' if self.failed else 'GREEN'} ({n_pass}/{n_total} checks pass)")
        for pid, ok, detail in self.results:
            if ok and not self.verbose:
                continue  # terse: suppress passing checks, always show failures
            status = "PASS" if ok else "FAIL"
            if not self.verbose and len(detail) > DETAIL_CAP:
                detail = detail[:DETAIL_CAP] + f"… (+{len(detail)-DETAIL_CAP} chars, use --verbose)"
            print(f"[{status}] {pid} {detail}".rstrip())


def run(state_dir: Path, rules_path: Path, verbose: bool = False) -> Report:
    r = Report(verbose=verbose)
    rules = D.load_json(rules_path)
    reg = D.load_jsonl(state_dir / "register.jsonl")
    verdicts = D.load_jsonl(state_dir / "verdicts.jsonl")
    challenges = D.load_jsonl(state_dir / "challenges.jsonl")
    manifest = D.load_json(state_dir / "manifest.json") if (state_dir / "manifest.json").exists() else {}
    artifacts = manifest.get("artifacts", {})
    params = manifest.get("params", {})
    present = set(artifacts.keys())

    _p1_schema(r, reg, verdicts, challenges, manifest)
    _p2_citations(r, reg, present)
    _p3_severity_evidence(r, reg)
    _p4_rederivation(r, reg, rules, manifest, challenges, verdicts, base_dir=state_dir)
    _p5_admission(r, verdicts, present, rules)
    _p6_challenges(r, challenges, verdicts)
    _p7_honesty(r, reg, verdicts, params)
    _p8_lifecycle(r, reg)
    _p9_rendering(r, state_dir, rules, D.derive_all(reg, rules, manifest, challenges, base_dir=state_dir))
    _p10_manifest(r, manifest, base_dir=state_dir, rules_path=rules_path)
    _p11_evolution(r, reg, rules, manifest, challenges, state_dir)
    return r


def _p1_schema(r, reg, verdicts, challenges, manifest) -> None:
    ok = True
    detail = []
    fps = {}
    for row in reg:
        rid = row.get("id", "?")
        if row.get("type") not in TYPES:
            ok = False; detail.append(f"{rid}:bad type")
        if row.get("severity") not in SEVERITIES:
            ok = False; detail.append(f"{rid}:bad severity")
        if row.get("evidence_mode") not in EVIDENCE_MODES:
            ok = False; detail.append(f"{rid}:bad evidence_mode")
        if row.get("verifiability") not in VERIFIABILITY:
            ok = False; detail.append(f"{rid}:bad verifiability")
        if row.get("status") not in STATUSES:
            ok = False; detail.append(f"{rid}:bad status")
        fp = row.get("fingerprint")
        if fp:
            fps.setdefault(fp, []).append(rid)
    dupes = {fp: ids for fp, ids in fps.items() if len(ids) > 1}
    if dupes:
        ok = False
        detail.append(f"duplicate fingerprints: {dupes}")
    r.check("P1", ok, "; ".join(detail))


def _p2_citations(r, reg, present) -> None:
    ok = True
    detail = []
    for row in reg:
        if row.get("type") == "unknown":
            continue
        cites = row.get("citations") or []
        if row.get("type") in {"risk", "strength"} and not cites:
            ok = False; detail.append(f"{row['id']}:{row['type']} without citation")
        if row.get("type") == "strength" and not D.is_cited_strength(row):
            ok = False; detail.append(f"{row['id']}:invalid cited strength")
        for c in cites:
            if not CITATION_RE.match(c):
                ok = False; detail.append(f"{row['id']}:malformed citation '{c}'")
                continue
            art = c.split(":", 1)[0]
            if art not in present:
                ok = False; detail.append(f"{row['id']}:cites unknown artifact {art}")
    r.check("P2", ok, "; ".join(detail))


def _p3_severity_evidence(r, reg) -> None:
    """Critical requires a cited exploit or cited absent control; asserted caps
    at High; a live-probe-only cell must be unknown unless a test-report backs it."""
    ok = True
    detail = []
    for row in reg:
        if row.get("type") != "risk":
            continue
        sev, mode = row.get("severity"), row.get("evidence_mode")
        if sev == "critical" and mode not in {"cited-exploit", "cited-absent-control"}:
            ok = False; detail.append(f"{row['id']}:critical with evidence_mode={mode}")
        if mode == "asserted" and sev == "critical":
            ok = False; detail.append(f"{row['id']}:asserted may not be critical")
        if row.get("verifiability") == "live-probe-only":
            has_testreport = any(c.startswith("A-") and ":" in c for c in (row.get("citations") or [])
                                 if _looks_like_test(c))
            if row.get("type") == "risk" and not has_testreport:
                ok = False
                detail.append(f"{row['id']}:live-probe-only asserted as risk without test-report")
    r.check("P3", ok, "; ".join(detail))


def _looks_like_test(cite: str) -> bool:
    tail = cite.split(":", 1)[1].lower() if ":" in cite else ""
    return any(k in tail for k in ("test", "probe", "suite", "eval", "report"))


def _p4_rederivation(r, reg, rules, manifest, challenges, stored_verdicts, base_dir=None) -> None:
    derived = D.derive_all(reg, rules, manifest, challenges, base_dir=base_dir)["verdicts"]
    dmap = {v["lens"]: v for v in derived}
    smap = {v["lens"]: v for v in stored_verdicts}
    ok = True
    detail = []
    if len(smap) != len(stored_verdicts):
        ok = False; detail.append("duplicate stored lens records")
    for lens, dv in dmap.items():
        sv = smap.get(lens)
        if sv is None:
            ok = False; detail.append(f"{lens}:missing from verdicts.jsonl")
            continue
        if sv != dv:
            ok = False
            detail.append(f"{lens}:stored decision fields differ from current derivation")
    for lens in smap:
        if lens not in dmap:
            ok = False; detail.append(f"{lens}:stored but not derivable (stale)")
    r.check("P4", ok, "; ".join(detail))


def _p5_admission(r, verdicts, present, rules) -> None:
    ok = True
    detail = []
    lensed = {v["lens"] for v in verdicts}
    for dim in ["D1", "D2", "D3", "D4", "D5", "D6"]:
        keys = rules["dimension_lens_map"][dim]
        keys = keys if isinstance(keys, list) else [keys]
        floor_ok, _ = D.floor_and_coverage(dim, present, rules)
        active = [k for k in keys if k in lensed] or ([dim] if dim in lensed else [])
        if not floor_ok and active:
            ok = False; detail.append(f"{dim}:below floor but has verdict {active}")
    r.check("P5", ok, "; ".join(detail))


def _p6_challenges(r, challenges, verdicts) -> None:
    ok = True
    detail = []
    for c in challenges:
        res = c.get("resolution")
        if not res or res.get("kind") not in {"upheld", "revised", "accepted"}:
            ok = False; detail.append(f"{c.get('id','?')}:unresolved (auto-accept not recorded)")
        elif res.get("kind") == "upheld" and not res.get("citation"):
            ok = False; detail.append(f"{c.get('id','?')}:upheld without counter-citation")
    r.check("P6", ok, "; ".join(detail))


def _p7_honesty(r, reg, verdicts, params) -> None:
    """No invented owners, dates, or currency figures (INV-10)."""
    ok = True
    detail = []
    roster = set(params.get("owner_roster", []))
    has_calendar = bool(params.get("release_calendar"))
    has_valuation = bool(params.get("valuation"))

    for row in reg:
        owner = row.get("owner")
        if owner and owner != "Owner unknown" and owner not in roster:
            ok = False; detail.append(f"{row['id']}:owner '{owner}' not in roster")
        for field in ("fix", "mitigation", "plan"):
            val = str(row.get(field, ""))
            if not has_calendar and _bad_date(val):
                ok = False; detail.append(f"{row['id']}.{field}:invented date")
            if not has_valuation and MONEY_RE.search(val) and not (row.get("citations")):
                ok = False; detail.append(f"{row['id']}.{field}:uncited currency figure")
    r.check("P7", ok, "; ".join(detail))


def _bad_date(text: str) -> bool:
    lowered = text.lower()
    for tok in ALLOWED_PLAN_TOKENS:
        lowered = lowered.replace(tok, "")
    return bool(DATE_RE.search(lowered))


def _p8_lifecycle(r, reg) -> None:
    ok = True
    detail = []
    for row in reg:
        if row.get("type") != "risk":
            continue
        st = row.get("status")
        if st == "closed":
            proof = row.get("proof") or {}
            if proof.get("type") not in PROOF_TYPES:
                ok = False; detail.append(f"{row['id']}:closed without valid proof")
            elif row.get("severity") == "critical" and proof.get("type") == "manual-attestation":
                ok = False; detail.append(f"{row['id']}:critical closed on manual-attestation")
        if st == "accepted":
            acc = row.get("acceptance") or {}
            if not all(acc.get(k) for k in ("owner", "expiry", "revisit_trigger")):
                ok = False; detail.append(f"{row['id']}:accepted missing owner/expiry/revisit_trigger")
            elif D.is_open_risk(row):
                ok = False; detail.append(f"{row['id']}:acceptance expired or invalid; reopen required")
    r.check("P8", ok, "; ".join(detail))


def _p9_rendering(r, state_dir, rules, expected=None) -> None:
    sc_path = state_dir / "scorecard.json"
    if not sc_path.exists():
        r.check("P9", True, "(no scorecard.json yet; run derive)")
        return
    sc = D.load_json(sc_path)
    ok = True
    detail = []
    if expected is not None and sc != expected:
        ok = False; detail.append("scorecard differs from current derivation")
    rendered = sc.get("scorecard", [])
    for row in rendered:
        if row["verdict"] in {"SKIPPED", "Undetermined"}:
            continue
        if row.get("score") is None:
            ok = False; detail.append(f"{row['dimension']}:missing score")
    r.check("P9", ok, "; ".join(detail))


def _p10_manifest(r, manifest, base_dir=None, rules_path=None) -> None:
    detail = D.manifest_integrity_errors(manifest, base_dir=base_dir, rules_path=rules_path)
    if manifest.get("pending_revalidation"):
        detail.append("findings pending revalidation")
    r.check("P10", not detail, "; ".join(detail))


def _p11_evolution(r, reg, rules, manifest, challenges, base_dir=None) -> None:
    if manifest.get("model_evolution") is None:
        r.check("P11", True, "no evolution evidence; D6 cannot claim evaluated resilience")
        return
    result = D.derive_all(reg, rules, manifest, challenges, base_dir=base_dir)["evolution"]
    r.check("P11", result["status"] == "QUALIFIED", "; ".join(str(x) for x in result.get("reasons", [])))


def main() -> int:
    ap = argparse.ArgumentParser(description="product-diligence render gate (P1-P11).")
    ap.add_argument("--dir", default=".diligence")
    ap.add_argument("--rules", default=None)
    ap.add_argument("--verbose", action="store_true",
                    help="show all 11 checks (not just failures) with full untruncated detail")
    args = ap.parse_args()
    state = Path(args.dir)
    rules_path = Path(args.rules) if args.rules else D._find_rules(state)
    report = run(state, rules_path, verbose=args.verbose)
    report.dump()
    if report.failed:
        print("Render is blocked until the above FAILs are fixed (INV-14). Re-run with --verbose for full detail.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
