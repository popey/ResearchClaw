from __future__ import annotations

import asyncio

from researchclaw.app.crons.executor import CronExecutor
from researchclaw.app.crons.manager import CronManager
from researchclaw.app.crons.models import (
    CronJobRequest,
    CronJobSpec,
    DispatchSpec,
    DispatchTarget,
    JobRuntimeSpec,
    ScheduleSpec,
)


def _build_agent_job(
    *,
    job_id: str = "job-1",
    timeout_seconds: int = 5,
) -> CronJobSpec:
    return CronJobSpec(
        id=job_id,
        name="Test Job",
        enabled=True,
        schedule=ScheduleSpec(cron="0 0 * * *", timezone="UTC"),
        task_type="agent",
        request=CronJobRequest(
            input=[
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "hello"}],
                },
            ],
        ),
        dispatch=DispatchSpec(
            channel="console",
            target=DispatchTarget(user_id="main", session_id="main"),
            mode="stream",
            meta={},
        ),
        runtime=JobRuntimeSpec(
            max_concurrency=1,
            timeout_seconds=timeout_seconds,
            misfire_grace_seconds=60,
        ),
        meta={},
    )


def test_cron_executor_raises_on_failed_response_event() -> None:
    class _Runner:
        async def stream_query(self, request):
            del request
            yield {
                "object": "response",
                "status": "failed",
                "type": "response",
                "error": {"message": "peer closed connection"},
            }

    class _ChannelManager:
        async def send_event(self, **kwargs):
            del kwargs

    executor = CronExecutor(runner=_Runner(), channel_manager=_ChannelManager())

    async def _run() -> None:
        await executor.execute(_build_agent_job())

    try:
        asyncio.run(_run())
    except RuntimeError as exc:
        assert "peer closed connection" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_cron_manager_tracks_pending_and_running_state() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    class _Executor:
        async def execute(self, job):
            del job
            started.set()
            await release.wait()

    manager = CronManager(repo=None, runner=object(), channel_manager=object())
    manager._executor = _Executor()  # noqa: SLF001

    job = _build_agent_job(timeout_seconds=30)

    async def _run() -> None:
        first = asyncio.create_task(manager._execute_once(job))  # noqa: SLF001
        await started.wait()

        second = asyncio.create_task(manager._execute_once(job))  # noqa: SLF001
        await asyncio.sleep(0)

        state = manager.get_state(job.id)
        assert state.running_count == 1
        assert state.pending_runs == 1
        assert state.last_status in {"running", "queued"}

        release.set()
        await asyncio.gather(first, second)

        final_state = manager.get_state(job.id)
        assert final_state.running_count == 0
        assert final_state.pending_runs == 0
        assert final_state.last_status == "success"

    asyncio.run(_run())


def test_cron_manager_stop_job_cancels_running_execution() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    class _Executor:
        async def execute(self, job):
            del job
            started.set()
            await release.wait()

    class _Repo:
        async def get_job(self, job_id):
            return _build_agent_job(job_id=job_id)

    manager = CronManager(repo=_Repo(), runner=object(), channel_manager=object())
    manager._executor = _Executor()  # noqa: SLF001

    job = _build_agent_job(job_id="job-stop", timeout_seconds=30)

    async def _run() -> None:
        task = asyncio.create_task(manager._execute_once(job))  # noqa: SLF001
        await started.wait()

        result = await manager.stop_job(job.id)
        assert result["cancelled"] == 1

        await asyncio.gather(task, return_exceptions=True)
        state = manager.get_state(job.id)
        assert state.last_status == "skipped"
        assert state.last_error == "cancelled"
        assert state.running_count == 0
        assert state.pending_runs == 0

    asyncio.run(_run())
