# Connector egress boundary

`ToolRegistry` uses `ConnectorTransport` for its default HTTP evidence, probe,
action and compensation requests. Explicit transports passed by trusted server
composition are dependency-injection seams (for example local test transports),
not request-controlled options. Changing that composition requires review.

The endpoint must have an exact allowlisted hostname, HTTPS, no credentials,
query or fragment. The explicit development exception permits HTTP to allowlisted
`localhost` or `127.0.0.1`, connected numerically to `127.0.0.1`.

Before credential issuance, bounded asynchronous DNS validation rejects an empty
answer or any nonglobal address. At each new TCP connection the network backend
resolves and validates the complete answer set again, then passes a checked
numeric address to the socket backend. Fallback may use another address from that
same validated set, never the unresolved hostname. DNS and candidate connection
attempts share a connect deadline. Initial validation has its own timeout;
this is not a total wall-clock deadline across all reads, retries or TLS stages.

IPv6 socket destinations are checked against the shared [IANA allocation
snapshot](loopos_authority/ipv6_egress_policy.json), which was checked on
2026-09-21 against IANA's Global Unicast and Special-Purpose registries. The
partially allocated `2001::/23` range permits only assignments IANA marks
globally reachable. Documentation, 6to4, NAT64 well-known and local-use ranges
are denied, even where a runtime classifies them as global. The browser literal
guard reads this same policy file; it does not resolve or pin domain names.
Supporting other ranges requires a reviewed update to the shared policy.

The original URL origin supplies the TLS server name, certificate hostname
verification and HTTP Host. HTTPS verification remains mandatory. Redirects
are rejected by the tool response reader. `trust_env=False` prevents ambient
proxy variables from substituting a different route. The connector does not
support a proxy route or ambient certificate overrides. A corporate proxy or CA
integration needs explicit implementation and verification, not an environment
variable that silently bypasses this boundary.

Connections may reuse an already validated public peer; every newly established
connection resolves again. DNS changes do not revoke an existing socket. This
control does not replace a separately enforced egress firewall, credential
revocation, certificate custody, or a kill switch that terminates live sessions.
An address classified as public can still be remapped by a network, service mesh,
custom NAT64 prefix, compromised resolver infrastructure or malicious public
service. Hosted routing and nonconnector egress remain separate proof obligations.
`AuditAnchorDispatcher` now composes this same connection guard with its own
exact configured hostname. Its signing, outbox and delivery contract is documented
in [AUDIT_ANCHOR_SECURITY.md](AUDIT_ANCHOR_SECURITY.md). Other clients and hosted
network enforcement remain outside this claim.

Reads treat a connection policy denial as terminal. External actions retain
their aggregate reservation after dispatch begins, including uncertain network
failures; the repair does not refund or redispatch an uncertain external effect.

## Verification

`authority/tests/test_connector_transport.py` exercises numeric destinations,
mixed A/AAAA answers, empty DNS, unsafe literals, translation ranges, reconnects,
original Host/SNI and certificate verification settings, error mapping, timeouts,
proxy isolation and an actual loopback development connection. Deterministic
stream doubles do not establish a hosted TLS handshake or production egress proof.

Implementation uses the public [HTTPCore network-backend API](https://www.encode.io/httpcore/network-backends/)
and [HTTPX transport API](https://www.python-httpx.org/advanced/transports/),
checked on 2026-09-21; directly used dependencies are pinned in requirements.txt.
