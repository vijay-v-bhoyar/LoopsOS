#!/usr/bin/env python3
"""Derive verdicts and the scorecard from the register.

Verdicts derive from cited register rows, rule tables, current evidence bytes and
the assessment time. The model never writes a verdict; it only writes findings
and challenges. This module is the sole implementation of that function, called
in two places: the orchestrator's derive phase (to produce verdicts) and the
checker's P4 (to re-derive and detect a stale or tampered verdicts.jsonl).

No third-party deps. No eval of rule data — predicates are dispatched through a
closed table so a malformed rules.json cannot execute arbitrary code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


# --- state loading -----------------------------------------------------------

def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise ValueError(f"{path.name}:{i} is not valid JSON: {e}") from e
    return rows


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --- row helpers -------------------------------------------------------------

def is_open_risk(r: dict) -> bool:
    if r.get("type") != "risk":
        return False
    if r.get("status") in {"open", "fixed-pending-proof"}:
        return True
    if r.get("status") == "accepted":
        acceptance = r.get("acceptance") or {}
        if not isinstance(acceptance, dict) or not all(acceptance.get(k) for k in ("owner", "expiry", "revisit_trigger")):
            return True
        try:
            expiry = datetime.fromisoformat(str(acceptance.get("expiry", "")).replace("Z", "+00:00"))
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            return expiry <= datetime.now(timezone.utc)
        except (ValueError, TypeError):
            return True
    return False


def is_cited_strength(r: dict) -> bool:
    return (r.get("type") == "strength" and r.get("evidence_mode") == "cited-strength"
            and isinstance(r.get("citations"), list) and bool(r["citations"])
            and all(isinstance(c, str) and re.fullmatch(r"(?:A-[A-Za-z0-9]+|MOAT):\S.*", c)
                    for c in r["citations"]))


def manifest_integrity_errors(manifest: dict, base_dir: Path | None = None,
                              rules_path: Path | None = None) -> list[str]:
    """Verify local evidence bytes. This is integrity, not authenticated provenance."""
    errors = []
    base = Path(base_dir or Path.cwd())
    if not isinstance(manifest, dict) or not manifest:
        return ["no manifest.json"]
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return ["artifacts must be an object"]
    for aid, meta in artifacts.items():
        if not isinstance(meta, dict):
            errors.append(f"{aid}:invalid artifact metadata")
            continue
        expected = meta.get("sha256")
        if not isinstance(expected, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", expected):
            errors.append(f"{aid}:invalid sha256")
            continue
        try:
            raw_path = meta.get("path")
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise ValueError("missing path")
            path = Path(raw_path)
            if not path.is_absolute():
                path = base / path
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected.lower():
                errors.append(f"{aid}:artifact bytes changed")
        except (OSError, ValueError, TypeError):
            errors.append(f"{aid}:artifact unavailable")
    pins = manifest.get("model_pins")
    for stage in ("sweep", "challenge"):
        pin = pins.get(stage) if isinstance(pins, dict) else None
        if (not isinstance(pin, str) or not pin.strip() or any(c in pin for c in "<>?")
                or pin.strip().lower() in {"none", "unknown", "tbd"}):
            errors.append(f"missing/invalid {stage} model pin")
    if manifest.get("subject") is not None:
        subject = manifest["subject"]
        for field in ("product", "revision", "environment", "configuration"):
            if not isinstance(subject, dict) or not isinstance(subject.get(field), str) or not subject[field].strip():
                errors.append(f"subject.{field}:required")
    if "rules_sha256" in manifest:
        expected = manifest["rules_sha256"]
        target = Path(rules_path) if rules_path else Path(__file__).resolve().with_name("rules.json")
        try:
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if not isinstance(expected, str) or expected.lower() != actual:
                errors.append("rules fingerprint changed")
        except OSError:
            errors.append("rules unavailable")
    if "prompt_hashes" in manifest:
        hashes = manifest["prompt_hashes"]
        if not isinstance(hashes, dict):
            errors.append("invalid prompt fingerprints")
        else:
            for name, expected in hashes.items():
                if name not in {"sweep.md", "challenge.md"}:
                    errors.append(f"unexpected prompt fingerprint: {name}")
                    continue
                try:
                    actual = hashlib.sha256(Path(__file__).resolve().with_name(name).read_bytes()).hexdigest()
                    if not isinstance(expected, str) or expected.lower() != actual:
                        errors.append(f"{name}:prompt fingerprint changed")
                except OSError:
                    errors.append(f"{name}:prompt unavailable")
    if manifest.get("run") and manifest["run"] != "run-001":
        prior = manifest.get("prior_manifest_sha256")
        if not isinstance(prior, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", prior):
            errors.append("invalid prior manifest fingerprint")
    return errors


def is_compensated(r: dict) -> bool:
    """A compensating control lifts a block only when cited AND exercised by a
    supplied test result (INV-6). A control missing its test does not count."""
    c = r.get("compensating_control")
    return bool(c and c.get("cited") and c.get("test"))


def has_mitigation(r: dict) -> bool:
    m = r.get("mitigation")
    return bool(m and str(m).strip())


def touches(r: dict, surfaces: list[str] | None) -> bool:
    if not surfaces:
        return True
    return bool(set(r.get("surface", [])) & set(surfaces))


# --- layer grading (feeds D2) ------------------------------------------------

def layer_grades(register: list[dict], rules: dict) -> dict[str, str]:
    """Grade each of L01-L20.

    base   = production if any strength cites the layer, else demo if any risk
             cites it, else evidence-missing (unknowns alone are not evidence).
    cap    = worst OPEN risk on the layer: critical->broken, high-uncompensated
             ->demo, high-compensated/medium->beta, low->production.
    grade  = min(base, cap). A grade above demo therefore requires a strength row
             (INV note in SKILL: "above Demo requires >=1 cited strength").
    """
    ranks = rules["grade_rank"]
    grades: dict[str, str] = {}
    for layer in rules["all_layers"]:
        strengths = [r for r in register if is_cited_strength(r) and layer in r.get("surface", [])]
        open_risks = [r for r in register if is_open_risk(r) and layer in r.get("surface", [])]

        if not strengths and not open_risks:
            grades[layer] = "evidence-missing"
            continue

        base = "production" if strengths else "demo"

        cap = "production"
        for r in open_risks:
            sev = r.get("severity")
            if sev == "critical":
                r_cap = "broken"
            elif sev == "high":
                r_cap = "beta" if is_compensated(r) else "demo"
            elif sev == "medium":
                r_cap = "beta"
            else:  # low
                r_cap = "production"
            if ranks[r_cap] < ranks[cap]:
                cap = r_cap

        grades[layer] = base if ranks[base] <= ranks[cap] else cap
    return grades


# --- predicate implementations (closed set) ----------------------------------
# Each predicate reads the shared context dict and its own JSON params.

def _p_risk_open_sev_eq(ctx: dict, p: dict) -> bool:
    sev = p["severity"]
    unc = p.get("uncompensated")
    surfaces = p.get("surfaces")
    for r in ctx["register"]:
        if not is_open_risk(r) or r.get("severity") != sev:
            continue
        if not touches(r, surfaces):
            continue
        if unc is True and is_compensated(r):
            continue
        if unc is False and not is_compensated(r):
            continue
        return True
    return False


def _p_risk_open_sev_min(ctx: dict, p: dict) -> bool:
    floor = ctx["rules"]["severity_rank"][p["severity"]]
    unc = p.get("uncompensated")
    surfaces = p.get("surfaces")
    for r in ctx["register"]:
        if not is_open_risk(r):
            continue
        if ctx["rules"]["severity_rank"].get(r.get("severity"), -1) < floor:
            continue
        if not touches(r, surfaces):
            continue
        if unc is True and is_compensated(r):
            continue
        if unc is False and not is_compensated(r):
            continue
        return True
    return False


def _p_risk_open_high_compensated(ctx: dict, p: dict) -> bool:
    return any(is_open_risk(r) and r.get("severity") == "high" and is_compensated(r)
               for r in ctx["register"])


def _p_risk_open_medium_no_mitigation(ctx: dict, p: dict) -> bool:
    return any(is_open_risk(r) and r.get("severity") == "medium" and not has_mitigation(r)
               for r in ctx["register"])


def _p_strength_absent_on(ctx: dict, p: dict) -> bool:
    surfaces = set(p["surfaces"])
    return not any(is_cited_strength(r) and (set(r.get("surface", [])) & surfaces)
                   for r in ctx["register"])


def _p_strength_present_on(ctx: dict, p: dict) -> bool:
    surfaces = set(p["surfaces"])
    return any(is_cited_strength(r) and (set(r.get("surface", [])) & surfaces)
               for r in ctx["register"])


def _p_control_absent_open(ctx: dict, p: dict) -> bool:
    """Any OPEN row asserting the cited absence of one of the named controls."""
    controls = set(p["controls"])
    for r in ctx["register"]:
        if not is_open_risk(r):
            continue
        if r.get("evidence_mode") == "cited-absent-control" and r.get("control") in controls:
            return True
    return False


def _p_strength_covers_controls(ctx: dict, p: dict) -> bool:
    """A strength row present for EVERY named control (control proven present)."""
    controls = set(p["controls"])
    covered = {r.get("control") for r in ctx["register"]
               if is_cited_strength(r) and r.get("control") in controls}
    return controls.issubset(covered)


def _p_evolution_status(ctx: dict, p: dict) -> bool:
    return ctx["evolution"]["status"] == p["status"]


def _p_layer_count_grade_eq_min(ctx: dict, p: dict) -> bool:
    n = sum(1 for g in ctx["layer_grades"].values() if g == p["grade"])
    return n >= p["count"]


def _p_layer_count_grade_rank_min(ctx: dict, p: dict) -> bool:
    ranks = ctx["rules"]["grade_rank"]
    n = sum(1 for g in ctx["layer_grades"].values() if ranks[g] >= p["rank_min"])
    return n >= p["count"]


def _p_layer_any_core_rank_max(ctx: dict, p: dict) -> bool:
    ranks = ctx["rules"]["grade_rank"]
    core = ctx["rules"]["core_layers"]
    return any(ranks[ctx["layer_grades"][layer]] <= p["rank_max"] for layer in core)


def _p_layer_all_rank_min(ctx: dict, p: dict) -> bool:
    ranks = ctx["rules"]["grade_rank"]
    return all(ranks[g] >= p["rank_min"] for g in ctx["layer_grades"].values())


def _p_layer_all_core_rank_min(ctx: dict, p: dict) -> bool:
    ranks = ctx["rules"]["grade_rank"]
    core = ctx["rules"]["core_layers"]
    return all(ranks[ctx["layer_grades"][layer]] >= p["rank_min"] for layer in core)


PREDICATES: dict[str, Callable[[dict, dict], bool]] = {
    "risk_open_sev_eq": _p_risk_open_sev_eq,
    "risk_open_sev_min": _p_risk_open_sev_min,
    "risk_open_high_compensated": _p_risk_open_high_compensated,
    "risk_open_medium_no_mitigation": _p_risk_open_medium_no_mitigation,
    "strength_absent_on": _p_strength_absent_on,
    "strength_present_on": _p_strength_present_on,
    "control_absent_open": _p_control_absent_open,
    "strength_covers_controls": _p_strength_covers_controls,
    "evolution_status": _p_evolution_status,
    "layer_count_grade_eq_min": _p_layer_count_grade_eq_min,
    "layer_count_grade_rank_min": _p_layer_count_grade_rank_min,
    "layer_any_core_rank_max": _p_layer_any_core_rank_max,
    "layer_all_rank_min": _p_layer_all_rank_min,
    "layer_all_core_rank_min": _p_layer_all_core_rank_min,
}


def eval_condition(cond: dict, ctx: dict) -> bool:
    if "all" in cond:
        return all(eval_condition(c, ctx) for c in cond["all"])
    if "any" in cond:
        return any(eval_condition(c, ctx) for c in cond["any"])
    pred = cond["pred"]
    if pred not in PREDICATES:
        raise ValueError(f"unknown predicate in rules.json: {pred}")
    return PREDICATES[pred](ctx, cond)


# --- coverage, confidence, undetermined --------------------------------------

def floor_and_coverage(lens_key: str, present: set[str], rules: dict) -> tuple[bool, float]:
    """Return (floor_satisfied, coverage) for a lens key like 'D1' or 'D4'."""
    base = lens_key.split("_")[0]  # D4_valuation -> D4
    f = rules["floors"][base]
    ok = set(f["required"]).issubset(present)
    for group in f.get("any_of", []):
        if not (set(group) & present):
            ok = False
    if "min_present" in f and len(present) < f["min_present"]:
        ok = False
    relevant = set(f["relevant"])
    coverage = len(present & relevant) / len(relevant) if relevant else 0.0
    return ok, round(coverage, 3)


def confidence_band(coverage: float, downgraded: bool, rules: dict) -> str:
    bands = rules["confidence_bands"]  # ordered high->low by min
    name = bands[-1]["name"]
    for b in bands:
        if coverage >= b["min"]:
            name = b["name"]
            break
    if downgraded:
        order = [b["name"] for b in reversed(bands)]  # low..high
        idx = order.index(name)
        name = order[max(0, idx - 1)]
    return name


def unknown_majority(dimension: str, register: list[dict]) -> bool:
    rel = [r for r in register if dimension in r.get("dimensions", [])]
    if not rel:
        return True  # nothing but silence is not confidence
    unknowns = sum(1 for r in rel if r.get("type") == "unknown")
    known = len(rel) - unknowns
    return unknowns > known


def top_blocker(dimension: str, register: list[dict], rules: dict) -> str | None:
    ranked = sorted(
        [r for r in register if is_open_risk(r) and dimension in r.get("dimensions", [])],
        key=lambda r: rules["severity_rank"].get(r.get("severity"), -1),
        reverse=True,
    )
    return ranked[0]["id"] if ranked else None


# --- D3 security score (render lens, no verdict enum) ------------------------

def d3_security(register: list[dict], rules: dict) -> dict:
    open_risks = [r for r in register if is_open_risk(r)]
    for rung in rules["d3_security_score"]["ladder"]:
        cond = rung["if"]
        hit = (
            (cond == "open_critical" and any(r.get("severity") == "critical" for r in open_risks)) or
            (cond == "open_high_uncompensated" and any(r.get("severity") == "high" and not is_compensated(r) for r in open_risks)) or
            (cond == "open_high_compensated" and any(r.get("severity") == "high" and is_compensated(r) for r in open_risks)) or
            (cond == "open_medium" and any(r.get("severity") == "medium" for r in open_risks)) or
            (cond == "clean")
        )
        if hit:
            return {"score": rung["score"], "label": rung["label"]}
    return {"score": 5, "label": "no open blockers"}


# --- top-level derive --------------------------------------------------------

def derive_verdict(lens_key: str, rules: dict, ctx: dict) -> dict:
    lens = rules["lenses"][lens_key]
    matched = None
    for rule in lens["rules"]:
        if rule.get("else"):
            matched = rule
            break
        if eval_condition(rule["when"], ctx):
            matched = rule
            break
    if matched is None:
        matched = lens["rules"][-1]

    verdict = matched["verdict"]
    rule_id = matched["id"]
    dimension = lens_key.split("_")[0]

    # A terminal else-branch is the optimistic answer; refuse to award it when
    # the evidence base is mostly unknowns (INV-8).
    if (matched.get("else") or matched.get("positive")) and unknown_majority(dimension, ctx["register"]):
        return {"verdict": "Undetermined", "rule": None, "score": None}

    return {"verdict": verdict, "rule": rule_id, "score": lens["scores"].get(verdict)}


def derive_all(register: list[dict], rules: dict, manifest: dict,
               challenges: list[dict], base_dir: Path | None = None, now=None) -> dict:
    present = set(manifest.get("artifacts", {}).keys())
    has_valuation = bool(manifest.get("params", {}).get("valuation"))
    grades = layer_grades(register, rules)
    try:
        from model_evolution import evaluate
        evolution = evaluate(manifest, base_dir=base_dir, now=now)
    except (ImportError, OSError, ValueError, TypeError, KeyError) as exc:
        evolution = {"status": "NOT_READY" if manifest.get("model_evolution") else "EVIDENCE_MISSING",
                     "reasons": [f"Model-evolution evidence unavailable: {type(exc).__name__}"],
                     "candidates": [], "execution_authorized": False}
    if not isinstance(evolution, dict) or evolution.get("status") not in {"EVIDENCE_MISSING", "NOT_READY", "QUALIFIED"}:
        evolution = {"status": "NOT_READY", "reasons": ["Invalid model-evolution evaluation"],
                     "candidates": [], "execution_authorized": False}
    ctx = {"register": register, "rules": rules, "layer_grades": grades, "evolution": evolution}

    # An accepted challenge downgrades its target's lens(es). A lens-targeted
    # challenge (D1..D6) downgrades that lens; a row-targeted challenge (R-nn)
    # downgrades every lens the row is tagged to.
    dims = {"D1", "D2", "D3", "D4", "D5", "D6"}
    row_dims = {r["id"]: r.get("dimensions", []) for r in register}
    accepted_lenses: set[str] = set()
    for c in challenges:
        if (c.get("resolution") or {}).get("kind") != "accepted":
            continue
        tgt = c.get("target", "")
        if tgt in dims:
            accepted_lenses.add(tgt)
        elif tgt in row_dims:
            accepted_lenses.update(row_dims[tgt])

    verdicts = []
    scorecard = []

    lens_map = rules["dimension_lens_map"]
    for dim in ["D1", "D2", "D3", "D4", "D5", "D6"]:
        ok, coverage = floor_and_coverage(dim, present, rules)
        downgraded = dim in accepted_lenses

        if dim == "D3":
            # Render lens: score from worst open severity; no rule verdict.
            if not ok:
                scorecard.append({"dimension": "Security & Safety", "verdict": "SKIPPED",
                                  "score": None, "confidence": None,
                                  "top_blocker": None, "note": _skip_note(dim, present, rules)})
                continue
            sec = d3_security(register, rules)
            verdicts.append({"lens": "D3", "verdict": sec["label"], "rule": "d3-ladder",
                             "rows": [], "coverage": coverage,
                             "confidence": confidence_band(coverage, downgraded, rules)})
            scorecard.append({"dimension": "Security & Safety", "verdict": sec["label"],
                              "score": sec["score"],
                              "confidence": confidence_band(coverage, downgraded, rules),
                              "top_blocker": top_blocker("D3", register, rules)})
            continue

        keys = lens_map[dim] if isinstance(lens_map[dim], list) else [lens_map[dim]]
        lens_key = _pick_lens_key(keys, has_valuation, rules)

        if not ok:
            title = rules["lenses"][lens_key]["title"]
            scorecard.append({"dimension": title, "verdict": "SKIPPED", "score": None,
                              "confidence": None, "top_blocker": None,
                              "note": _skip_note(dim, present, rules)})
            continue

        d = derive_verdict(lens_key, rules, ctx)
        conf = confidence_band(coverage, downgraded, rules)
        verdicts.append({"lens": lens_key, "verdict": d["verdict"], "rule": d["rule"],
                         "rows": _contributing_rows(dim, register), "coverage": coverage,
                         "confidence": conf})
        if dim == "D6":
            receipt = manifest.get("model_evolution")
            verdicts[-1]["evolution_evidence"] = {
                "status": evolution["status"],
                "sha256": receipt.get("sha256") if isinstance(receipt, dict) else None,
                "subject": manifest.get("subject"),
            }
        scorecard.append({"dimension": rules["lenses"][lens_key]["title"],
                          "verdict": d["verdict"], "score": d["score"],
                          "confidence": None if d["verdict"] == "Undetermined" else conf,
                          "top_blocker": top_blocker(dim, register, rules)})

    return {"layer_grades": grades, "verdicts": verdicts, "scorecard": scorecard,
            "valuation_mode": has_valuation, "evolution": evolution}


def _pick_lens_key(keys: list[str], has_valuation: bool, rules: dict) -> str:
    for k in keys:
        needs = rules["lenses"][k].get("requires_valuation_params", False)
        if needs == has_valuation:
            return k
    return keys[0]


def _contributing_rows(dimension: str, register: list[dict]) -> list[str]:
    return [r["id"] for r in register
            if (is_open_risk(r) or is_cited_strength(r) or r.get("type") == "unknown")
            and dimension in r.get("dimensions", [])]


def _skip_note(dim: str, present: set[str], rules: dict) -> str:
    f = rules["floors"][dim]
    missing = [a for a in f["required"] if a not in present]
    for group in f.get("any_of", []):
        if not (set(group) & present):
            missing.append("(" + " or ".join(group) + ")")
    return f"{dim} skipped: missing {', '.join(missing) or 'artifacts below floor'}"


# --- CLI ---------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Derive verdicts and scorecard from the register.")
    ap.add_argument("--dir", default=".diligence", help="state directory")
    ap.add_argument("--rules", default=None, help="explicit rules.json override (default: this package's rules.json)")
    ap.add_argument("--print", action="store_true", help="print scorecard to stdout")
    args = ap.parse_args()

    d = Path(args.dir)
    rules_path = Path(args.rules) if args.rules else _find_rules(d)
    rules = load_json(rules_path)
    register = load_jsonl(d / "register.jsonl")
    challenges = load_jsonl(d / "challenges.jsonl")
    manifest = load_json(d / "manifest.json") if (d / "manifest.json").exists() else {"artifacts": {}, "params": {}}

    result = derive_all(register, rules, manifest, challenges, base_dir=d)

    with (d / "verdicts.jsonl").open("w", encoding="utf-8") as fh:
        for v in result["verdicts"]:
            fh.write(json.dumps(v) + "\n")
    (d / "scorecard.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    if args.print:
        for row in result["scorecard"]:
            score = row["score"] if row["score"] is not None else "-"
            print(f"{row['dimension']:<28} {str(score):<3} {row['verdict']:<32} "
                  f"conf={row['confidence'] or '-'} blocker={row['top_blocker'] or '-'}")
    return 0


def _find_rules(state_dir: Path) -> Path:
    local = Path(__file__).resolve().with_name("rules.json")
    if local.is_file():
        return local
    raise FileNotFoundError("Package rules.json missing; supply an explicit --rules override")


if __name__ == "__main__":
    sys.exit(main())
