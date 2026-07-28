import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
REPORT_MD = REPORT_DIR / "LINE_BY_LINE_PRACTICALITY_AUDIT.md"
REPORT_JSON = REPORT_DIR / "line_by_line_practicality_audit.json"

SCAN_PATHS = [
    "SDLC_CONTINUOUS_IMPROVEMENT_LOOP_FRAMEWORK.md",
    "LOOPS_SYSTEM_USE_CASES.md",
    "LOOPS_SYSTEM_MOAT_USE_CASES.md",
    "LOOPS_SYSTEM_PRACTICALITY_REVIEW.md",
    "108_LOOP_AGENTIC_ARCHITECTURE_GAP_REVIEW.md",
    "loops",
    "runtime",
    "controls",
    "owners",
    "evidence",
    "probes",
    "evals",
    "schemas",
    "standards",
    "scripts",
]

TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".py"}
MAX_REPORT_ROWS = 250


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for item in SCAN_PATHS:
        path = ROOT / item
        if not path.exists():
            continue
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            files.append(path)
            continue
        if path.is_dir():
            files.extend(
                child
                for child in path.rglob("*")
                if child.is_file() and child.suffix.lower() in TEXT_SUFFIXES
            )
    return sorted(set(files))


def add_finding(
    findings: list[dict[str, Any]],
    severity: str,
    path: Path,
    line_number: int,
    issue: str,
    recommendation: str,
) -> None:
    findings.append(
        {
            "severity": severity,
            "file": rel(path),
            "line": line_number,
            "issue": issue,
            "recommendation": recommendation,
        }
    )


def scan_line(path: Path, line_number: int, line: str, findings: list[dict[str, Any]]) -> None:
    relative = rel(path)
    stripped = line.strip()

    if (
        "C:/Users/vijay/Downloads/production-grade-continuous-improvement-loop.md" in stripped
        and relative not in {
            "scripts/audit_loop_practicality.py",
            "scripts/generate_runtime_backbone.py",
            "standards/STANDARD_SOURCE.yaml",
        }
    ):
        add_finding(
            findings,
            "blocker",
            path,
            line_number,
            "non-vendored standard dependency",
            "refer to standards/production-grade-continuous-improvement-loop.md so generation is reproducible",
        )

    if relative.startswith(("owners/", "evidence/", "loops/")) and (
        "UNASSIGNED" in stripped or "To be assigned" in stripped
    ):
        add_finding(
            findings,
            "action_required",
            path,
            line_number,
            "activation placeholder",
            "replace with named owner, accountable team, or authoritative evidence location before ACTIVE use",
        )

    if relative.startswith("runtime/metric_packs.yaml") and "to_be_set_by_policy_owner" in stripped:
        add_finding(
            findings,
            "action_required",
            path,
            line_number,
            "metric target is unset",
            "set a target value and observation window for selected pilot loops",
        )

    if relative.startswith(("runtime/loop-descriptors/", "loops/")) and (
        stripped == "status: DRAFT" or stripped == "- Lifecycle status: `DRAFT`"
    ):
        add_finding(
            findings,
            "action_required",
            path,
            line_number,
            "loop remains in DRAFT",
            "promote only after owners, evidence, probes, golden-task fixtures, metric targets, and handoffs are bound",
        )

    if len(line.rstrip("\n")) > 260 and relative.endswith((".md", ".yaml")):
        add_finding(
            findings,
            "warning",
            path,
            line_number,
            "very long line",
            "shorten or split this line if humans will maintain the file directly",
        )


def file_level_checks(path: Path, text: str, findings: list[dict[str, Any]]) -> None:
    relative = rel(path)
    if relative.startswith("loops/") and relative.endswith(".md") and path.name != "README.md":
        required_phrases = [
            "Trigger -> Qualify -> Observe -> Diagnose",
            "Action applied is not outcome proven",
            "Do not proceed when authority is unmapped",
            "Monitor effectiveness",
        ]
        for phrase in required_phrases:
            if phrase not in text:
                add_finding(
                    findings,
                    "blocker",
                    path,
                    1,
                    f"missing practical loop phrase: {phrase}",
                    "regenerate the loop file from the standard template",
                )

    if relative.startswith("runtime/loop-descriptors/") and relative.endswith(".yaml"):
        for field in ["loop_id:", "purpose:", "authority:", "evidence:", "controls:", "metric_pack_ref:"]:
            if field not in text:
                add_finding(
                    findings,
                    "blocker",
                    path,
                    1,
                    f"descriptor missing field {field}",
                    "regenerate runtime descriptors and rerun corpus validation",
                )


def build_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Line-by-Line Practicality Audit",
        "",
        "## Summary",
        "",
        f"- Files scanned: {payload['summary']['files_scanned']}",
        f"- Lines scanned: {payload['summary']['lines_scanned']}",
        f"- Blockers: {payload['summary']['by_severity'].get('blocker', 0)}",
        f"- Action-required findings: {payload['summary']['by_severity'].get('action_required', 0)}",
        f"- Warnings: {payload['summary']['by_severity'].get('warning', 0)}",
        "",
        "## Practical Readout",
        "",
        "The corpus is structurally usable when blockers are zero. Action-required findings mostly identify the deliberate DRAFT-to-ACTIVE work: assign owners, bind evidence locations, set metric targets, and connect executable probes.",
        "",
        "## Top Finding Types",
        "",
        "| Issue | Count |",
        "|---|---:|",
    ]
    for issue, total in payload["summary"]["by_issue"].most_common():
        lines.append(f"| {issue} | {total} |")

    lines.extend(
        [
            "",
            f"## First {min(MAX_REPORT_ROWS, len(payload['findings']))} Line Findings",
            "",
            "| Severity | File | Line | Issue | Recommendation |",
            "|---|---|---:|---|---|",
        ]
    )
    for finding in payload["findings"][:MAX_REPORT_ROWS]:
        lines.append(
            "| {severity} | `{file}` | {line} | {issue} | {recommendation} |".format(
                **finding
            )
        )

    if len(payload["findings"]) > MAX_REPORT_ROWS:
        lines.append("")
        lines.append(
            f"Only the first {MAX_REPORT_ROWS} findings are shown here. The complete finding set is in `reports/line_by_line_practicality_audit.json`."
        )

    lines.extend(
        [
            "",
            "## Activation Guidance",
            "",
            "1. Pick one pilot playbook from `runtime/pilot_playbooks.yaml`.",
            "2. Resolve only the owners and evidence locations needed by that playbook.",
            "3. Set metric targets for those loops.",
            "4. Bind the listed probes to real systems.",
            "5. Promote selected descriptors from DRAFT to PILOT, then ACTIVE after proof holds through the observation window.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    files = iter_text_files()
    findings: list[dict[str, Any]] = []
    lines_scanned = 0

    for path in files:
        text = path.read_text(encoding="utf-8")
        file_level_checks(path, text, findings)
        for line_number, line in enumerate(text.splitlines(), start=1):
            lines_scanned += 1
            scan_line(path, line_number, line, findings)

    by_severity = Counter(finding["severity"] for finding in findings)
    by_issue = Counter(finding["issue"] for finding in findings)
    payload = {
        "summary": {
            "files_scanned": len(files),
            "lines_scanned": lines_scanned,
            "by_severity": dict(by_severity),
            "by_issue": dict(by_issue),
        },
        "findings": findings,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    REPORT_MD.write_text(build_report({**payload, "summary": {**payload["summary"], "by_issue": by_issue}}), encoding="utf-8", newline="\n")

    print(f"Scanned {len(files)} files and {lines_scanned} lines")
    print(f"Blockers: {by_severity.get('blocker', 0)}")
    print(f"Action required: {by_severity.get('action_required', 0)}")
    print(f"Warnings: {by_severity.get('warning', 0)}")
    if by_severity.get("blocker", 0):
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS_WITH_ACTION_ITEMS" if findings else "RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
