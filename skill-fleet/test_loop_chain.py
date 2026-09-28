import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import loop_chain


class ChainTests(unittest.TestCase):
    def chain(self, root: Path):
        stages = []
        for kind in ("vision", "build", "assurance", "release"):
            file = root / f"{kind}.json"; file.write_text(kind, encoding="utf-8")
            stages.append({"kind": kind, "goal": "goal-1", "artifact": {"path": file.name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}})
        stages[1]["engine"] = "codex-product-build-loop"
        stages[2]["result"] = "GOAL_VERIFIED"
        stages[3]["decision"] = "NO_GO"
        return {"goal": {"id": "goal-1", "criteria": ["verified output"]}, "delivery_engines": ["codex-product-build-loop"], "stages": stages}

    def test_valid_fail_closed_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(loop_chain.verify(self.chain(Path(tmp)), Path(tmp))["status"], "CHAIN_VERIFIED")

    def test_nested_engine_and_forged_receipt_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); chain = self.chain(root)
            chain["delivery_engines"].append("product-loop")
            with self.assertRaises(loop_chain.ChainError):
                loop_chain.verify(chain, root)
            chain = self.chain(root); chain["stages"][0]["artifact"]["sha256"] = "0" * 64
            with self.assertRaises(loop_chain.ChainError):
                loop_chain.verify(chain, root)


if __name__ == "__main__":
    unittest.main()
