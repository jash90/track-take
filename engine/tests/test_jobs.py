import time

import pytest

from tracktake import jobs, project


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.setattr(project, "PROJECTS", tmp_path / "projects")
    project.create("Job test")
    return jobs.JobManager(tmp_path / "jobs")


def wait(manager, job_id, until=("done", "failed", "cancelled"), timeout=30):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        job = manager.get(job_id)
        if job.status in until:
            return job
        time.sleep(0.1)
    raise AssertionError(f"job still {manager.get(job_id).status}")


def test_job_runs_in_its_own_process_and_reports(manager):
    job = manager.submit("analyze", "job-test", "t", "tracktake.jobs:selftest", {"seconds": 0.3})
    done = wait(manager, job.id)
    assert done.status == "done" and done.progress["done"] == done.progress["total"]
    assert "selftest started" in manager.view(done)["log_tail"]


def test_failure_is_reported(manager):
    job = manager.submit("analyze", "job-test", "t", "tracktake.jobs:selftest", {"fail": True})
    done = wait(manager, job.id)
    assert done.status == "failed" and "selftest failure" in done.message


def test_one_job_per_kind_and_project(manager):
    manager.submit("analyze", "job-test", "t", "tracktake.jobs:selftest", {"seconds": 3})
    with pytest.raises(jobs.Conflict):
        manager.submit("analyze", "job-test", "t", "tracktake.jobs:selftest")


def test_job_survives_a_server_restart_and_can_be_cancelled(manager, tmp_path):
    job = manager.submit("render", "job-test", "t", "tracktake.jobs:selftest", {"seconds": 20})
    wait(manager, job.id, until=("running",))
    restarted = jobs.JobManager(tmp_path / "jobs")  # a new server process reading the same records
    assert restarted.get(job.id).status == "running"
    time.sleep(0.5)
    assert restarted.get(job.id).progress["done"] > 1  # still making progress without the first manager
    restarted.cancel(job.id)
    assert wait(restarted, job.id).status == "cancelled"


def test_dead_worker_is_marked_failed(manager):
    job = manager.submit("analyze", "job-test", "t", "tracktake.jobs:selftest", {"seconds": 20})
    running = wait(manager, job.id, until=("running",))
    import os
    import signal

    os.killpg(running.pid, signal.SIGKILL)
    assert wait(manager, job.id).status == "failed"
