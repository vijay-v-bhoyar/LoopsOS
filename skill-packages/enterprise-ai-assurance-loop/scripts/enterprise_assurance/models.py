"""Dated capability registry admission; candidates never silently replace a baseline."""
from .common import require, digest


def assess_candidate(baseline, candidate, observed_at, benchmark_decision):
    required = {"id", "provider", "route", "identity_verified", "capabilities", "source", "published_at", "reviewed_at", "expires_at", "deprecates_at", "fallbacks", "subject_sha"}
    for entry in (baseline, candidate):
        require(isinstance(entry, dict) and set(entry) == required, "invalid model capability registry entry")
        require(isinstance(entry["id"], str) and isinstance(entry["provider"], str) and isinstance(entry["route"], str), "model identity required")
        require(type(entry["identity_verified"]) is bool, "identity verification state required")
        require(isinstance(entry["source"], str) and entry["source"].startswith("https://"), "dated primary evidence URL required")
        require(all(type(entry[k]) is int for k in ("published_at", "reviewed_at", "expires_at", "deprecates_at")), "model evidence dates required")
        require(entry["published_at"] <= entry["reviewed_at"] <= observed_at, "future or inconsistent model evidence")
        require(isinstance(entry["capabilities"], dict) and entry["capabilities"], "capability fingerprint required")
        require(isinstance(entry["fallbacks"], list) and entry["id"] not in entry["fallbacks"], "invalid fallback graph")
    reasons = []
    if candidate["expires_at"] <= observed_at: reasons.append("MODEL_EVIDENCE_STALE")
    if candidate["deprecates_at"] <= observed_at: reasons.append("MODEL_DEPRECATED")
    if not candidate["identity_verified"]: reasons.append("ROUTE_IDENTITY_UNVERIFIED")
    require(isinstance(benchmark_decision, dict), "benchmark decision required")
    if benchmark_decision.get("subject_sha") != candidate["subject_sha"]: reasons.append("BENCHMARK_SUBJECT_MISMATCH")
    if benchmark_decision.get("decision") != "GO": reasons.append("REGRESSION_GATE_NOT_PASSED")
    if benchmark_decision.get("permission_manifest", {}).get("expires_at", 0) <= observed_at: reasons.append("BENCHMARK_EXPIRED")
    if benchmark_decision.get("proof") != "ENTERPRISE": reasons.append("ENTERPRISE_BENCHMARK_REQUIRED")
    changed = sorted(key for key in set(baseline["capabilities"]) | set(candidate["capabilities"])
                     if baseline["capabilities"].get(key) != candidate["capabilities"].get(key))
    return {"status": "EVIDENCE_REQUIRED" if reasons else "CANDIDATE_FOR_AUTHORIZED_REVIEW", "reasons": reasons,
            "capability_changes": changed, "baseline_evidence_stale": baseline["expires_at"] <= observed_at,
            "fallback_review_required": candidate["fallbacks"], "candidate_sha": digest(candidate),
            "promotion_authorized": False, "authority": "none"}
