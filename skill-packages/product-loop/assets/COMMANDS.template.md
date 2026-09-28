# Commands — verbatim, proven to execute
<!-- Written by INIT after executing each candidate once. DOCTOR repairs broken
     entries. Cycles run these exactly as written — never guess or substitute.
     A purpose with no working command is MISSING (creating it is backlog work). -->

test:      <command>
lint:      <command | MISSING>
lint:design:  <command | MISSING>   # design-token conformance; VERIFY gate 2 runs it
typecheck: <command | MISSING>
build:     <command | MISSING>
start:     <command>
smoke:     <command or scripted journey>
ports:     <ports the product binds; DOCTOR clears stale holders>
scan:secrets: <command | MISSING>   # security-review skill records these
scan:sast:    <command | MISSING>
scan:secrets:full: <command | MISSING>   # full-history; ship-release gates on it
scan:deps:    <command | MISSING>
map:          <python3 <skill-path>/scripts/generate_map.py . --if-stale — code-map skill records this>
evals:        <python3 <skill-path>/scripts/run_evals.py . --cycle <N> — product-evals skill records this>
bundle:verify: <python3 <skill-path>/scripts/bundle_verify.py . --active .loop/bundle/active.json | MISSING>  # agent-release; ORIENT § Phase 1 HALTs (Cause: bundle-drift) on any mismatch — MISSING here means no unattended run
impact:check: <python3 <skill-path>/scripts/impact_check.py . --plan <declared-touched-files> --map .loop/MAP.md | MISSING>  # COMMIT § Phase 6; out-of-set diff is a plan defect, not a silent pass
chain:verify: <python3 <skill-path>/scripts/chain_verify.py .loop/LOOP_LOG.md .loop/GOVERNANCE.md | MISSING>  # verifies Prev:/EntryHash: chains; names the first broken row on tamper
runrecord:emit: <python3 <skill-path>/scripts/runrecord_emit.py . --cycle <N> | MISSING>  # REFLECT § Phase 8, last step; derived-only, never authoritative
release:govern: <python3 <skill-path>/scripts/release_phase.py . --execute ship --hash <sha> | MISSING>  # release-governor; governed mode only (SKILL.md § 5.6 a–f). Also invoked as `... resume` for the veto sweep (ORIENT § Phase 1)
telemetry:ingest:  <python3 <skill-path>/scripts/ingest_telemetry.py . | MISSING>  # product-telemetry; REVIEW runs it pre-GROOM
telemetry:pull:<source>: <export command dumping normalized JSONL into .loop/telemetry/raw/ | MISSING>
harden:mutation:  <python3 <skill-path>/scripts/mutation_score.py . --changed --base main --test-command "<test cmd>" | MISSING>  # test-hardening; REVIEW-cadence mutation score, NEVER per-cycle
loop:health:  <python3 <skill-path>/scripts/loop_health.py . | MISSING>  # product-evals loop-health; REVIEW reads the verdict, human-facing diagnostic (not an optimization target)
container:verify:  <python3 <skill-path>/scripts/verify_spec.py . | MISSING>  # devcontainer-spec; MUST return PASS before unsafe mode / fleet
migrate:up:local:    <command | MISSING>   # migration-safety harness; NEVER record prod under these purposes
migrate:down:local:  <command | MISSING>
db:schema:local:     <command | MISSING>   # e.g. pg_dump --schema-only
db:rowcounts:local:  <command | MISSING>   # EXACT count(*) per table (n_live_tup is an estimate and gets flagged)
db:migration-state:local: <command | MISSING> # prints the tool's applied-version list; without it tracker leaks are invisible

# .loop/budget.json is runner config, not a discovered command — the human sets
# ceilings (usd/tokens/wallClockMin/cycles), the runner meters spend via
# model-gateway attribution, and ORIENT reads it at pre-cycle admission
# (SKILL.md § 6 Phase 1). The loop never writes it.
