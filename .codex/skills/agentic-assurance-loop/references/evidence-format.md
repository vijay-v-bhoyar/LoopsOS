# Portable owner evidence format

These helpers are local record validators and atomic appenders. They do not execute arbitrary commands, deliver help, schedule work, authenticate people, grant authority or decide production readiness. The parent lifecycle conductor retains those concerns. The identical `scripts/evidence_io.py` is vendored into each of the three standalone owner packages so installing one does not require another package. Keep its copies and tests synchronized when updating it.

Use the host's Python 3 executable. On this Windows host the bundled executable is available through Codex workspace dependencies; do not assume `python` is on PATH. Substitute the appropriate owner script below:

```text
python -B scripts/repair_ledger.py <record.json> --subject <current-subject.json>
python -B scripts/repair_ledger.py <record.json> --subject <current-subject.json> --append <event.json>
```

Create the initial record with the domain fields and `events: []` using the host's normal file writer. For assurance substitute `finding_ledger.py`; for vision use `vision_ledger.py`. The subject is independently supplied by the conductor and has exactly four nonempty string fields: `product`, `target`, `revision`, `configuration`. The conductor must derive revision/configuration from the actual tested source and runtime, and compare criteria and modes to its own accepted contract. Copying an old subject file is not a freshness check.

Each artifact reference has exactly `path` and `sha256`. Paths are POSIX-style relative paths under the directory containing the record. Absolute paths, parent traversal, backslashes, drive prefixes, symlinks and Windows reparse points are rejected. Hashes must be complete lowercase SHA256 values and are recomputed. Archive old inputs/outputs/oracles under this directory rather than referencing mutable working files; retain the mapping from snapshot to current working artifact in the parent evidence index.

Each check receipt has exactly:

```text
subject: the four-field tested subject
actor: nonempty actual operator/verifier name
at, expires: timezone-aware ISO timestamps, issued before now
command: nonempty argument list describing the executed procedure
exit_code: integer (zero for successful verification, nonzero for reproduction)
assertions: positive integer count of meaningful checks actually executed
output: artifact reference to stdout/stderr or direct result
oracle: artifact reference to the test/procedure and expected assertions
artifacts: nonempty list of tested artifact references
```

Record these values from actual execution. The validator rehashes files and checks schema, subject, freshness, ordering and domain bindings. It cannot establish that a claimed command ran or that the recorded oracle is adequate. Inspect direct outputs, actual runtime identity, test coverage and evidence provenance before accepting its readiness output. No JSON `PASS` field is accepted as semantic truth.

Append holds an exclusive local `.lock` file, validates the proposed full record, writes/fsyncs a same-directory temporary file, then atomically replaces the record. A failed append leaves the previous record unchanged. A competing or abandoned lock fails closed; inspect ownership before manual recovery and never silently steal a lock. Do not use concurrent network filesystem writers. No automatic lock recovery, schema migration or hostile-writer protection is supplied here.

Successful validation exits 0 and emits domain readiness or pending status with `authority: none`; exit 0 is not goal completion. Invalid/missing evidence, malformed input or lock contention exits 2 as `INVALID_OR_BLOCKED`. Stale subject or expired verification removes readiness but keeps historical evidence. Missing historical artifacts invalidate the record: restore the archived proof or have the parent review an explicit migration, without silently erasing history.

A principal able to rewrite the entire record, criteria, actor names and artifacts can forge consistent local history. The host must protect the accepted goal, mode, identities, budget and provenance. These helpers do not enforce a security boundary against that principal or hostile filesystem replacement races. Do not claim tamper-proof accounting or authenticated independent approval.
