from __future__ import annotations

import asyncio

from .engine import ExecutionEngine
from .store import AuthorityStore, Conflict


class ExecutionJobWorker:
    def __init__(
        self,
        store: AuthorityStore,
        engine: ExecutionEngine,
        worker_id: str,
        lease_seconds: int = 120,
        batch_size: int = 10,
        max_attempts: int = 5,
    ):
        self.store = store
        self.engine = engine
        self.worker_id = worker_id
        self.lease_seconds = max(lease_seconds, 3)
        self.batch_size = max(1, min(batch_size, 100))
        self.max_attempts = max(1, max_attempts)

    async def run_once(self, dispatch_source: str = "internal") -> int:
        jobs = self.store.claim_execution_jobs(self.worker_id, self.lease_seconds, self.batch_size)
        self.store.record_operational_signal(
            "execution_worker_dispatch",
            dispatch_source,
            {"worker_id": self.worker_id, "claimed_jobs": len(jobs)},
        )
        for job in jobs:
            owner_task = asyncio.current_task()
            heartbeat = asyncio.create_task(self._heartbeat(job["job_id"], owner_task))
            try:
                if job["command"] == "execute":
                    await self.engine.execute(job["tenant_id"], job["run_id"], reclaim_running=True)
                elif job["command"] == "rollback":
                    reason = str(job["payload"].get("reason") or "Durable rollback job.")
                    await self.engine.rollback(job["tenant_id"], job["run_id"], reason, reclaim_running=True)
                else:
                    raise RuntimeError(f"Unsupported execution job command: {job['command']}.")
                self.store.complete_execution_job(job["job_id"], self.worker_id)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                try:
                    self.store.fail_execution_job(
                        job["job_id"],
                        self.worker_id,
                        str(error) or error.__class__.__name__,
                        self.max_attempts,
                    )
                except Conflict:
                    pass
            finally:
                heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)
        return len(jobs)

    async def _heartbeat(self, job_id: str, owner_task: asyncio.Task[object] | None) -> None:
        while True:
            await asyncio.sleep(max(1, self.lease_seconds // 3))
            try:
                self.store.renew_execution_job(job_id, self.worker_id, self.lease_seconds)
            except Conflict:
                if owner_task:
                    owner_task.cancel()
                return
