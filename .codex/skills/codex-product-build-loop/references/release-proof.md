# Release and production proof

Read this reference when the user asks about production readiness, deployment, release, live users, or whether work is complete beyond the local repository.

## Proof states

| State | Meaning |
|---|---|
| Declared | A document, design, schema, or configuration says the capability exists. |
| Implemented | Current source or configuration appears to implement it. |
| Exercised | The relevant check or probe ran, whether green or red. |
| Proven | The required probe passed for the exact product, version, environment, configuration, and acceptance threshold. |
| Sustained | Repeated runs or an observation window show the outcome remains effective. |

Do not promote one state into another without evidence. In particular, action applied is not outcome proven.

## Evidence boundaries

Keep separate rows for:

1. Source and static inspection.
2. Focused local tests.
3. Local integration or served-preview behavior.
4. Production build or packaged artifact.
5. Git branch, commit, and remote state.
6. Deployment state for the exact target and version.
7. Authenticated-live journeys and real integrations.
8. Monitoring or sustained-effectiveness evidence.
9. Required human approval or residual-risk acceptance.

A local test is not deployment evidence. A ready deployment is not authenticated-live proof. An unauthenticated health route is not proof of an authenticated journey. Installation is not configuration or operation. Skipped, degraded, expired, stale, or scope-mismatched evidence is not a pass.

## Release gate

- Verify the intended deployment target, account/project, source revision, configuration contract, artifact identity, and rollback path.
- Do not request or expose secrets. Ask for redacted configuration status or execute through an authorized secret-bearing environment.
- Do not deploy, publish, push, promote, delete, or mutate production unless the user explicitly authorizes that action and the exact target is known.
- Treat missing security, migration, live-integration, rollback, monitoring, or approval evidence according to the declared release gate. Missing required proof yields `NO_GO`.
- A temporary exception records authorized residual risk; it does not convert a failed control into a pass.

## Evidence ledger

For material work, record:

```text
requirement -> changed surface -> check/probe -> target/version -> result -> evidence location -> remaining gap
```

Verdicts:

- `PASS`: all evidence required for the stated scope is current and green.
- `PARTIAL`: some requested scope is complete but a meaningful gap remains.
- `BLOCKED`: missing authority, input, dependency, or environment prevents completion.
- `NO_GO`: a required release or production gate is not met.

Name the narrowest safe next action. Do not describe a release as complete while required external or human-owned evidence remains absent.
