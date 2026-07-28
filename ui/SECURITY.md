# Security Model

## Protected Assets

- Enterprise use-case text, extracted document text, reviewed transcripts, owner/evidence overlays, approvals, and execution records.
- Tenant identity, role claims, recommendation provenance, corpus integrity, audit events, and exported action plans.
- Optional AI and transcription service boundaries.

## Primary Threats And Controls

| Threat | Required control |
| --- | --- |
| Browser role spoofing | Local role selection is labeled evaluation-only; enterprise mode requires BFF session verification and otherwise blocks startup |
| Cross-tenant data access | Tenant scope is derived server-side; API authorization is checked on every object; isolation probes are a release gate |
| Approval or audit tampering | Approvals and executions require an append-only authoritative audit sink with actor, tenant, correlation ID, timestamp, before/after state, and policy decision |
| Approve/reject-and-swap | Authority decisions bind to the SHA-256 hash of the exact plan, evidence scope, risk, corpus version, and loop descriptor; approvals expire, preserve renewal history, and are consumed once; rejection atomically blocks the exact run |
| Duplicate or ambiguous side effects | Write-ahead dispatch intent, caller idempotency keys, server deduplication, bounded retry classes, and linked recovery runs |
| SSRF or connector credential exfiltration | Exact host allowlist, HTTPS, DNS/private-address rejection, redirect refusal, response limits, and server-only credential injection |
| Document parser abuse | File type/size/count/time limits, text-only extraction, no injected HTML, parser worker termination, and no OCR in this release |
| Audio or document exfiltration | Raw files/audio remain transient; external transfer requires explicit action; endpoints are HTTPS and host-allowlisted |
| Prompt injection through source text | Optional AI may propose fields only; the deterministic engine alone selects loops; proposals require user review |
| Endpoint abuse or SSRF-like configuration | URLs reject credentials and remote HTTP, enforce exact host policy, refuse redirects, time out, and cap JSON responses |
| XSS/clickjacking | React text rendering, no document HTML injection, CSP, `frame-ancestors 'none'`, `X-Frame-Options: DENY`, and MIME sniffing disabled |
| Browser storage loss | Bounded writes, save-failure state, portable export, and confirmed deletion; browser storage is never authoritative in enterprise mode |
| Dependency or image compromise | Lockfile installs, CI audit, pinned release image digest, SBOM, provenance, and vulnerability scanning at release |

## Data Handling

Evaluation mode stores accepted source text and workspace records in `localStorage`. Raw `File`, `Blob`, object URL, audio, interim transcript, and rejected proposal objects are not persisted. Workspace export contains the accepted workspace record and must inherit the enterprise classification of its source data.

Governed execution is persisted by the tenant-scoped authority API. Production deployments must place its database on encrypted persistent storage, disable development sessions, and replicate audit hashes to the approved external sink. Log metadata and stable error codes; do not log source text, transcripts, authorization material, connector credentials, or raw document contents.

## Reporting

Use the configured `VITE_LOOPOS_SUPPORT_CONTACT` for operational incidents. Security reports must include the image digest, environment, incident reference, affected tenant, and UTC timestamps, without attaching sensitive source material to ordinary tickets.
