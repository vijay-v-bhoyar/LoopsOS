import json
import multiprocessing as mp
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest

import fleet_runtime as f


def compete(path, owner, fence, identity, start, queue, resource, amount=6):
    start.wait(10)
    try:
        f.Fleet(path).admit(owner,fence,identity,[{"resource":resource,"mode":"write"}],amount)
        queue.put("admitted")
    except f.FleetError:
        queue.put("blocked")


def execute(path, owner, fence, cwd, queue, seconds=15):
    try:
        result = f.run_job(f.Fleet(path),owner,fence,"child",[{"resource":"file:child","mode":"write"}],2,
                          [sys.executable,"-B","-c","import time; from pathlib import Path; Path('started').write_text('started'); time.sleep(30); Path('late').write_text('bad')"],cwd,seconds,["late"])
        queue.put(result)
    except Exception as exc:
        queue.put({"error":str(exc)})


class FleetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root/"fleet.sqlite"
        self.fleet = f.Fleet(self.db)
        self.fleet.init({"product":"test","target":"local","revision":"revision-1","configuration":"config-1"},10,2,4,120)
        self.owner = "coordinator"
        self.fence = self.fleet.acquire(self.owner)

    def tearDown(self):
        self.temp.cleanup()

    def claim(self, name):
        return [{"resource":name,"mode":"write"}]

    def run_output(self, name, text):
        cwd = self.root/name
        cwd.mkdir()
        return f.run_job(self.fleet,self.owner,self.fence,name,self.claim("file:"+name),2,
                         [sys.executable,"-B","-c",f"from pathlib import Path; Path('result.txt').write_text({text!r})"],str(cwd),5,["result.txt"])

    def plan(self):
        return {"expected_jobs":["a","b"],"steps":[[sys.executable,"-B","-c","from pathlib import Path; Path('joined.txt').write_text(Path('a/result.txt').read_text()+Path('b/result.txt').read_text())"]],"verify":[sys.executable,"-B","-c","from pathlib import Path; assert Path('joined.txt').read_text() == 'AB'"],"cwd":str(self.root),"seconds":5,"reserve":2,"artifacts":["joined.txt"],"criteria":["combined output AB"]}

    def race(self, resources, amount=6):
        ctx=mp.get_context("spawn")
        ready=ctx.Event(); queue=ctx.Queue()
        processes=[ctx.Process(target=compete,args=(str(self.db),self.owner,self.fence,str(i),ready,queue,r,amount)) for i,r in enumerate(resources)]
        for p in processes:p.start()
        ready.set()
        output=[queue.get(timeout=15) for _ in processes]
        for p in processes:
            p.join(15)
            self.assertEqual(p.exitcode,0)
        return output

    def test_multiprocess_aggregate_budget_race(self):
        self.assertEqual(sorted(self.race(["file:a","file:b"])),["admitted","blocked"])
        self.assertEqual(self.fleet.snapshot()["charged"],6)

    def test_multiprocess_shared_contract_race(self):
        self.assertEqual(sorted(self.race(["contract:api/v1","contract:api/v1"],2)),["admitted","blocked"])

    def test_multiprocess_disjoint_admission(self):
        self.assertEqual(self.race(["file:a","file:b"],2),["admitted","admitted"])
        with self.assertRaises(f.FleetError):
            self.fleet.admit(self.owner,self.fence,"c",self.claim("file:c"),2)

    def test_namespace_and_directory_conflicts(self):
        self.assertTrue(f.conflict(self.claim("file:src.v2"),self.claim("file:src.v2/a.py")))
        self.assertTrue(f.conflict(self.claim("state:db"),self.claim("state:db/table")))
        self.assertFalse(f.conflict([{"resource":"contract:v1","mode":"read"}],[{"resource":"contract:v1","mode":"read"}]))
        with self.assertRaises(f.FleetError):f.claims_valid(self.claim("file:Src"))
        with self.assertRaises(f.FleetError):f.claims_valid(self.claim("file:../a"))

    def test_unknown_surfaces_serialize(self):
        self.fleet.admit(self.owner,self.fence,"a",self.claim("*"),2)
        with self.assertRaises(f.FleetError):self.fleet.admit(self.owner,self.fence,"b",self.claim("file:b"),2)

    def test_lease_fencing_and_takeover(self):
        with self.fleet.tx() as db:db.execute("UPDATE fleet SET lease_until=0")
        new=self.fleet.acquire("replacement")
        self.assertGreater(new,self.fence)
        with self.assertRaises(f.FleetError):self.fleet.renew(self.owner,self.fence)
        with self.assertRaises(f.FleetError):self.fleet.admit(self.owner,self.fence,"old",self.claim("file:a"),2)

    def test_unknown_workers_prevent_takeover(self):
        self.fleet.admit(self.owner,self.fence,"a",self.claim("file:a"),2)
        with self.fleet.tx() as db:db.execute("UPDATE fleet SET lease_until=0")
        with self.assertRaises(f.FleetError):self.fleet.acquire("replacement")

    def test_reinit_does_not_reset_accounting(self):
        self.fleet.admit(self.owner,self.fence,"a",self.claim("file:a"),2)
        with self.assertRaises(FileExistsError):self.fleet.init({"product":"p","target":"t","revision":"r","configuration":"c"},10,2,4,120)
        self.assertEqual(self.fleet.snapshot()["charged"],2)

    def test_real_cancellation_and_wait(self):
        ctx=mp.get_context("spawn"); queue=ctx.Queue()
        process=ctx.Process(target=execute,args=(str(self.db),self.owner,self.fence,str(self.root),queue))
        process.start()
        try:
            deadline=time.monotonic()+10
            while not (self.root/"started").exists() and time.monotonic()<deadline:time.sleep(.05)
            self.assertTrue((self.root/"started").exists())
            self.fleet.cancel()
            result=queue.get(timeout=15)
            process.join(15)
            self.assertEqual(process.exitcode,0)
            self.assertEqual(result["status"],"cancelled")
            self.assertTrue(result["reaped"])
            self.assertFalse((self.root/"late").exists())
            self.assertEqual(self.fleet.snapshot()["charged"],2)
            with self.assertRaises(f.FleetError):self.fleet.admit(self.owner,self.fence,"new",self.claim("file:new"),2)
        finally:
            if process.is_alive():process.terminate();process.join(5)

    def test_real_timeout(self):
        result=f.run_job(self.fleet,self.owner,self.fence,"slow",self.claim("file:slow"),2,[sys.executable,"-B","-c","import time;time.sleep(30)"],str(self.root),1,["out"])
        self.assertEqual(result["status"],"timed_out")
        self.assertTrue(result["reaped"])

    def test_failed_job_and_missing_artifact_fail_closed(self):
        result=f.run_job(self.fleet,self.owner,self.fence,"fail",self.claim("file:fail"),2,[sys.executable,"-B","-c","raise SystemExit(3)"],str(self.root),5,["out"])
        self.assertEqual(result["status"],"failed")
        with self.assertRaises(f.FleetError):
            f.run_job(self.fleet,self.owner,self.fence,"missing",self.claim("file:missing"),2,[sys.executable,"-B","-c","pass"],str(self.root),5,["out"])
        self.assertEqual(self.fleet.snapshot()["charged"],4)

    def test_serial_integration_and_subject_receipt(self):
        self.run_output("a","A");self.run_output("b","B")
        receipt=f.integrate(self.fleet,self.owner,self.fence,self.plan())
        self.assertEqual(receipt["status"],"INTEGRATED_LOCALLY")
        self.assertEqual(receipt["subject"]["revision"],"revision-1")
        self.assertEqual((self.root/"joined.txt").read_text(),"AB")
        self.assertEqual(len(receipt["executions"]),2)
        with self.assertRaises(f.FleetError):f.integrate(self.fleet,self.owner,self.fence,self.plan())

    def test_final_acceptance_failure(self):
        self.run_output("a","A");self.run_output("b","B")
        plan=self.plan();plan["verify"]=[sys.executable,"-B","-c","raise SystemExit(1)"]
        with self.assertRaises(f.FleetError):f.integrate(self.fleet,self.owner,self.fence,plan)
        self.assertEqual(self.fleet.snapshot()["fleet"]["integration"],"failed")

    def test_integration_rejects_missing_jobs_and_empty_verify(self):
        self.run_output("a","A")
        with self.assertRaises(f.FleetError):f.integrate(self.fleet,self.owner,self.fence,self.plan())
        self.run_output("b","B")
        plan=self.plan();plan["verify"]=[]
        with self.assertRaises(f.FleetError):f.integrate(self.fleet,self.owner,self.fence,plan)

    def test_worker_artifact_drift_blocks_integration(self):
        self.run_output("a","A");self.run_output("b","B")
        (self.root/"a/result.txt").write_text("changed")
        with self.assertRaises(f.FleetError):f.integrate(self.fleet,self.owner,self.fence,self.plan())

    def test_invalid_invocation_does_not_charge(self):
        with self.assertRaises(f.FleetError):f.run_job(self.fleet,self.owner,self.fence,"a",self.claim("file:a"),2,["python","-c","pass"],str(self.root),5,["out"])
        self.assertEqual(self.fleet.snapshot()["charged"],0)

    def test_integration_charges_reservation(self):
        self.run_output("a","A");self.run_output("b","B")
        f.integrate(self.fleet,self.owner,self.fence,self.plan())
        self.assertEqual(self.fleet.snapshot()["charged"],6)

    def test_integration_cannot_overspend(self):
        self.run_output("a","A");self.run_output("b","B")
        plan=self.plan();plan["reserve"]=7
        with self.assertRaises(f.FleetError):f.integrate(self.fleet,self.owner,self.fence,plan)
        self.assertFalse((self.root/"joined.txt").exists())

    @unittest.skipUnless(os.name == "nt","Windows containment test")
    def test_descendant_stops_when_parent_exits(self):
        child="import time;from pathlib import Path;time.sleep(2);Path('escaped.txt').write_text('bad')"
        parent=f"import subprocess,sys;from pathlib import Path;subprocess.Popen([sys.executable,'-B','-c',{child!r}]);Path('done').write_text('done')"
        result=f.run_job(self.fleet,self.owner,self.fence,"tree",self.claim("file:done"),2,[sys.executable,"-B","-c",parent],str(self.root),5,["done"])
        self.assertEqual(result["status"],"succeeded")
        time.sleep(2.3)
        self.assertFalse((self.root/"escaped.txt").exists())

    def test_cancellation_failure_keeps_unresolved_reservation(self):
        from unittest.mock import patch
        with patch.object(f,"bounded",side_effect=f.ContainmentError("cannot prove termination")):
            with self.assertRaises(f.ContainmentError):
                f.run_job(self.fleet,self.owner,self.fence,"unknown",self.claim("file:unknown"),2,[sys.executable,"-B","-c","pass"],str(self.root),2,["out"])
        self.assertEqual(self.fleet.snapshot()["jobs"][0]["status"],"running")

    def test_actual_file_changes_exceed_claim(self):
        with self.assertRaisesRegex(f.FleetError,"actual changed files"):
            f.run_job(self.fleet,self.owner,self.fence,"wrong",self.claim("file:allowed"),2,[sys.executable,"-B","-c","from pathlib import Path;Path('outside.txt').write_text('bad')"],str(self.root),5,["outside.txt"])
        self.assertEqual(self.fleet.snapshot()["jobs"][0]["status"],"failed")

    def test_fractional_remaining_integration_budget(self):
        self.run_output("a","A");self.run_output("b","B")
        plan=self.plan();plan["seconds"]=1
        plan["steps"][0][3]="import time;time.sleep(.15);"+plan["steps"][0][3]
        receipt=f.integrate(self.fleet,self.owner,self.fence,plan)
        self.assertEqual(receipt["status"],"INTEGRATED_LOCALLY")
        self.assertEqual((self.root/"joined.txt").read_text(),"AB")
        self.assertEqual(len(receipt["executions"]),2)

    def test_nonfinite_and_boolean_duration_rejected_before_admission(self):
        for seconds in (float("nan"),float("inf"),float("-inf"),True,False,0,-1):
            with self.subTest(seconds=seconds):
                with self.assertRaises(f.FleetError):
                    f.run_job(self.fleet,self.owner,self.fence,"bad",self.claim("file:bad"),2,[sys.executable,"-B","-c","pass"],str(self.root),seconds,["out"])
                plan=self.plan();plan["seconds"]=seconds
                with self.assertRaises(f.FleetError):f.integrate(self.fleet,self.owner,self.fence,plan)
        self.assertEqual(self.fleet.snapshot()["charged"],0)


if __name__ == "__main__":
    unittest.main()
