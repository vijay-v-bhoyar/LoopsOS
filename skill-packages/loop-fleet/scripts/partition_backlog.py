#!/usr/bin/env python3
"""Partition the backlog into file-disjoint slices, one per fleet agent.

Stdlib only. Two backlog items are safe to build in parallel only if their
predicted file touch-sets do not overlap — `deps:` alone is necessary but not
sufficient (two dep-free items editing the same file still conflict at merge).
This partitioner predicts each item's touch-set from explicit `files:` hints,
the code-map "where things live" index, and item text, then greedily packs
items into N partitions whose touch-sets are provably disjoint. Items whose
touch-set cannot be determined, or that collide with every partition, stay
UNASSIGNED — the coordinator runs them solo. A merge conflict downstream is a
partitioner defect (touch-set under-predicted), logged as such, not a routine
event to resolve cleverly.

Output: .loop/fleet/PARTITIONS.md — the authority the coordinator reads.
Exit 0 if a usable partition (≥1 agent with ≥1 item) was produced, else 1.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Item start line, per the product-backlog parse contract.
ITEM_START = re.compile(r"^- \[ \] (B\d+) · (.+)$")
FILES_HINT = re.compile(r"^\s*files:\s*(.+)$")
DEPS_HINT = re.compile(r"^\s*deps:\s*\[([^\]]*)\]")
# code-map "where things live": "- <label>: `dir1`, `dir2`"
WHERE_LINE = re.compile(r"^- ([^:]+):\s*(.+)$")
BACKTICK_PATH = re.compile(r"`([^`]+)`")


def already_handled_ids(repo: Path) -> set[str]:
    """Item ids that are done or in-flight, so a mid-fleet re-partition never
    re-hands a completed or actively-built item to another agent. Sources: the
    backlog Done section and commit subjects on every loop/fleet-* branch
    (commits follow `cycle-N: <id> ·`/`<id>` per the product-loop commit format)."""
    handled: set[str] = set()
    backlog = repo / ".loop" / "BACKLOG.md"
    if backlog.exists():
        in_done = False
        for line in backlog.read_text().splitlines():
            if line.startswith("## "):
                in_done = line.strip() == "## Done"
            elif in_done:
                handled |= set(re.findall(r"\bB\d+\b", line))
    try:
        branches = subprocess.run(
            ["git", "-C", str(repo), "branch", "--list", "loop/fleet-*",
             "--format", "%(refname:short)"],
            capture_output=True, text=True, timeout=15).stdout.split()
        for branch in branches:
            subjects = subprocess.run(
                ["git", "-C", str(repo), "log", branch, "--format=%s", "-n", "200"],
                capture_output=True, text=True, timeout=15).stdout
            handled |= set(re.findall(r"\bB\d+\b", subjects))
    except Exception:
        pass  # no git / no branches yet — Done-only exclusion still applies
    return handled


def parse_now_items(backlog_text: str) -> list[dict]:
    """Items in the Now section only — the sole selectable pool."""
    items, in_now, current = [], False, None
    for line in backlog_text.splitlines():
        if line.startswith("## "):
            in_now = line.strip() == "## Now"
            if current:
                items.append(current)
                current = None
            continue
        if not in_now:
            continue
        start = ITEM_START.match(line)
        if start:
            if current:
                items.append(current)
            current = {"id": start.group(1), "title": start.group(2).strip(),
                       "files": set(), "deps": set(), "text": start.group(2)}
        elif current:
            current["text"] += " " + line.strip()
            if (files := FILES_HINT.match(line)):
                current["files"] |= {p.strip() for p in files.group(1).split(",") if p.strip()}
            if (deps := DEPS_HINT.match(line)):
                current["deps"] |= {d.strip() for d in deps.group(1).split(",") if d.strip()}
    if current:
        items.append(current)
    return items


def load_where_index(map_path: Path) -> dict[str, list[str]]:
    """label -> [dirs] from code-map's 'Where things live', for touch prediction."""
    if not map_path.exists():
        return {}
    index, in_section = {}, False
    for line in map_path.read_text().splitlines():
        if line.startswith("## "):
            in_section = "where things live" in line.lower()
            continue
        if in_section and (m := WHERE_LINE.match(line)):
            index[m.group(1).strip().lower()] = BACKTICK_PATH.findall(m.group(2))
    return index


def predict_touch_set(item: dict, where: dict[str, list[str]]) -> set[str] | None:
    """Explicit files: hints win. Else map item text to where-things-live dirs.
    None = undeterminable -> the item is not safely parallelizable."""
    if item["files"]:
        return {f.rstrip("/") for f in item["files"]}
    text = item["text"].lower()
    touched: set[str] = set()
    for label, dirs in where.items():
        label_words = [w for w in re.split(r"[ /&-]+", label) if len(w) > 2]
        if any(word in text for word in label_words):
            touched |= {d.rstrip("/") for d in dirs}
    return touched or None


def _is_dir_path(path: str) -> bool:
    """A touch entry is a directory if it has no file extension — file: hints
    give files, the where-index gives dirs. Heuristic, and the conservative
    failure (treating a file as a dir) only ever over-predicts conflict."""
    return "." not in Path(path).name


def paths_conflict(a: set[str], b: set[str]) -> bool:
    """Two touch-sets conflict for parallel git work iff they share an exact
    path, or one side's DIRECTORY entry contains the other's path. Two distinct
    files under a common directory do NOT conflict — git merges them cleanly,
    and treating them as conflicting would needlessly serialize the fleet."""
    for pa in a:
        for pb in b:
            if pa == pb:
                return True
            if _is_dir_path(pa) and pb.startswith(pa + "/"):
                return True
            if _is_dir_path(pb) and pa.startswith(pb + "/"):
                return True
    return False


def partition(items: list[dict], where: dict[str, list[str]], agents: int
              ) -> tuple[list[list[dict]], list[tuple[dict, str]]]:
    """Greedy first-fit into `agents` bins with provably disjoint touch-sets.
    Larger touch-sets placed first (harder to fit later). Dependencies must
    resolve within the same bin or already be Done elsewhere — cross-bin deps
    would serialize the bins, defeating the point, so such items go solo."""
    ready = [i for i in items]
    for item in ready:
        item["touch"] = predict_touch_set(item, where)

    bins: list[list[dict]] = [[] for _ in range(agents)]
    bin_touch: list[set[str]] = [set() for _ in range(agents)]
    bin_ids: list[set[str]] = [set() for _ in range(agents)]
    unassigned: list[tuple[dict, str]] = []

    for item in sorted(ready, key=lambda i: -(len(i["touch"]) if i["touch"] else 0)):
        if item["touch"] is None:
            unassigned.append((item, "touch-set undeterminable (add a files: hint)"))
            continue
        unresolved_deps = set(item["deps"])  # deps must be satisfied in the same bin
        # An item is eligible for a bin only if it conflicts with NO bin but that
        # one — a directory-level touch-set can conflict with a file already in a
        # DIFFERENT bin, which would break cross-bin disjointness after placement.
        # Requiring conflict-freedom against all other bins keeps the emitted
        # partitions provably disjoint (the invariant the whole fleet rests on).
        eligible = []
        for index in range(agents):
            if unresolved_deps and not unresolved_deps <= bin_ids[index]:
                continue
            conflicts_elsewhere = any(
                other != index and paths_conflict(item["touch"], bin_touch[other])
                for other in range(agents))
            if not paths_conflict(item["touch"], bin_touch[index]) and not conflicts_elsewhere:
                eligible.append(index)
        if eligible:
            index = min(eligible, key=lambda i: len(bins[i]))  # least-loaded spreads work
            bins[index].append(item)
            bin_touch[index] |= item["touch"]
            bin_ids[index].add(item["id"])
        else:
            reason = ("cross-partition dependency" if unresolved_deps
                      else "touch-set conflicts across partitions (tighten files: hints)")
            unassigned.append((item, reason))
    return bins, unassigned


def render(bins: list[list[dict]], unassigned: list[tuple[dict, str]],
           agents: int) -> str:
    lines = ["# Fleet partitions",
             "<!-- Generated by loop-fleet partition_backlog.py. The coordinator is",
             "     the authority that reads this. An agent may select ONLY items under",
             "     its own heading. A merge conflict means a touch-set was under-",
             "     predicted here — fix the prediction (usually a files: hint), don't",
             "     paper over it at merge. -->", ""]
    for index in range(agents):
        agent = f"agent-{index + 1}"
        lines.append(f"## {agent}")
        if not bins[index]:
            lines.append("- (empty — fewer disjoint partitions than agents)")
        for item in bins[index]:
            touch = ", ".join(sorted(item["touch"])) or "?"
            lines.append(f"- {item['id']} · {item['title']} · touches: {touch}")
        lines.append("")
    lines.append("## UNASSIGNED — coordinator runs these solo, not in the fleet")
    if not unassigned:
        lines.append("- none")
    for item, reason in unassigned:
        lines.append(f"- {item['id']} · {item['title']} — {reason}")
    return "\n".join(lines) + "\n"


def main() -> int:
    print("BLOCKED: legacy partition CLI is disabled. Predictions are candidates; fleet_runtime.py requires file, contract and state reservations.", file=sys.stderr)
    return 2
    # Historical CLI retained below for source review, never executed.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".")
    parser.add_argument("--agents", type=int, default=2,
                        help="fleet size; 2 is the sane early ceiling")
    args = parser.parse_args()
    if args.agents < 1:
        sys.exit("--agents must be >= 1")
    repo = Path(args.repo).resolve()

    backlog_path = repo / ".loop" / "BACKLOG.md"
    if not backlog_path.exists():
        sys.exit(f"no backlog at {backlog_path}")
    items = parse_now_items(backlog_path.read_text())
    if not items:
        sys.exit("no items in the Now section to partition")
    handled = already_handled_ids(repo)
    excluded = [i["id"] for i in items if i["id"] in handled]
    items = [i for i in items if i["id"] not in handled]
    if excluded:
        print(f"excluded {len(excluded)} already-shipped/in-flight items: {excluded}")
    if not items:
        sys.exit("all Now items are already shipped or in-flight — nothing to partition")

    where = load_where_index(repo / ".loop" / "MAP.md")
    bins, unassigned = partition(items, where, args.agents)

    out_path = repo / ".loop" / "fleet" / "PARTITIONS.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(bins, unassigned, args.agents))

    assigned = sum(len(b) for b in bins)
    print(f"partitions -> {out_path}")
    print(f"assigned {assigned} item(s) across {args.agents} agent(s); "
          f"{len(unassigned)} solo")
    for index, bin_items in enumerate(bins, 1):
        print(f"  agent-{index}: {[i['id'] for i in bin_items]}")
    return 0 if assigned else 1


if __name__ == "__main__":
    sys.exit(main())
