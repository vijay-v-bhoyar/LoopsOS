"""Three complete synthetic journeys. FIXTURE results never authorize live release."""
import argparse
import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from support import Fixture
from enterprise_assurance.common import require, write, digest
from enterprise_assurance.operations import export_pack


def run(output):
    output = Path(output)
    require(not output.exists(), "choose a new demo output directory")
    output.mkdir(parents=True)
    results = []
    for product in ("knowledge", "insurance", "agentic"):
        root = output / product; root.mkdir()
        f = Fixture(root, product=product)
        plan = f.engine.plan("test-run")
        f.populate()
        f.engine.challenge("test-run", f.review())
        decision = f.engine.decide("test-run")
        require(decision["decision"] == "GO" and not decision["deployment_authorized"], "synthetic gate behavior failed")
        # Add an explicit known-unaddressed risk after the first review. The decision must change.
        f.engine.record_risk("test-run", f.sign("risk", f.risk()))
        blocked = f.engine.decide("test-run")
        require(blocked["decision"] == "NO_GO" and blocked["risks"], "unaddressed risk was hidden")
        write(root / "trust-test-only.json", f.trust)
        write(root / "subject.json", f.subject); write(root / "profile.json", f.profile); write(root / "plan.json", plan)
        export_pack(f.engine, "test-run", root / "export")
        results.append({"product": product, "initial_fixture_decision": decision["decision"], "after_unaddressed_risk": blocked["decision"],
                        "delivery_engine": decision["delivery_engine"], "owners": len(decision["coverage"]),
                        "live_release": "NO_GO", "trust_sha": digest(f.trust)})
    receipt = {"status": "PASS", "scope": "three synthetic end-to-end verifier journeys", "results": results, "authority": "none"}
    write(output / "receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--output", required=True, type=Path)
    import json
    print(json.dumps(run(parser.parse_args().output), indent=2))
