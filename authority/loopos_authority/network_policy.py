"""Public destination policy based on IANA's IPv6 allocation registries.

The address snapshot below was checked against IANA on 2026-09-21. Python's
``ipaddress.is_global`` is useful defense in depth, but its classification can
lag special-purpose assignments and runtime releases. The connector and
configuration validator share this narrower registry-backed policy so they
cannot drift independently.
"""
from __future__ import annotations

import ipaddress
import json
from importlib.resources import files


_POLICY = json.loads(files(__package__).joinpath("ipv6_egress_policy.json").read_text(encoding="utf-8"))
IPV6_GLOBAL_UNICAST_ALLOCATIONS = tuple(
    ipaddress.IPv6Network(prefix) for prefix in _POLICY["global_unicast_allocations"]
)
IPV6_IANA_GLOBALLY_REACHABLE_SPECIALS = tuple(
    ipaddress.IPv6Network(prefix) for prefix in _POLICY["globally_reachable_special_assignments"]
)
IPV6_IETF_PROTOCOL_ASSIGNMENTS = ipaddress.IPv6Network(_POLICY["partially_allocated_special_parent"])
IPV6_BLOCKED_SPECIAL_DESTINATIONS = tuple(
    ipaddress.IPv6Network(prefix) for prefix in _POLICY["blocked_special_destinations"]
)


def is_public_global_address(value: str | ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return whether a destination is public under the current egress policy.

    IPv6 is allowlisted by IANA's global-unicast allocation table, with the
    partially allocated 2001::/23 further restricted to IANA entries marked
    globally reachable. Translation and 6to4 destinations are not supported.
    IPv4 uses Python's standard global classification with explicit special
    and local-use exclusions.
    """
    if isinstance(value, str) and "%" in value:
        return False
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False

    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None or address.sixtofour is not None or address.teredo is not None:
            return False
        if address in IPV6_IETF_PROTOCOL_ASSIGNMENTS:
            return any(address in network for network in IPV6_IANA_GLOBALLY_REACHABLE_SPECIALS)
        if not any(address in network for network in IPV6_GLOBAL_UNICAST_ALLOCATIONS):
            return False
        # 6to4 and RFC 6052 translation prefixes can route through or encode
        # private IPv4 destinations despite global allocation or reachability.
        if any(address in network for network in IPV6_BLOCKED_SPECIAL_DESTINATIONS):
            return False
        return True

    return bool(
        address.is_global
        and not address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
    )
