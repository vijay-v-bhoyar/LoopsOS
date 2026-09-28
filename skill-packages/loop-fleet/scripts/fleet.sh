#!/usr/bin/env bash
echo 'BLOCKED: legacy fleet.sh is disabled, including cleanup. Use fleet_runtime.py; preserve branches and state.' >&2
exit 2
# Fleet coordinator for the loop-fleet skill.
#
# Threat model: concurrent worktrees mutating shared .loop/ state (corruption),
# two agents on one item (duplicate work), a partition that shares files
# (merge conflict = wasted spend), and an unbounded fleet burning cost. This
# script owns the safe parts: worktree lifecycle, a single-writer lock on
# shared state, a fail-closed budget ceiling, and serial merge through the
# SAME VERIFY gate the solo loop uses. Agents only ever build in isolation.
#
# Usage: fleet.sh <repo> <cycles-per-agent> [agents]
# Preconditions this enforces: clean tree, on main or a fleet base, a fresh
# PARTITIONS.md, and a recorded per-cycle budget cap.
set -euo pipefail

REPO="${1:?usage: fleet.sh <repo> <cycles-per-agent> [agents]  |  fleet.sh <repo> --cleanup}"
REPO="$(cd "$REPO" && pwd)"

# --cleanup: tear down a crashed run's worktrees/branches/markers and exit.
if [[ "${2:-}" == "--cleanup" ]]; then
  # Remove EVERY worktree checked out to a loop/fleet-* branch, wherever it
  # lives — a leftover worktree at an unexpected path otherwise blocks its
  # branch's deletion silently. Parse `worktree list --porcelain` for the
  # branch each worktree holds rather than assuming the path convention.
  while read -r wt_path; do
    [[ -n "$wt_path" ]] && git -C "$REPO" worktree remove --force "$wt_path" 2>/dev/null || true
  done < <(git -C "$REPO" worktree list --porcelain \
             | awk '/^worktree /{p=$2} /^branch refs\/heads\/loop\/fleet-/{print p}')
  git -C "$REPO" worktree prune 2>/dev/null || true
  stuck=""
  for br in $(git -C "$REPO" branch --list 'loop/fleet-*' --format '%(refname:short)'); do
    git -C "$REPO" branch -D "$br" 2>/dev/null || stuck="$stuck $br"
  done
  rm -f "$REPO/.loop/fleet/ACTIVE" "$REPO"/.loop/fleet/agent-*.skip
  if [[ -n "$stuck" ]]; then
    echo "cleanup incomplete — branches still checked out elsewhere:$stuck" >&2
    echo "remove their worktrees (git worktree list) and re-run --cleanup" >&2
    exit 1
  fi
  echo "fleet cleanup complete: worktrees removed, loop/fleet-* branches deleted, markers cleared"
  exit 0
fi

CYCLES="${2:?usage: fleet.sh <repo> <cycles-per-agent> [agents]}"
AGENTS="${3:-2}"
LOOP_DIR="$REPO/.loop"
FLEET_DIR="$LOOP_DIR/fleet"
LOCK="$FLEET_DIR/shared-state.lock"     # single-writer guard for shared .loop/ files
LEDGER="$FLEET_DIR/budget.ledger"
COORD_LOG="$FLEET_DIR/coordinator.log"
SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"

# Budget governor — fail closed. LOOP_MAX_COST_CENTS caps the whole run;
# LOOP_MAX_CYCLE_COST_CENTS caps one cycle. Without a ceiling set, refuse to
# run: an unattended fleet with no budget is denial-of-wallet waiting to happen.
: "${LOOP_MAX_COST_CENTS:?set LOOP_MAX_COST_CENTS — an unbounded fleet has no cost ceiling}"
MAX_CYCLE_COST="${LOOP_MAX_CYCLE_COST_CENTS:-$LOOP_MAX_COST_CENTS}"
# Time and spawn ceilings are independent of the cost governor: cost is an
# estimate parsed from invocation output, wall-clock is measured. A hung
# provider or retry storm must not run the fleet for hours even if the cost
# arithmetic never trips.
FLEET_DEADLINE_SECONDS="${LOOP_FLEET_DEADLINE_SECONDS:-14400}"   # 4h default
MAX_TOTAL_SPAWNS="${LOOP_MAX_TOTAL_SPAWNS:-$((AGENTS * CYCLES * 2))}"
FLEET_START_EPOCH="$(date +%s)"
spawn_count=0

log() { echo "[$(date -Is)] $*" | tee -a "$COORD_LOG" >&2; }
die() { log "FATAL: $*"; exit 1; }

[[ -f "$LOOP_DIR/VISION.md" ]] || die "no VISION.md — run product-loop INIT first"
[[ -f "$FLEET_DIR/PARTITIONS.md" ]] || die "no PARTITIONS.md — run partition_backlog.py first"
[[ ! -f "$LOOP_DIR/STOP" ]] || die "STOP file present"
# STOP and fleet artifacts are expected untracked state, not a dirty product tree.
dirty="$(git -C "$REPO" status --porcelain | grep -v "[.]loop/" || true)"
[[ -z "$dirty" ]] || die "working tree dirty — fleet needs a clean base"

command -v flock >/dev/null || die "flock required for safe shared-state serialization"
mkdir -p "$FLEET_DIR"

# Fix 4: cooperative fleet-active marker. Enforcement is not possible across
# arbitrary processes, so this is a COOPERATIVE guard: the solo product-loop and
# the partitioner check it and refuse to write shared state while a fleet runs.
# Stated as cooperative, not claimed as a lock on other processes.
ACTIVE_MARKER="$FLEET_DIR/ACTIVE"
if [[ -f "$ACTIVE_MARKER" ]]; then
  existing_pid="$(cat "$ACTIVE_MARKER" 2>/dev/null || echo '?')"
  if kill -0 "$existing_pid" 2>/dev/null; then
    die "another fleet coordinator (pid $existing_pid) is active — one fleet per repo"
  fi
  log "stale ACTIVE marker (pid $existing_pid dead) — reclaiming"
fi
echo "$$" > "$ACTIVE_MARKER"

# Fix 5: on ANY exit, clear the marker and prune worktrees so the next run's
# `worktree add` cannot fail on leftovers. Branches are kept (they hold unmerged
# work); worktrees are disposable views and are removed.
cleanup() {
  local code=$?
  for ((a = 1; a <= AGENTS; a++)); do
    git -C "$REPO" worktree remove --force "$REPO/../fleet-agent-$a" 2>/dev/null || true
    rm -f "$FLEET_DIR/agent-$a.skip"
  done
  git -C "$REPO" worktree prune 2>/dev/null || true
  rm -f "$ACTIVE_MARKER"
  log "cleanup done (exit $code); unmerged branches kept, worktrees pruned"
}
trap cleanup EXIT
: > "$LEDGER"

base_branch="$(git -C "$REPO" branch --show-current)"
[[ "$base_branch" == "main" || "$base_branch" == "master" || "$base_branch" == fleet/* ]] \
  || die "on '$base_branch' — start the fleet from main or a fleet/* branch"

# spent_cents: sum of the ledger, the single source of truth for the governor.
spent_cents() { awk '{s+=$1} END{print s+0}' "$LEDGER"; }

# cost_from_capture: extract cost-in-cents from a coordinator-captured Claude
# Code JSON result. The field name has shifted across CLI versions, so try the
# known keys; anything unparseable returns the per-cycle cap (fail closed).
# Uses python for robust JSON parsing — never a regex that a crafted transcript
# could spoof.
cost_from_capture() {
  local file="$1"
  python3 - "$file" "$MAX_CYCLE_COST" <<'PY'
import json, sys
path, cap = sys.argv[1], int(sys.argv[2])
try:
    with open(path) as handle:
        data = json.load(handle)
    if isinstance(data, list):  # stream-json: last result object wins
        data = next((d for d in reversed(data) if isinstance(d, dict)
                     and d.get("type") == "result"), data[-1] if data else {})
    usd = None
    for key in ("total_cost_usd", "cost_usd", "total_cost"):
        if isinstance(data.get(key), (int, float)):
            usd = data[key]; break
    print(cap if usd is None else max(0, round(usd * 100)))
except Exception:
    print(cap)  # fail closed: unparseable cost is charged the full cap
PY
}

# run_agent_cycle: build ONE cycle in an isolated worktree for one agent.
# The agent instance is told to select only from its partition and to write
# cycle artifacts under its own fleet subdir — never shared state.
run_agent_cycle() {
  local agent="$1" worktree="$REPO/../fleet-$agent" branch="loop/fleet-$agent"

  if [[ -f "$FLEET_DIR/$agent.skip" ]]; then
    log "$agent: skipped — unresolved rebase/merge defect (see merge-defects.log)"
    return 12
  fi
  if [[ ! -d "$worktree" ]]; then
    git -C "$REPO" worktree add -q -b "$branch" "$worktree" "$base_branch"
    log "$agent: worktree $worktree on $branch"
  fi

  local before_cost; before_cost="$(spent_cents)"
  if [[ "$before_cost" -ge "$LOOP_MAX_COST_CENTS" ]]; then
    log "$agent: run budget ${LOOP_MAX_COST_CENTS}c reached — skipping"
    return 10
  fi

  # Cost is derived from the coordinator-captured invocation output, NOT from
  # any file the worktree writes — an agent (or injected backlog text) must not
  # be able to under-report its own spend and defeat the governor. The captured
  # JSON is parsed by the coordinator; a value we cannot parse is charged the
  # full per-cycle cap (fail closed). Any worktree-supplied number is advisory
  # and clamped up to the cap, never trusted below it.
  local capture="$FLEET_DIR/$agent.capture.json"; : > "$capture"
  local prompt="Use the product-loop skill. You are fleet $agent. Select ONLY \
items listed under '## $agent' in .loop/fleet/PARTITIONS.md; if none remain, \
write no changes and report idle. Run exactly one cycle. Do not edit shared \
.loop/ state files directly — the fleet coordinator merges."

  ( cd "$worktree" && timeout --kill-after=60 "${LOOP_CYCLE_TIMEOUT:-45m}" \
      claude -p "$prompt" --output-format json \
      ${LOOP_UNSAFE:+--dangerously-skip-permissions} \
      >"$capture" 2>>"$COORD_LOG" ) || log "$agent: cycle exited nonzero"
  cat "$capture" >>"$COORD_LOG" 2>/dev/null || true

  local cycle_cost; cycle_cost="$(cost_from_capture "$capture")"
  # Clamp: never below 0, and a reported value above the cap is itself a breach.
  [[ "$cycle_cost" =~ ^[0-9]+$ ]] || cycle_cost="$MAX_CYCLE_COST"
  flock "$LOCK" bash -c 'echo "$1" >> "$2"' _ "$cycle_cost" "$LEDGER"
  if [[ "$cycle_cost" -gt "$MAX_CYCLE_COST" ]]; then
    log "$agent: cycle cost ${cycle_cost}c exceeded per-cycle cap ${MAX_CYCLE_COST}c — halting fleet"
    touch "$LOOP_DIR/STOP"
    return 11
  fi
  log "$agent: cycle done (${cycle_cost}c; run total $(spent_cents)c)"
}

# merge_agent: integrate one agent's branch through the SAME VERIFY gate, under
# the shared-state lock so no two merges interleave. A branch failing VERIFY at
# merge time is left unmerged and flagged — parallel build, serial verified
# integrate. Merge conflict => partitioner under-predicted the touch-set.
merge_agent() {
  local agent="$1" branch="loop/fleet-$agent"
  git -C "$REPO" rev-parse --verify -q "$branch" >/dev/null || return 0

  flock "$LOCK" bash -c '
    set -euo pipefail
    repo="$1"; branch="$2"; base="$3"; agent="$4"; fleet="$5"
    cd "$repo"
    if ! git merge --no-ff --no-commit "$branch" >/dev/null 2>&1; then
      git merge --abort 2>/dev/null || true
      echo "CONFLICT $agent $branch — partitioner defect: touch-sets overlapped" \
        >> "$fleet/merge-defects.log"
      exit 20
    fi
    # VERIFY gate parity: reuse the recorded commands the solo loop verifies with.
    ok=1
    while IFS= read -r line; do
      case "$line" in
        test:*|lint:*|lint:design:*|typecheck:*|build:*|smoke:*)
          cmd="${line#*: }"
          bash -c "$cmd" >/dev/null 2>&1 || { ok=0; break; }
        ;;
      esac
    done < "$repo/.loop/COMMANDS.md"
    if [[ "$ok" -ne 1 ]]; then
      git merge --abort 2>/dev/null || git reset --hard HEAD >/dev/null
      echo "VERIFY-FAILED $agent $branch — reverted, item must be re-queued" \
        >> "$fleet/merge-defects.log"
      exit 21
    fi
    git commit -q -m "fleet: merge $agent ($branch) through VERIFY gate"
  ' _ "$REPO" "$branch" "$base_branch" "$agent" "$FLEET_DIR" \
    && log "$agent: merged" \
    || log "$agent: NOT merged (see $FLEET_DIR/merge-defects.log)"
}

# rebase_worktrees_onto_base: after a round's merges, every live agent worktree
# must move onto the updated base before the next round, or it builds on stale
# state and diverges. A rebase conflict is the SAME partitioner-defect signal as
# a merge conflict, surfaced one round earlier — logged, worktree left for the
# human, agent skipped next round.
rebase_worktrees_onto_base() {
  local worktree branch
  for ((a = 1; a <= AGENTS; a++)); do
    worktree="$REPO/../fleet-agent-$a"; branch="loop/fleet-agent-$a"
    [[ -d "$worktree" ]] || continue
    if ! ( cd "$worktree" && git rebase "$base_branch" >/dev/null 2>&1 ); then
      ( cd "$worktree" && git rebase --abort 2>/dev/null || true )
      echo "REBASE-CONFLICT agent-$a $branch — partitioner defect: touch-sets overlapped across rounds" \
        >> "$FLEET_DIR/merge-defects.log"
      log "agent-$a: rebase onto $base_branch conflicted — flagged, will skip"
      touch "$FLEET_DIR/agent-$a.skip"
    fi
  done
}

log "fleet start: $AGENTS agents x $CYCLES cycles, base $base_branch, budget ${LOOP_MAX_COST_CENTS}c, deadline ${FLEET_DEADLINE_SECONDS}s, spawn cap ${MAX_TOTAL_SPAWNS}"
for ((round = 1; round <= CYCLES; round++)); do
  [[ -f "$LOOP_DIR/STOP" ]] && { log "STOP present — ending after round $((round-1))"; break; }
  [[ "$(spent_cents)" -ge "$LOOP_MAX_COST_CENTS" ]] && { log "run budget reached — ending"; break; }
  elapsed=$(( $(date +%s) - FLEET_START_EPOCH ))
  [[ "$elapsed" -ge "$FLEET_DEADLINE_SECONDS" ]] && { log "fleet deadline ${FLEET_DEADLINE_SECONDS}s reached — ending"; break; }
  [[ "$spawn_count" -ge "$MAX_TOTAL_SPAWNS" ]] && { log "spawn ceiling ${MAX_TOTAL_SPAWNS} reached — ending"; break; }
  log "=== round $round/$CYCLES (elapsed ${elapsed}s, spawns ${spawn_count}) ==="
  # Agents build in parallel...
  pids=()
  for ((a = 1; a <= AGENTS; a++)); do
    spawn_count=$((spawn_count + 1))
    run_agent_cycle "agent-$a" & pids+=("$!")
  done
  for pid in "${pids[@]}"; do wait "$pid" || true; done
  # ...then merge serially through one VERIFY gate...
  for ((a = 1; a <= AGENTS; a++)); do merge_agent "agent-$a"; done
  # ...then rebase live worktrees onto the newly-merged base (Fix 3).
  rebase_worktrees_onto_base
done

log "fleet done. Merged branches on $base_branch; defects in $FLEET_DIR/merge-defects.log if any."
log "Re-run partition_backlog.py before the next fleet round — the backlog changed."
