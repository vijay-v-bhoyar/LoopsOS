# LoopOS Enterprise Deployment Gate

LoopOS has two explicit postures: `evaluation` and `enterprise`. Evaluation mode is browser-local and must not be used as an authority plane. Enterprise mode fails closed until every required binding is configured and runtime-verified.

## Required Bindings

| Binding | Required contract | Activation proof |
| --- | --- | --- |
| Identity | BFF-managed session; IdP groups mapped server-side to LoopOS roles | Session endpoint verifies issuer, audience, signature, expiry, tenant, subject, and one explicit role mapping |
| Persistence | LoopOS authority service and tenant-scoped durable Postgres database | Authority readiness reports Postgres and the authenticated workspace list succeeds; enterprise mode never uses browser workspace storage |
| Audit | Authority hash chain delivered through the durable outbox to an external append-only sink | Authority readiness reports a configured sink and zero undelivered anchors |
| Transport | HTTPS for every non-local origin | Certificate, reachability, redirect, and hostname checks pass |
| Retention | Approved retention and deletion policy URL | Legal/security owners approve the policy and deletion evidence path |
| Operations | Named support contact and on-call route | Alert routing and incident exercise pass |
| Outbound policy | Exact host allowlist for AI/transcription endpoints | Egress policy and endpoint data-processing terms are approved |
| Backup and restore | Secure reference to a recent restore exercise | Authority validates the reference and freshness timestamp; an independent reviewer validates the exercise itself |

The required `VITE_` values are documented in `.env.example`. They are public build configuration, never secrets. Tokens and service credentials belong only in the BFF or service runtime.

## Production Build

```bash
docker compose build
docker compose up -d
```

Terminate TLS at the enterprise ingress, keep the supplied security headers, and narrow `connect-src` in `nginx.conf` to approved origins. Set `VITE_LOOPOS_AUTHORITY_URL` to the exact HTTPS authority origin or to `/api` behind a same-origin ingress. Enterprise mode probes `/health/ready`, exchanges the managed identity session, and loads the tenant workspace register before it can transition to `enterprise_ready`.

## Release Gate

1. Pin the image by digest and attach SBOM, vulnerability scan, and provenance from the enterprise build service.
2. Run unit, design-token, build, Playwright, corpus-validation, and practicality-audit gates.
3. Test tenant isolation, session expiry, CSRF, audit append/retrieve, retention deletion, and restore in staging.
4. Confirm CSP and egress allowlists contain only approved service origins.
5. Record security, privacy, legal, product, and operations approval references.
6. Canary to an internal cohort; promote only when errors, latency, persistence, and audit delivery meet the runbook thresholds.

## Current Boundary

This repository supplies the portal, deterministic recommendation engine, governed execution authority, tenant-scoped SQLite/Postgres store contract, authoritative workspace revisions, tool/probe runtime, audit chain with a durable external-anchor outbox, and hardened containers. It does not supply the organization IdP/BFF, a provisioned managed Postgres instance, the independently administered WORM/SIEM sink, secrets manager, or organization-specific retention/backup implementation. Production activation remains blocked until those bindings are provisioned and verified.
