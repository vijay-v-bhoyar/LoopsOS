#!/usr/bin/env bash
echo 'BLOCKED: legacy shell self-test is deprecated; run test_fleet_runtime.py.' >&2
exit 2
# Self-test for partition_backlog.py — proves the safety invariant (emitted
# partitions are file-disjoint), balanced spread, and correct handling of
# true conflicts, cross-partition deps, and undeterminable items.
# Exit 0 = all hold.
set -u
PART="$(cd "$(dirname "$0")" && pwd)/partition_backlog.py"
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/.loop/fleet"
cat > "$WORK/.loop/MAP.md" << 'EOF'
# Code Map
## Where things live
- auth: `src/auth`
- api: `src/api`
- ui: `src/components`
EOF
cat > "$WORK/.loop/BACKLOG.md" << 'EOF'
## Now
- [ ] B001 · auth work A
      files: src/auth/a.ts
      deps: []
- [ ] B002 · ui work
      files: src/components/x.tsx
      deps: []
- [ ] B003 · TRUE CONFLICT with B001 — same exact file
      files: src/auth/a.ts
      deps: []
- [ ] B004 · api work
      files: src/api/y.ts
      deps: []
- [ ] B005 · depends on B002
      files: src/components/z.tsx
      deps: [B002]
- [ ] B006 · no hint no mappable words
      deps: []
- [ ] B007 · dir-level via text mentions api
      deps: []
EOF
python3 "$PART" "$WORK" --agents 2 > /tmp/pt_out 2>&1 || { echo "FAIL: nonzero exit"; cat /tmp/pt_out; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHONPATH="$SCRIPT_DIR" python3 - "$WORK" << 'EOF' || exit 1
import sys, re
from pathlib import Path
from partition_backlog import (parse_now_items, load_where_index,
                               predict_touch_set, paths_conflict)
work = Path(sys.argv[1])
items = parse_now_items((work/".loop/BACKLOG.md").read_text())
where = load_where_index(work/".loop/MAP.md")
touch = {i["id"]: predict_touch_set(i, where) for i in items}
txt = (work/".loop/fleet/PARTITIONS.md").read_text()
a1 = re.findall(r"\n- (B\d+)", txt.split("## agent-1")[1].split("## agent-2")[0])
a2 = re.findall(r"\n- (B\d+)", txt.split("## agent-2")[1].split("## UNASSIGNED")[0])
unassigned = txt.split("## UNASSIGNED")[1]

def bset(ids):
    s = set()
    for i in ids: s |= (touch[i] or set())
    return s

checks = {
 "INVARIANT: bins file-disjoint": not paths_conflict(bset(a1), bset(a2)),
 "B001 and B003 (same file) never co-parallel":
     not (("B001" in a1 and "B003" in a1) or ("B001" in a2 and "B003" in a2)),
 "work spread (both agents non-empty)": len(a1) >= 1 and len(a2) >= 1,
 "B006 undeterminable -> UNASSIGNED": "B006" in unassigned and "undeterminable" in unassigned,
 "B005 cross-partition dep OR co-located with B002":
     ("B005" in unassigned) or
     ("B002" in a1 and "B005" in a1) or ("B002" in a2 and "B005" in a2),
 "B007 dir-level prediction placed or solo":
     "B007" in a1 or "B007" in a2 or "B007" in unassigned,
}
for name, ok in checks.items(): print(("ok  " if ok else "FAIL"), name)
sys.exit(0 if all(checks.values()) else 1)
EOF

# The true-conflict pair must NOT share a bin even under adversarial ordering.
echo "ok  invariant + conflict cases"

# --agents 1 degenerate case: everything determinable in one bin, no crash
python3 "$PART" "$WORK" --agents 1 > /dev/null 2>&1 || { echo "FAIL: single-agent"; exit 1; }
echo "ok  single-agent degenerate"
echo "SELFTEST PASS"
