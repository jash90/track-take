import pytest

from tracktake import remote
from tracktake.shards import split_args, wanted
from tracktake.vast import State

SHOTS = [{"id": f"s{i:02d}", "start": i * 5.0, "end": i * 5.0 + (3.0 if i % 3 else 8.0)} for i in range(1, 46)]


def workers(n: int) -> list[State]:
    return [State(instance_id=100 + i, dph=0.4, name=f"w{i + 1}", local_port=8190 + i) for i in range(n)]


def covered(assignments, orient):
    ids = [s for a in assignments if orient in a.orients for s in a.shots]
    return sorted(ids)


@pytest.mark.parametrize("n", [2, 3, 4, 6])
def test_every_shot_once_per_orientation(n):
    plan = remote.plan(SHOTS, workers(n))
    every = sorted(s["id"] for s in SHOTS)
    assert covered(plan, "landscape") == every
    assert covered(plan, "portrait") == every


def test_four_workers_two_per_format_with_leaders():
    plan = remote.plan(SHOTS, workers(4))
    leaders = {a.leader_of: a for a in plan if a.leader_of}
    assert set(leaders) == {"landscape", "portrait"}
    assert [f.name for f in leaders["landscape"].followers] == ["w2"]
    assert [f.name for f in leaders["portrait"].followers] == ["w4"]
    loads = [sum(s["end"] - s["start"] for s in SHOTS if s["id"] in a.shots) for a in plan if "landscape" in a.orients]
    assert max(loads) - min(loads) <= 8.0  # longest-first spreading keeps the slices even


def test_single_worker_does_everything():
    (a,) = remote.plan(SHOTS, workers(1))
    assert a.orients == ("landscape", "portrait") and a.leader_of == "both" and len(a.shots) == 45


@pytest.mark.parametrize("n", [1, 2, 4])
def test_one_orientation_uses_every_worker(n):
    plan = remote.plan(SHOTS, workers(n), ("portrait",))
    assert all(a.orients == ("portrait",) for a in plan) and len(plan) == n
    assert covered(plan, "portrait") == sorted(s["id"] for s in SHOTS) and covered(plan, "landscape") == []
    (leader,) = [a for a in plan if a.leader_of]
    assert leader.leader_of == "portrait" and len(leader.followers) == n - 1
    assert "--orient portrait" in remote.shard_command(plan[0], "codex")


def test_bad_orientation():
    with pytest.raises(ValueError):
        remote.plan(SHOTS, workers(2), ("square",))


def test_shots_keep_storyboard_order():
    for a in remote.plan(SHOTS, workers(4)):
        assert a.shots == sorted(a.shots)


def test_shard_commands():
    a = remote.plan(SHOTS, workers(4))[1]
    codex = remote.shard_command(a, "codex")
    assert codex.startswith(f"{remote.PY} scripts/full_clips.py") and "--orient landscape" in codex
    assert f"--shots {','.join(a.shots)}" in codex
    comfy = remote.shard_command(a, "comfy")
    assert "full_keys_comfy.py" in comfy and comfy.count("--shots") == 2 and " && " in comfy
    both = remote.shard_command(remote.plan(SHOTS, workers(1))[0], "codex")
    assert "--orient" not in both


def test_split_args_and_wanted():
    pos, opts = split_args(["dir", "codex", "http://a", "--shots", "s01,s02", "--orient", "portrait"])
    assert pos == ["dir", "codex", "http://a"]
    assert wanted(opts) == ({"s01", "s02"}, ("portrait",))
    assert wanted({}) == (None, ("landscape", "portrait"))
    with pytest.raises(ValueError):
        wanted({"orient": "square"})


def test_start_backgrounds_only_the_job(monkeypatch):
    sent = []
    monkeypatch.setattr(remote, "ssh", lambda state, s, command, **kw: sent.append(command) or "4242")
    assert remote.start(None, None, "clips_codex", "sleep 1") == 4242
    # `a && b && job &` would background the whole list, keeping the ssh session open until the job ends
    assert "; setsid nohup bash -c" in sent[0] and "&& setsid" not in sent[0]


def test_authorize_key_survives_missing_final_newline(tmp_path):
    import subprocess

    keys = tmp_path / "authorized_keys"
    keys.write_text("ssh-ed25519 AAAAaccount me@mac")  # as Vast writes it: no final newline
    cmd = remote.authorize_key_command("ssh-ed25519 AAAAgather root@w3", str(keys))
    for _ in range(2):  # idempotent
        subprocess.run(["bash", "-c", cmd.replace("mkdir -p ~/.ssh && ", "")], check=True)
    assert keys.read_text().splitlines() == ["ssh-ed25519 AAAAaccount me@mac", "ssh-ed25519 AAAAgather root@w3"]


def test_multi_gpu_host_gets_more_shots_and_all_comfy_urls():
    big, small = workers(2)
    big.gpus = 4
    plan = remote.plan(SHOTS, [big, small], ("landscape",))
    by = {a.worker.name: a for a in plan}
    assert len(by["w1"].shots) > 3 * len(by["w2"].shots)
    cmd = remote.shard_command(by["w1"], "codex")
    assert all(f"http://127.0.0.1:{18188 + i}" in cmd for i in range(4)) and "18192" not in cmd
