# Graph-aware product tracing

Read this reference when Graphify or another repository graph is available, when graph artifacts already exist, or when the user requires graph-based build and test work.

## Before implementation

1. Check the graph manifest or report for repository identity, source revision, generation time, extraction diagnostics, and coverage limitations.
2. Query the graph for the requested user outcome and affected entrypoints before broad file exploration.
3. Trace callers, callees, state transitions, UI-to-API paths, persistence, authorization, tests, and runtime/deployment entrypoints for the changed surface.
4. Confirm important results in current source. A graph is navigation evidence, not an authority that overrides source or runtime behavior.

Prefer the installed Graphify skill or documented project commands over guessed CLI syntax. Inspect the export schema before writing integrity checks; an export may call relationships `links` or `edges`.

## After meaningful edits

1. Refresh the repository graph using the project’s supported workflow.
2. Re-query the changed path and confirm the intended new or changed relationships are represented.
3. Run available integrity diagnostics for missing endpoints, dangling or duplicate relationships, collapsed edges, parse failures, and zero-node source files.
4. Bind graph evidence to the current repository and source revision.

If extraction is unavailable or incomplete, continue with an explicit source-and-test trace when safe and permitted. Report `Graph trace: unavailable` or the exact coverage limitation. Do not call a partial graph complete, and do not use stale graph counts as current proof.
