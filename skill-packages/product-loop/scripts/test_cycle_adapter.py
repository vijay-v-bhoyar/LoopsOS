"""Local fixture execution and adversarial admission checks; no model/provider calls."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import cycle_adapter as adapter

WORKER = '''import os,json,hashlib,time,sys
from pathlib import Path
mode=sys.argv[1]
if mode=="sleep": time.sleep(10)
if mode=="fail": sys.exit(7)
if mode=="absent": sys.exit(0)
if mode=="descendant":
 import subprocess
 subprocess.Popen([sys.executable,"-c","import time,pathlib;time.sleep(2);pathlib.Path('../descendant-late').write_text('escaped')"])
artifact=Path.cwd()/"artifact.txt"
r={"contract":"product-loop/local-cycle@1","run_id":os.environ["LOOP_RUN_ID"],"config_digest":os.environ["LOOP_CONFIG_DIGEST"],"parent_goal":json.loads(os.environ["LOOP_PARENT_GOAL"]),"result":"LOCAL_WORK_REPORTED","artifact":{"path":str(artifact),"sha256":hashlib.sha256(artifact.read_bytes()).hexdigest()}}
if mode=="stale": r["run_id"]="older-cycle"
if mode=="parent": r["parent_goal"]["id"]="different-goal"
Path(os.environ["LOOP_RECEIPT_PATH"]).write_text(json.dumps(r))
'''


class CycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        (self.repo / ".loop").mkdir()
        (self.repo / "artifact.txt").write_text("actual local fixture\n")
        (self.repo / "worker.py").write_text(WORKER)
        for args in (["init", "-b", "codex/fixture"], ["add", "."], ["-c", "user.name=Fixture", "-c", "user.email=fixture@invalid", "commit", "-m", "fixture"]):
            subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)
        self.config = {"schema": 1, "capability": "local-process", "parent_goal": {"id": "goal-1", "criteria": ["criterion-1"]},
                       "identity": adapter.snapshot(self.repo), "argv": [sys.executable, "-B", str(self.repo / "worker.py"), "ok"],
                       "pins": [{"path": str(Path(sys.executable).resolve()), "sha256": adapter.sha(sys.executable)},
                                {"path": str(self.repo / "worker.py"), "sha256": adapter.sha(self.repo / "worker.py")}],
                       "limits": {"max_cycles": 2, "wall_seconds": 10, "per_cycle_seconds": 2},
                       "expires_at_epoch": time.time() + 300, "environment": "minimal-local"}
        self.state = self.base / "state.json"

    def tearDown(self):
        self.temp.cleanup()

    def initialize(self, mode="ok"):
        self.config["argv"][-1] = mode
        adapter.initialize(self.state, self.config)

    def test_success_receipt_never_completes_parent_or_release(self):
        self.initialize()
        result = adapter.run_cycle(self.state, self.config)
        self.assertEqual(result["status"], "CYCLE_REPORTED")
        self.assertEqual(result["parent_acceptance"], "NOT_EVALUATED")
        self.assertEqual(result["release"], adapter.RELEASE)
        self.assertGreater(result["elapsed_seconds"], 0)

    @unittest.skipUnless(os.name=="nt","Windows Job containment")
    def test_success_reaps_descendants_before_terminal_record(self):
        self.initialize("descendant")
        result=adapter.run_cycle(self.state,self.config)
        self.assertEqual(result["status"],"CYCLE_REPORTED")
        time.sleep(2.1)
        self.assertFalse((self.base/"descendant-late").exists())

    @unittest.skipUnless(os.name=="nt","Windows Job containment")
    def test_unknown_job_cleanup_retains_active_reservation(self):
        self.initialize()
        real_close=adapter.WindowsJob.close
        def uncertain(job):
            real_close(job)
            raise adapter.ContainmentError("injected missing descendant confirmation")
        with patch.object(adapter.WindowsJob,"close",uncertain):
            result=adapter.run_cycle(self.state,self.config)
        self.assertEqual(result["status"],"UNKNOWN_CANCELLATION")
        self.assertIsNotNone(adapter.load_state(self.state,self.config)["active"])
        with self.assertRaises(adapter.Refused):adapter.run_cycle(self.state,self.config)

    def test_cumulative_cycle_and_reserved_wall_caps(self):
        self.initialize()
        for _ in range(2):
            self.assertEqual(adapter.run_cycle(self.state, self.config)["status"], "CYCLE_REPORTED")
        with self.assertRaisesRegex(adapter.Refused, "cycle-budget"):
            adapter.run_cycle(self.state, self.config)
        self.assertEqual(adapter.load_state(self.state, self.config)["seconds_reserved"], 4)

    def test_wall_reservation_refuses_next_cycle(self):
        self.config["limits"]["wall_seconds"] = 3
        self.initialize()
        adapter.run_cycle(self.state, self.config)
        with self.assertRaisesRegex(adapter.Refused, "wall-budget"):
            adapter.run_cycle(self.state, self.config)

    def test_nonzero_child_is_not_progress(self):
        self.initialize("fail")
        self.assertEqual(adapter.run_cycle(self.state, self.config)["status"], "FAILED")

    def test_missing_receipt_is_not_progress(self):
        self.initialize("absent")
        self.assertEqual(adapter.run_cycle(self.state, self.config)["status"], "FAILED")

    def test_stale_receipt_and_wrong_parent_are_not_progress(self):
        for mode in ("stale", "parent"):
            with self.subTest(mode=mode):
                state = self.base / (mode + ".json")
                config = copy.deepcopy(self.config)
                config["argv"][-1] = mode
                adapter.initialize(state, config)
                self.assertEqual(adapter.run_cycle(state, config)["status"], "FAILED")

    def test_existing_receipt_rejected_before_reservation(self):
        self.initialize()
        Path(str(self.state) + ".cycle-1.json").write_text("{}")
        with self.assertRaisesRegex(adapter.Refused, "preexisting"):
            adapter.run_cycle(self.state, self.config)
        self.assertEqual(adapter.load_state(self.state, self.config)["cycles_reserved"], 0)

    def test_stop_before_admission_writes_nothing(self):
        (self.repo / ".loop" / "STOP").write_text("stop")
        with self.assertRaisesRegex(adapter.Refused, "STOP"):
            self.initialize()
        self.assertFalse(self.state.exists())

    def test_wrong_repo_subdir_branch_head_and_dirty_contents(self):
        (self.repo / "artifact.txt").write_text("user edit")
        with self.assertRaisesRegex(adapter.Refused, "identity-or-content"):
            adapter.admission(self.config)
        with self.assertRaisesRegex(adapter.Refused, "wrong-repository-root"):
            adapter.snapshot(self.repo / ".loop")
        self.config["identity"]["branch"] = "main"
        with self.assertRaisesRegex(adapter.Refused, "branch-not"):
            adapter.admission(self.config)

    def test_pin_drift_and_missing_bundle(self):
        self.config["pins"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(adapter.Refused, "bundle-drift"):
            self.initialize()
        self.config["pins"] = []
        with self.assertRaisesRegex(adapter.Refused, "missing-bundle"):
            self.initialize()

    def test_release_and_provider_lanes_fail_closed(self):
        for capability in ("release", "provider", "local-with-provider"):
            self.config["capability"] = capability
            with self.assertRaisesRegex(adapter.Refused, "capabilities-blocked"):
                self.initialize()

    def test_expired_config_missing_budget_and_boolean_limits(self):
        self.config["expires_at_epoch"] = time.time() - 1
        with self.assertRaisesRegex(adapter.Refused, "expired"):
            self.initialize()
        self.config["limits"]["max_cycles"] = True
        with self.assertRaisesRegex(adapter.Refused, "cycle-cap"):
            self.initialize()
        del self.config["limits"]
        with self.assertRaises(adapter.Refused):
            self.initialize()

    def test_corrupt_ledger_and_reset_attempt_refused(self):
        self.initialize()
        with self.assertRaisesRegex(adapter.Refused, "already-exists"):
            self.initialize()
        state = adapter.read(self.state)
        state["seconds_reserved"] = -1
        adapter.write(self.state, state)
        with self.assertRaisesRegex(adapter.Refused, "corrupt"):
            adapter.run_cycle(self.state, self.config)

    def test_pending_interrupted_cycle_blocks_restart(self):
        self.initialize()
        state = adapter.read(self.state)
        state.update(cycles_reserved=1, seconds_reserved=2, active={"run_id": "interrupted"})
        adapter.write(self.state, adapter.seal(state))
        with self.assertRaisesRegex(adapter.Refused, "interrupted"):
            adapter.run_cycle(self.state, self.config)

    def test_one_writer_lock(self):
        self.initialize()
        with adapter.Lock(self.state):
            with self.assertRaisesRegex(adapter.Refused, "state-locked"):
                adapter.run_cycle(self.state, self.config)

    def test_park_reconsider_only_changed_prerequisite_once(self):
        self.initialize()
        event = {"action": "park", "item": "B-1", "prerequisites": {"input": "missing"}, "reason": "need owner preference"}
        self.assertEqual(adapter.parked_event(self.state, self.config, event)["status"], "PARKED")
        event["action"] = "reconsider"
        with self.assertRaisesRegex(adapter.Refused, "unchanged"):
            adapter.parked_event(self.state, self.config, event)
        event["prerequisites"]["input"] = "supplied-evidence-hash"
        self.assertEqual(adapter.parked_event(self.state, self.config, event)["status"], "REVALIDATION_REQUIRED")
        with self.assertRaisesRegex(adapter.Refused, "already-reconsidered"):
            adapter.parked_event(self.state, self.config, event)
        event["prerequisites"]["input"] = "newer-evidence-hash"
        adapter.parked_event(self.state, self.config, event)
        event["prerequisites"]["input"] = "supplied-evidence-hash"
        with self.assertRaisesRegex(adapter.Refused, "already-reconsidered"):
            adapter.parked_event(self.state, self.config, event)

    def test_config_full_file_hash_not_prefix(self):
        file = self.base / "config.json"
        adapter.write(file, self.config)
        self.assertEqual(adapter.load_config(file, adapter.sha(file)), self.config)
        with self.assertRaises(adapter.Refused):
            adapter.load_config(file, adapter.sha(file)[:12])

    def test_state_cannot_pollute_product_identity(self):
        with self.assertRaisesRegex(adapter.Refused, "outside-product"):
            adapter.initialize(self.repo / "state.json", self.config)

    def test_duplicate_json_and_huge_integer_rejected(self):
        path = self.base / "bad.json"
        for content in ('{"x":1,"x":2}', '{"x":' + '9' * 5000 + '}'):
            path.write_text(content)
            with self.assertRaises(adapter.Refused):
                adapter.read(path)

    def test_unknown_cancellation_preserves_active(self):
        self.config["limits"]["per_cycle_seconds"] = 0.01
        self.initialize("sleep")
        class Child:
            pid = 12345678
            returncode = None
            stdin = io.BytesIO()
            def poll(self): return None
        with patch.object(adapter.subprocess, "Popen", return_value=Child()), patch.object(adapter, "WindowsJob"), patch.object(adapter, "terminate", side_effect=adapter.Refused("injected cancellation refusal")), patch.object(adapter, "admission", return_value={}):
            result = adapter.run_cycle(self.state, self.config)
        self.assertEqual(result["status"], "UNKNOWN_CANCELLATION")
        self.assertIsNotNone(adapter.load_state(self.state, self.config)["active"])
        with self.assertRaisesRegex(adapter.Refused, "interrupted"):
            adapter.run_cycle(self.state, self.config)

    def test_actual_timeout_reaps_owned_process(self):
        self.config["limits"]["per_cycle_seconds"] = 0.2
        self.initialize("sleep")
        result = adapter.run_cycle(self.state, self.config)
        self.assertEqual(result["status"], "TIMED_OUT")
        self.assertIsNotNone(result["returncode"])
        self.assertIsNone(adapter.load_state(self.state, self.config)["active"])

    def test_actual_stop_cancels_inflight_owned_process(self):
        self.initialize("sleep")
        timer = threading.Timer(0.6, lambda: (self.repo / ".loop" / "STOP").write_text("stop"))
        timer.start()
        try:
            result = adapter.run_cycle(self.state, self.config)
        finally:
            timer.join()
        self.assertEqual(result["status"], "CANCELLED")
        self.assertIsNotNone(result["returncode"])

    def test_stop_after_reservation_before_dispatch_is_cancelled(self):
        self.initialize()
        original=adapter.admission
        calls=0
        def stop_on_second(config):
            nonlocal calls
            calls+=1
            if calls==2:(self.repo/".loop/STOP").write_text("stop")
            return original(config)
        with patch.object(adapter,"admission",side_effect=stop_on_second):
            result=adapter.run_cycle(self.state,self.config)
        self.assertEqual(result["status"],"CANCELLED")
        self.assertIsNone(result["returncode"])
        self.assertEqual(adapter.load_state(self.state,self.config)["cycles_reserved"],1)


if __name__ == "__main__":
    unittest.main()
