# Workspace removal and data-erasure boundary

This document describes the current product behavior. It is not an organizational retention policy or legal advice. The data/records owner must supply approved retention, hold and erasure rules; the application does not invent retention periods.

## What the action changes

| Mode | Removed by workspace removal | Completion evidence |
| --- | --- | --- |
| Evaluation | The selected draft in this browser's `loopos.v2.workspace-state` workspace list, including fields nested in that draft | Successful local storage write and reload showing the draft absent |
| Enterprise | The selected tenant-scoped authority workspace row, after the authority accepts the queued request | Successful authenticated deletion response and a fresh tenant-scoped workspace listing; the optimistic UI list alone is insufficient |

The confirmation explains the boundary, requires acknowledgment, and resets acknowledgment when reopened or when the selected subject/storage changes. Cancel does not submit removal. Persistence failures remain visible when the last workspace disappears from the UI; an unavailable authority can be retried. Conflicts or denied permissions require restoring authorized authoritative state, not repeated bypass attempts.

## Evidence and copy inventory

| Record/copy | Effect of workspace removal | Required follow-up for an erasure request |
| --- | --- | --- |
| Local evaluation draft and nested intake content | Removed from that browser's saved workspace list | Verify storage write and reload; inspect other browser profiles/tabs separately |
| Enterprise workspace row | Removed on accepted API deletion | Confirm authenticated API result and fresh listing |
| Release initiatives, proof packs, decision evidence, audit events, connector events and governed execution records | Retained separately; no cascading purge is claimed | Records owner determines approved retention and holds; produce record-specific disposition evidence |
| Downloaded JSON and other exports | Not revoked or erased | Locate recipients and storage; follow authorized disposition policy |
| Other browser copies, caches and session artifacts | Not cleared by this action | Inventory actual browser storage and purge only within approved scope |
| Backups, replicas, snapshots, restore points and logs | No deletion or restore suppression is established | Validate tombstones/holds and replay restore with synthetic canaries |
| AI provider requests, vendor logs and external connector systems | Not affected by local workspace removal | Obtain authorized vendor-specific deletion and retention evidence; mark unverifiable outcomes explicitly |
| Undiscovered derivatives, embeddings, summaries and checkpoints | No completeness claim | Discover actual lineage before asserting full erasure |

The UI must never describe this action as total data erasure or proof that all retained data is compliant. The observed API behavior retained a release proof pack after workspace deletion; this may be legitimate record retention and remains visible as an unresolved policy boundary.

## Required organizational acceptance evidence

1. Name an accountable data/records owner and independent reviewer; record applicable jurisdiction, purposes, data categories, contracts, approved retention and hold authorities.
2. Inventory actual storage, lineage and export destinations; distinguish observed inventory from unknown scope.
3. For each derivative, define disposition on removal/erasure, hold precedence, deletion deadlines, tombstone behavior, restore suppression and evidence custody. Do not automatically destroy retained audit evidence.
4. Run authorized synthetic-canary scenarios across deletion, concurrent sessions, replicas, offline recovery, restore, legal hold and hold release. Confirm unauthorized users cannot delete another tenant's records.
5. Obtain provider acknowledgments where applicable; preserve gaps when external deletion cannot be observed. Independently review results before closing the risk.

## Assessment status

F08 is **PARTIAL**: the misleading confirmation is corrected and limited local UI behavior is tested. The organizational policy, real derivative purge, legal holds, backup/restore deletion propagation and vendor deletion evidence remain **OPEN**. Local synthetic tests are not organizational approval, live storage verification or certification.
