# Owner 6 method

**Add:** current signing/trust-root security, anti-replay and anti-downgrade, as well as long-lived confidentiality and crypto agility.

**Red tests:** protected ingress hides weak downstream/export/backup paths; a correctly signed but revoked old package restores dangerous authority.

**Blue controls and acceptance:** enumerate cryptographic paths and protected data lifetimes; test negotiated algorithms, key rotation/revocation, signer identity, audience, and rollback rejection. Test a validly signed malicious package: signature verification may succeed while behavioral containment must deny prohibited effects.

**Required output:** CBOM, approved algorithms/issuers, migration evidence, lifetime assumptions, unobservable vendor paths. A signature proves an authenticated provenance property, not safe behavior; future cryptanalytic resistance cannot be guaranteed.

## Execution prerequisites

Use the shared enterprise-ai-assurance-loop verifier and its pinned owner catalog. Collector observations require raw artifacts and authenticated scope. Local oracle fixtures exercise this skill's assessment logic only; they do not execute these scenarios against a real product. For enterprise validation obtain a named authorized target, approved thresholds, accessible data/tool paths, a protected collector, the accountable domain owner and independent challenge. Declare inaccessible observations as missing or untestable with a reason.
