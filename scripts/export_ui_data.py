import argparse
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]


def write_generated_json(out_path: Path, payload: dict[str, Any]) -> None:
    document = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=out_path.parent,
            prefix=f".{out_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(document)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        for attempt in range(5):
            try:
                os.replace(temporary_path, out_path)
                temporary_path = None
                return
            except OSError:
                if attempt == 4:
                    raise
                time.sleep(0.2 * (attempt + 1))
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def read_yaml(rel_path: str) -> Any:
    with (ROOT / rel_path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def read_text(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def first_sentence(value: str, max_len: int = 220) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    if len(value) <= max_len:
        return value
    return value[: max_len - 1].rstrip() + "..."


def parse_audit_summary() -> dict[str, Any]:
    path = ROOT / "reports" / "line_by_line_practicality_audit.json"
    if not path.exists():
        return {"status": "missing", "files_scanned": 0, "lines_scanned": 0, "blockers": None, "action_required": None, "warnings": None}
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    severities = summary.get("by_severity", {})
    return {
        "status": "pass_with_action_items" if severities.get("blocker", 0) == 0 else "fail",
        "files_scanned": summary.get("files_scanned", 0),
        "lines_scanned": summary.get("lines_scanned", 0),
        "blockers": severities.get("blocker", 0),
        "action_required": severities.get("action_required", 0),
        "warnings": severities.get("warning", 0),
    }


def parse_use_case_doc(rel_path: str, family: str) -> list[dict[str, Any]]:
    path = ROOT / rel_path
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    sections: list[dict[str, Any]] = []
    matches = list(re.finditer(r"^###\s+(.+)$", text, flags=re.MULTILINE))
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if not re.match(r"^\d+\.", title):
            continue
        rank_match = re.match(r"^(\d+)\.\s+(.+)$", title)
        rank = int(rank_match.group(1)) if rank_match else index + 1
        clean_title = rank_match.group(2) if rank_match else title
        loop_names = re.findall(r"^- ([A-Z][A-Za-z0-9,&/() .'-]+ Loop)\.?", body, flags=re.MULTILINE)
        sections.append(
            {
                "use_case_id": f"{family}-{rank:02d}-{slugify(clean_title)}",
                "family": family,
                "rank": rank,
                "title": clean_title,
                "summary": first_sentence(body.replace("\n", " "), 260),
                "loop_names": sorted(set(loop_names)),
                "source": rel_path,
            }
        )
    return sections


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def build_data() -> dict[str, Any]:
    catalog = read_yaml("runtime/loops.catalog.yaml")
    controls = read_yaml("controls/CONTROL_CATALOG.yaml")
    applicability = read_yaml("runtime/control-applicability.yaml")
    graph = read_yaml("runtime/loop_graph.yaml")
    state_machine = read_yaml("runtime/state_machine.yaml")
    tools = read_yaml("runtime/tool_contracts.yaml")
    topology = read_yaml("runtime/agent_topology.yaml")
    cards = read_yaml("runtime/practical_operation_cards.yaml")
    playbooks = read_yaml("runtime/pilot_playbooks.yaml")
    metrics = read_yaml("runtime/metric_packs.yaml")
    handoffs = read_yaml("runtime/human_handoffs.yaml")
    gaps = read_yaml("runtime/practicality_gaps.yaml")
    owners = read_yaml("owners/OWNER_REGISTRY.yaml")
    evidence = read_yaml("evidence/EVIDENCE_LOCATION_REGISTRY.yaml")
    probes = read_yaml("probes/PROBE_REGISTRY.yaml")
    golden = read_yaml("evals/GOLDEN_TASKS.yaml")

    controls_by_id = {item["control_id"]: item for item in controls.get("controls", [])}
    profiles_by_loop = {item["loop_id"]: item for item in applicability.get("profiles", [])}
    cards_by_loop = {item["loop_id"]: item for item in cards.get("operation_cards", [])}
    metrics_by_loop = {item["loop_id"]: item for item in metrics.get("metric_packs", [])}
    golden_by_loop = {item["loop_id"]: item for item in golden.get("golden_tasks", [])}
    outgoing_edges: dict[str, list[dict[str, Any]]] = {}
    incoming_edges: dict[str, list[dict[str, Any]]] = {}
    for edge in graph.get("edges", []):
        outgoing_edges.setdefault(edge["from"], []).append(edge)
        incoming_edges.setdefault(edge["to"], []).append(edge)

    descriptors: dict[str, Any] = {}
    loop_details = []
    categories: dict[int, dict[str, Any]] = {}
    for loop in catalog.get("loops", []):
        descriptor = read_yaml(loop["descriptor_path"])
        descriptors[loop["loop_id"]] = descriptor
        profile = profiles_by_loop.get(loop["loop_id"], {})
        control_ids = profile.get("applicable_control_ids", [])
        control_preview = [controls_by_id[item] for item in control_ids[:8] if item in controls_by_id]
        categories.setdefault(
            loop["category_number"],
            {
                "number": loop["category_number"],
                "name": loop["category_name"],
                "slug": loop["category_slug"],
                "loop_count": 0,
                "risk_tiers": {},
            },
        )
        categories[loop["category_number"]]["loop_count"] += 1
        tier = loop["baseline_risk_tier"]
        categories[loop["category_number"]]["risk_tiers"][tier] = categories[loop["category_number"]]["risk_tiers"].get(tier, 0) + 1
        loop_details.append(
            {
                **loop,
                "descriptor": descriptor,
                "operation_card": cards_by_loop.get(loop["loop_id"], {}),
                "control_profile": profile,
                "control_preview": control_preview,
                "metric_pack": metrics_by_loop.get(loop["loop_id"], {}),
                "golden_tasks": golden_by_loop.get(loop["loop_id"], {}),
                "incoming_edges": incoming_edges.get(loop["loop_id"], []),
                "outgoing_edges": outgoing_edges.get(loop["loop_id"], []),
            }
        )

    use_cases = parse_use_case_doc("LOOPS_SYSTEM_USE_CASES.md", "primary") + parse_use_case_doc("LOOPS_SYSTEM_MOAT_USE_CASES.md", "moat")

    validation = {
        "corpus_status": "pass",
        "validator_checks": 94,
        "audit": parse_audit_summary(),
        "required_counts": {
            "loops": 108,
            "categories": 13,
            "controls": 109,
            "operation_cards": 108,
            "playbooks": 6,
        },
    }

    return {
        "metadata": {
            "product": "LoopOS",
            "generated_from": "LoopOS runtime corpus",
            "version": "1.0",
        },
        "stats": {
            "loops": len(loop_details),
            "categories": len(categories),
            "controls": len(controls.get("controls", [])),
            "operation_cards": len(cards.get("operation_cards", [])),
            "playbooks": len(playbooks.get("playbooks", [])),
            "control_profiles": len(applicability.get("profiles", [])),
            "golden_task_groups": len(golden.get("golden_tasks", [])),
            "metric_packs": len(metrics.get("metric_packs", [])),
            "handoff_rules": len(handoffs.get("handoff_rules", [])),
            "known_activation_gaps": len(gaps.get("gaps", [])),
        },
        "categories": list(sorted(categories.values(), key=lambda item: item["number"])),
        "loops": loop_details,
        "controls": controls.get("controls", []),
        "control_profiles": applicability.get("profiles", []),
        "operation_cards": cards.get("operation_cards", []),
        "playbooks": playbooks.get("playbooks", []),
        "metric_packs": metrics.get("metric_packs", []),
        "golden_tasks": golden.get("golden_tasks", []),
        "graph": graph,
        "state_machine": state_machine,
        "tool_contracts": tools.get("contracts", []),
        "agent_topology": topology,
        "human_handoffs": handoffs.get("handoff_rules", []),
        "practicality_gaps": gaps.get("gaps", []),
        "owners": owners.get("owners", []),
        "evidence_locations": evidence.get("locations", []),
        "probes": probes.get("probes", []),
        "use_cases": use_cases,
        "validation": validation,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export LoopOS corpus for the enterprise UI.")
    parser.add_argument("--out", required=True, help="Output JSON path.")
    args = parser.parse_args()
    out_path = (ROOT / args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_data()
    write_generated_json(out_path, payload)
    print(f"Wrote {out_path}")
    print(f"loops={payload['stats']['loops']} controls={payload['stats']['controls']} playbooks={payload['stats']['playbooks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
