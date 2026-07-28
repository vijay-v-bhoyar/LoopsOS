# LoopOS Enterprise Deployment Gate

LoopOS has two explicit postures: `evaluation` and `enterprise`. Evaluation mode is browser-local and must not be used as an authority plane. Enterprise mode fails closed until every required binding is configured and runtime-verified.

## Required Bindings

| Binding | Required contract | Activation proof |
| --- | --- | --- |
| Identity | BFF-managed session; IdP groups mapped server-side to LoopOS roles | Session endpoint verifies tenant, subject, role, expiry, and CSRF protection |
| Persistence | LoopOS authority service and tenant-scoped durable database | Read/write/isolation/restart probes pass; browser storage is only a non-authoritative workspace cache |
| Audit | Authority hash chain replicated to an external append-only sink | Write, retrieve, correlation, clock, chain verification, and external-anchor probes pass |
| Transport | HTTPS for every non-local origin | Certificate, reachability, redirect, and hostname checks pass |
| Retention | Approved retention and deletion policy URL | Legal/security owners approve the policy and deletion evidence path |
| Operations | Named support contact and on-call route | Alert routing and incident exercise pass |
| Outbound policy | Exact host allowlist for AI/transcription endpoints | Egress policy and endpoint data-processing terms are approved |

The required `VITE_` values are documented in `.env.example`. They are public build configuration, never secrets. Tokens and service credentials belong only in the BFF or service runtime.

## Production Build

```bash
docker compose build
docker compose up -d
```

Terminate TLS at the enterprise ingress, keep the supplied security headers, and narrow `connect-src` in `nginx.conf` to approved origins. Do not set `VITE_LOOPOS_DEPLOYMENT_MODE=enterprise` until the authority API exists and the runtime probes are wired into `evaluateDeploymentPosture`.

## Release Gate

1. Pin the image by digest and attach SBOM, vulnerability scan, and provenance from the enterprise build service.
2. Run unit, design-token, build, Playwright, corpus-validation, and practicality-audit gates.
3. Test tenant isolation, session expiry, CSRF, audit append/retrieve, retention deletion, and restore in staging.
4. Confirm CSP and egress allowlists contain only approved service origins.
5. Record security, privacy, legal, product, and operations approval references.
6. Canary to an internal cohort; promote only when errors, latency, persistence, and audit delivery meet the runbook thresholds.

## Current Boundary

This repository now supplies the portal, deterministic recommendation engine, governed execution authority, single-instance SQLite persistence, tool/probe runtime, audit chain, and hardened containers. It does not supply the organization IdP/BFF, horizontally scalable managed database, external WORM/SIEM anchor, secrets manager, or organization-specific retention implementation. Production activation remains blocked until those bindings are integrated and verified.
