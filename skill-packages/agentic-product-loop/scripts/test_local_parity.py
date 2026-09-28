"""Exercise the guard and direct runner against the same local admission contract."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import loop_guard

PRODUCT_SCRIPTS = Path(__file__).resolve().parents[2] / "product-loop" / "scripts"
sys.path.insert(0, str(PRODUCT_SCRIPTS))
import cycle_adapter
import test_cycle_adapter as cycle_fixtures


class ParityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = cycle_fixtures.CycleTests()
        self.fixture.setUp()
        self.config_path = self.fixture.base / "config.json"
        cycle_adapter.write(self.config_path, self.fixture.config)
        self.adapter_path = PRODUCT_SCRIPTS / "cycle_adapter.py"

    def tearDown(self):
        self.fixture.tearDown()

    def test_shared_admission_identical(self):
        via_guard = loop_guard.local_admission(str(self.adapter_path), str(self.config_path), cycle_adapter.sha(self.config_path))
        self.assertEqual(via_guard, cycle_adapter.admission(self.fixture.config))

    def test_changed_config_refused_without_rebinding(self):
        old_hash = cycle_adapter.sha(self.config_path)
        config = self.fixture.config
        config["limits"]["max_cycles"] += 1
        cycle_adapter.write(self.config_path, config)
        with self.assertRaisesRegex(ValueError, "config-hash"):
            loop_guard.local_admission(str(self.adapter_path), str(self.config_path), old_hash)

    def test_changed_adapter_never_imported(self):
        fake = self.fixture.base / "unsafe.py"
        marker = self.fixture.base / "executed"
        fake.write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n")
        with self.assertRaisesRegex(ValueError, "adapter-hash"):
            loop_guard.local_admission(str(fake), str(self.config_path), cycle_adapter.sha(self.config_path))
        self.assertFalse(marker.exists())

    def test_canonical_reference_pin_is_required(self):
        with patch.object(loop_guard, "EXPECTED_REFERENCE_SHA256", "0" * 64):
            with self.assertRaisesRegex(ValueError, "reference-hash"):
                loop_guard.local_admission(str(self.adapter_path), str(self.config_path), cycle_adapter.sha(self.config_path))

    def test_manifest_parity(self):
        manifest = json.loads((Path(__file__).resolve().parents[1] / "references" / "local-cycle-contract.json").read_text())
        self.assertEqual(manifest["adapter_sha256"], cycle_adapter.sha(self.adapter_path))
        self.assertEqual(manifest["canonical_reference_sha256"].upper(), loop_guard.EXPECTED_REFERENCE_SHA256)
        self.assertEqual(manifest["contract"], cycle_adapter.CONTRACT)
        self.assertEqual(manifest["release"], cycle_adapter.RELEASE)


if __name__ == "__main__":
    unittest.main()
