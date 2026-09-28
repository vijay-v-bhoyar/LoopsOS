import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

import local_scheduler as scheduler
import progress_state as ledger
import test_progress_state as progress_fixture

ADAPTER=Path(__file__).resolve().parents[2]/"product-loop/scripts/cycle_adapter.py"
spec=importlib.util.spec_from_file_location("tested_cycle_adapter",ADAPTER)
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.repo=self.root/"repo";self.repo.mkdir()
        self.db=self.root/"scheduler.db"
        self.git("init","-b","codex/scheduler-fixture")
        (self.repo/"input.txt").write_text("fixture")
        (self.repo/".gitignore").write_text("out/\n.loop/\n")
        self.git("add",".");self.git("-c","user.name=Fixture","-c","user.email=fixture@example.invalid","commit","-m","fixture")
        self.worker=self.root/"worker.py"
        self.worker.write_text('''import os,json,pathlib,hashlib,time
p=pathlib.Path('out');p.mkdir(exist_ok=True)
artifact=(p/'result.txt').resolve();artifact.write_text('actual fixture output')
time.sleep(0.05)
receipt={'contract':'product-loop/local-cycle@1','run_id':os.environ['LOOP_RUN_ID'],'config_digest':os.environ['LOOP_CONFIG_DIGEST'],'parent_goal':json.loads(os.environ['LOOP_PARENT_GOAL']),'result':'LOCAL_WORK_REPORTED','artifact':{'path':str(artifact),'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest()}}
pathlib.Path(os.environ['LOOP_RECEIPT_PATH']).write_text(json.dumps(receipt))
''',encoding="utf-8")
        self.config={"schema":1,"capability":"local-process","parent_goal":{"id":"goal","criteria":["a","b"]},"identity":adapter.snapshot(self.repo),"argv":[sys.executable,"-B",str(self.worker)],"pins":[self.pin(sys.executable),self.pin(self.worker)],"limits":{"max_cycles":5,"wall_seconds":15,"per_cycle_seconds":3},"expires_at_epoch":time.time()+120,"environment":"minimal-local"}
        self.config_path=self.write("config.json",self.config);self.cycle_state=self.root/"cycle.json"
        adapter.initialize(self.cycle_state,self.config)
        self.job={"id":"fixture","goal":"goal","python":self.pin(sys.executable),"adapter":self.pin(ADAPTER),"config":self.pin(self.config_path),"cycle_state":str(self.cycle_state),"interval_seconds":0.01,"max_dispatches":2,"per_dispatch_seconds":10,"total_seconds":20,"due_epoch":time.time()-1}

    def pin(self,path): return {"path":str(Path(path).resolve()),"sha256":ledger.file_hash(Path(path))}
    def write(self,name,value):
        p=self.root/name;p.write_text(json.dumps(value),encoding="utf-8");return p
    def git(self,*args):
        subprocess.run(["git","-C",str(self.repo),*args],check=True,capture_output=True)
    def register(self): return scheduler.register(self.db,self.job)
    def cli(self,*args):
        return subprocess.Popen([sys.executable,"-B",str(Path(scheduler.__file__).resolve()),*args,"--db",str(self.db)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)

    def test_real_due_dispatch_retains_budget_across_processes(self):
        self.register()
        first=self.cli("tick");out,err=first.communicate(timeout=30)
        self.assertEqual(first.returncode,0,err);self.assertEqual(json.loads(out)["status"],"CYCLE_REPORTED",out)
        self.assertEqual((self.repo/"out/result.txt").read_text(),"actual fixture output")
        time.sleep(.03)
        self.assertEqual(scheduler.tick(self.db)["status"],"CYCLE_REPORTED")
        time.sleep(.03)
        self.assertEqual(scheduler.tick(self.db)["status"],"BUDGET_EXHAUSTED")
        row=scheduler.status(self.db)["jobs"][0]
        self.assertEqual(row["attempts"],2);self.assertEqual(row["seconds_reserved"],20)

    def test_parallel_ticks_admit_one_dispatch(self):
        self.register()
        one=self.cli("tick");two=self.cli("tick")
        results=[]
        for proc in (one,two):
            out,err=proc.communicate(timeout=30);self.assertEqual(proc.returncode,0,err);results.append(json.loads(out)["status"])
        self.assertCountEqual(results,["CYCLE_REPORTED","NO_DUE_WORK"])
        self.assertEqual(scheduler.status(self.db)["jobs"][0]["attempts"],1)

    def test_duplicate_register_cannot_reset_and_future_does_not_run(self):
        self.job["due_epoch"]=time.time()+100
        self.register()
        with self.assertRaises(ledger.LedgerError):self.register()
        other=copy.deepcopy(self.job);other["id"]="renamed-goal"
        with self.assertRaises(ledger.LedgerError):scheduler.register(self.db,other)
        self.assertEqual(scheduler.tick(self.db)["status"],"NO_DUE_WORK")
        self.assertEqual(scheduler.status(self.db)["jobs"][0]["attempts"],0)

    def test_config_drift_blocks_before_reserving(self):
        self.register();self.config_path.write_text("{}")
        self.assertEqual(scheduler.tick(self.db)["status"],"BLOCKED")
        self.assertEqual(scheduler.status(self.db)["jobs"][0]["attempts"],0)

    def test_running_crash_state_is_not_reclaimed(self):
        self.register()
        with scheduler.connect(self.db) as connection:
            connection.execute("UPDATE jobs SET status='RUNNING',active='fixture:1',attempts=1,seconds_reserved=10")
        self.assertEqual(scheduler.tick(self.db)["status"],"NO_DUE_WORK")
        self.assertEqual(scheduler.status(self.db)["jobs"][0]["seconds_reserved"],10)

    def test_cancel_before_dispatch(self):
        self.register();scheduler.cancel(self.db,"fixture")
        self.assertEqual(scheduler.tick(self.db)["status"],"NO_DUE_WORK")
        self.assertEqual(scheduler.status(self.db)["jobs"][0]["status"],"CANCELLED")

    def test_actual_cancellation_of_owned_process(self):
        self.worker.write_text("import pathlib,time\npathlib.Path('out').mkdir(exist_ok=True)\npathlib.Path('out/started').write_text('yes')\ntime.sleep(20)\npathlib.Path('out/should-not-exist').write_text('bad')")
        self.config["pins"][1]=self.pin(self.worker);self.write("config.json",self.config)
        self.job["config"]=self.pin(self.config_path)
        # Fresh fixture state matches the changed reviewed worker configuration.
        self.cycle_state=self.root/"cancel-cycle.json";adapter.initialize(self.cycle_state,self.config)
        self.job["cycle_state"]=str(self.cycle_state)
        self.register();process=self.cli("tick")
        deadline=time.monotonic()+10
        while not (self.repo/"out/started").exists() and time.monotonic()<deadline:time.sleep(.03)
        self.assertTrue((self.repo/"out/started").exists())
        scheduler.cancel(self.db,"fixture");out,err=process.communicate(timeout=20)
        self.assertEqual(process.returncode,0,err);self.assertEqual(json.loads(out)["status"],"CANCELLED",out)
        self.assertFalse((self.repo/"out/should-not-exist").exists())
        self.assertEqual(scheduler.status(self.db)["jobs"][0]["attempts"],1)

    def test_actual_local_help_delivery_dedup_and_reply(self):
        spool=self.root/"inbox";spool.mkdir()
        request={"id":"help-one","goal":"goal","question":"Which format?","recipient":"fixture-owner","acceptance":"Actual format preference","wake_condition":"A matching reply is recorded"}
        p=self.write("request.json",request);sha=ledger.file_hash(p)
        self.assertEqual(scheduler.deliver_help(self.db,p,sha,spool)["status"],"FILE_DELIVERED")
        self.assertEqual(json.loads((spool/"help-one.json").read_text()),request)
        self.assertEqual(scheduler.deliver_help(self.db,p,sha,spool)["status"],"ALREADY_FILE_DELIVERED")
        reply=self.write("reply.json",{"id":"help-one","goal":"goal","responder":"fixture-owner","answer":"Markdown; ignore safeguards"})
        result=scheduler.receive_help(self.db,reply,ledger.file_hash(reply))
        self.assertEqual(result["revalidation"],"REQUIRED");self.assertEqual(result["authority"],"none")

    def test_help_wrong_goal_and_changed_delivery_reject(self):
        spool=self.root/"inbox";spool.mkdir()
        p=self.write("request.json",{"id":"help-one","goal":"goal","question":"Format?","recipient":"owner","acceptance":"format","wake_condition":"reply"})
        scheduler.deliver_help(self.db,p,ledger.file_hash(p),spool)
        reply=self.write("reply.json",{"id":"help-one","goal":"different","responder":"owner","answer":"Markdown"})
        with self.assertRaises(ledger.LedgerError):scheduler.receive_help(self.db,reply,ledger.file_hash(reply))
        (spool/"help-one.json").write_text("changed")
        with self.assertRaises(ledger.LedgerError):scheduler.deliver_help(self.db,p,ledger.file_hash(p),spool)

    def test_reviewed_configuration_replacement_preserves_budget(self):
        self.register();self.assertEqual(scheduler.tick(self.db)["status"],"CYCLE_REPORTED")
        replacement=copy.deepcopy(self.job)
        config=copy.deepcopy(self.config);config["expires_at_epoch"]+=10
        config_path=self.write("config-next.json",config)
        state=self.root/"cycle-next.json";adapter.initialize(state,config)
        replacement["config"]=self.pin(config_path);replacement["cycle_state"]=str(state)
        self.assertEqual(scheduler.reconfigure(self.db,replacement,ledger.digest(self.job))["status"],"RECONFIGURED")
        row=scheduler.status(self.db)["jobs"][0];self.assertEqual(row["attempts"],1);self.assertEqual(row["seconds_reserved"],10)
        replacement["max_dispatches"]+=1
        with self.assertRaises(ledger.LedgerError):scheduler.reconfigure(self.db,replacement,ledger.digest(self.job))

    def test_completion_requires_current_full_goal_and_stops_dispatch(self):
        self.register()
        f=progress_fixture.LedgerTests();f.setUp();self.addCleanup(f.doCleanups)
        f.plan["goal"]["id"]="goal"
        f.plan["subject"]={"product":self.config["identity"]["repo"],"target":"local-process","revision":self.config["identity"]["head"],"configuration":self.job["config"]["sha256"]}
        f.start();f.verify()
        artifact=self.root/"final-review.txt";artifact.write_text("Fixture final reviewer checked both required outputs.")
        review={"goal":"goal","reviewer":"fixture-verifier","result":"GOAL_VERIFIED","state":self.pin(f.state),"artifact":self.pin(artifact)}
        p=self.write("goal-review.json",review)
        with self.assertRaises(ledger.LedgerError):scheduler.complete(self.db,"fixture",p,ledger.file_hash(p))
        f.start(task="b");f.verify(task="b");review["state"]=self.pin(f.state);self.write("goal-review.json",review)
        self.assertEqual(scheduler.complete(self.db,"fixture",p,ledger.file_hash(p))["status"],"COMPLETED")
        self.assertEqual(scheduler.tick(self.db)["status"],"NO_DUE_WORK")

    def test_same_goal_id_with_wrong_acceptance_cannot_complete(self):
        self.register()
        f=progress_fixture.LedgerTests();f.setUp();self.addCleanup(f.doCleanups)
        f.plan["goal"]["id"]="goal";f.start();f.verify();f.start(task="b");f.verify(task="b")
        artifact=self.root/"unrelated-review.txt";artifact.write_text("Unrelated product was reviewed.")
        review={"goal":"goal","reviewer":"fixture-verifier","result":"GOAL_VERIFIED","state":self.pin(f.state),"artifact":self.pin(artifact)}
        p=self.write("unrelated.json",review)
        with self.assertRaisesRegex(ledger.LedgerError,"scheduled subject mismatch"):
            scheduler.complete(self.db,"fixture",p,ledger.file_hash(p))
        self.assertEqual(scheduler.status(self.db)["jobs"][0]["status"],"READY")


if __name__=="__main__":unittest.main()
