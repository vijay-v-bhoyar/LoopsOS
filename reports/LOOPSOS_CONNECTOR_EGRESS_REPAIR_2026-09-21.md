# LoopsOS connector egress repair — H01

**Local result: PASS for the connector DNS-to-socket boundary. Parent goal: PARTIAL. Enterprise release: NO_GO.**

This continuation strengthens Owner 5 security assurance, with implications for
Owner 3 agentic actions, Owner 9 data protection and Owner 10 independent challenge.
All thirteen original owner dispositions and parent acceptance requirements remain
in scope in the [detailed assessment](LOOPSOS_13_OWNER_REPAIR_ASSESSMENT_2026-09-21.md).

## What the red team reproduced

H01 was previously an untested hypothesis. An independent local probe exercised
the actual HTTPX protocol path with controlled DNS and a fake socket stream. The
first endpoint lookup returned a public address, but the connection layer received
the unresolved hostname and a second simulated lookup selected loopback. The
synthetic bearer-bearing request reached that stream. A second scenario showed
an ambient `HTTPS_PROXY` routing the connector through an unallowlisted proxy.

These are reproduced destination-binding failures. No real credential was used
or disclosed. Fake TLS streams do not establish that a deployed attacker could
complete a certificate-valid handshake; no hosted SSRF exploit is claimed.
The [baseline trace](../output/loopsos-enterprise-repair/h01/independent-baseline.json)
and its source hash remain unchanged.

## What the blue team changed

The default connector now uses a public HTTPX/HTTPCore transport implementation.
Every new connection resolves the hostname asynchronously, rejects the complete
answer set if any address is unsafe, and passes only a checked numeric address to
the socket backend. A failed candidate can fall back only to another address from
that same validated set. It cannot fall back to resolving the hostname again.

TLS uses the original hostname for SNI and mandatory certificate verification;
HTTP Host also remains the original origin. Ambient proxy routing is disabled.
Private, reserved, nonglobal, scoped and malformed addresses are denied, as are
known IPv6 translation/tunnel ranges including NAT64, mapped IPv4, 6to4 and Teredo.
The independent reviewer identified the NAT64 edge case during implementation.

Initial DNS validation now runs asynchronously with a timeout, so it does not
block the event loop. Connection-time resolution and numeric candidate attempts
share a connect deadline. This is not a single end-to-end deadline across every
read, TLS stage and retry. Existing policy-denial, retry and uncertain-effect
accounting contracts are preserved. No uncertain mutation is automatically
refunded or redispatched.

Both deployment requirements files explicitly pin the directly used HTTPcore and
AnyIO dependencies. The full suite initially caught a missing root mirror update;
the root file was corrected, and the original equality assertion was retained.
The README's outdated release-decision paragraph was also aligned with the
existing protected policy and authenticated review contract.

## Evidence actually run

| Check | Observed result | Boundary |
|---|---|---|
| Focused connector suite | 18 passed | Includes mixed/empty DNS, unsafe literals, IPv6 translation, reconnect, deadlines, SNI/Host, proxy isolation and error mapping |
| Independent challenge | 15/15 passed | Separate probe author; real HTTPX/httpcore flow with controlled socket/TLS doubles |
| Numeric backend probes | IPv4 and IPv6 passed | Real AnyIO path; final platform connect intercepted; any extra DNS lookup fails the probe |
| Loopback connection | Passed within the focused suite | Actual local HTTP server and default development transport; no external traffic |
| Full authority suite | 361 passed executions, 1 skipped | 362 executions, 342 distinct cases; 20 imported API cases are discovered twice |
| Release browser journey | 6 passed | Desktop and mobile against the local authority, including approval and subsequent rejection |
| Skill registry | PASS | Unchanged digest and lifecycle policy 1.1.0 |
| Graph refresh | 163 code files, 2,010 nodes, 6,257 edges | 81 unresolved structural references; zero dangling endpoints |

The skipped authority case needs a PostgreSQL test DSN. That integration is
unproven. Existing UI unit and full-browser evidence is retained for unchanged UI
sources; those full suites were not rerun in this connector slice. The current
six-case release journey is newly executed evidence. Counts from overlapping
suites are not additive unique-test totals.

The first full run had 362 executions with one failure and one skip: root and
authority dependency manifests differed. That failure remains in
`output/loopsos-enterprise-repair/authority-attempt-1.log`. The corrected full run
and independent closure are retained under [the H01 evidence directory](../output/loopsos-enterprise-repair/h01/).

## Exact identity and history

The [completion receipt](../output/loopsos-enterprise-repair/h01/completion-receipt.json)
binds current checks, source hashes, original parent run, sole conductor and sole
delivery engine. The current source manifest covers **312 files**:

`7089a7a3bf657d44b69e0eb04975b79288ea22381ae1f8a3745740e24bca0876`

Registry: `skill-fleet/registry.json`, lifecycle policy **1.1.0**; registry SHA-256:

`1a3b198b8d6a6108ab0a3a8a194e86fc22039465ce724ee8782ba8ab732974b0`

The prior assessment, risk register, parent run and verification are preserved
under H01 `*-before` artifacts. The [independent review](../output/loopsos-enterprise-repair/h01/independent-review.md)
records source hashes, raw probe results and a corrected stale harness
expectation without changing product behavior to satisfy it.

## Known but unaddressed enterprise risk

This repair covers `ToolRegistry` connector reads, probes, actions and compensation
using its default transport. `AuditAnchorDispatcher` has a separate HTTP client
and needs its own egress review. Trusted application code can inject a custom
transport; that composition must remain outside untrusted write authority.

Public destinations can forward requests internally, and enterprise networks may
remap public addresses or use custom translation prefixes. Hosted TLS custody,
resolver behavior, independently enforced firewall policy and live-socket
revocation remain unproven. Existing pooled sockets remain connected to their
validated peer; DNS changes alone do not revoke them. Conservative effect charging
after dispatch begins may require authorized reconciliation even when a subsequent
transport denial prevents a connection.

The original organizational, IdP, provider, retention, cryptographic, operational
and independent enterprise-signoff prerequisites remain open. Scanner coverage
also remains degraded; this change is not a substitute for the pending advisory
scan. No deployment, live mutation, external notification or provider charge was
performed. The next locally runnable security work is the separate audit-anchor
egress review; hosted tests require a named authorized target and approved network
policy. H01 remains **PARTIAL_LOCAL_CONNECTOR_REPAIRED**, not enterprise-closed.

Implementation references: the official [HTTPCore network-backend contract](https://www.encode.io/httpcore/network-backends/)
and [HTTPX custom transport contract](https://www.python-httpx.org/advanced/transports/),
checked 2026-09-21. Operational details are in [CONNECTOR_EGRESS.md](../authority/CONNECTOR_EGRESS.md).
