"""Registry-bound IPv6 policy tests; no DNS or socket activity."""
from __future__ import annotations

import unittest

from loopos_authority.config import _http_host_is_valid
from loopos_authority.connector_transport import global_address


class PublicAddressPolicyTests(unittest.TestCase):
    def test_special_and_unallocated_ipv6_ranges_are_denied(self) -> None:
        for address in (
            "100::1",
            "100:0:0:1::1",
            "2001:2::1",
            "2001:10::1",
            "2001:1::4",
            "2001:db8::1",
            "2001:ffff::1",
            "2a20::1",
            "2d00::1",
            "3ffe::1",
            "3fff::1",
            "5f00::1",
        ):
            with self.subTest(address=address):
                self.assertFalse(global_address(address))
                self.assertFalse(_http_host_is_valid(address))

    def test_iana_globally_reachable_assignments_remain_allowed(self) -> None:
        for address in (
            "2001:1::1",
            "2001:1::2",
            "2001:1::3",
            "2001:3::1",
            "2001:4:112::1",
            "2001:20::1",
            "2001:30::1",
            "2001:4000::1",
            "2400::1",
            "2410::1",
            "2600::1",
            "2610::1",
            "2620::1",
            "2630::1",
            "2800::1",
            "2a00::1",
            "2a10::1",
            "2c00::1",
            "2606:4700:4700::1111",
        ):
            with self.subTest(address=address):
                self.assertTrue(global_address(address))
                self.assertTrue(_http_host_is_valid(address))


if __name__ == "__main__":
    unittest.main()
