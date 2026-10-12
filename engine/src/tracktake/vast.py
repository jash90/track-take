"""Rent a Vast.ai GPU, provision ComfyUI on it and reach it from this Mac through an SSH tunnel.

Everything goes through the official `vastai` CLI with `--raw` (JSON). Renting costs money, so `up` refuses offers
above `max_dph` and the CLI only rents with an explicit --yes. State lives in ~/.config/tracktake/vast.json.
"""

from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from tracktake.config import REPO_ROOT, STATE_DIR, VastSettings

SETUP_SCRIPT = REPO_ROOT / "comfy" / "provisioning" / "vast_setup.sh"
STATE_FILE = STATE_DIR / "vast.json"
LABEL = "tracktake"

Runner = Callable[[list[str]], str]


class VastError(RuntimeError):
    pass


def run_cli(args: list[str]) -> str:
    """Run `vastai <args>` and return stdout; the API key comes from `vastai set api-key` or VAST_API_KEY."""
    cmd = ["vastai", *args]
    if key := os.environ.get("VAST_API_KEY"):
        cmd += ["--api-key", key]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    out, err = r.stdout.strip(), r.stderr.strip()
    # vastai exits 0 on API errors and prints {"error": true, ...} (to stdout or stderr)
    for text in (out, err):
        if text.startswith("{") and '"error": true' in text:
            msg = json.loads(text).get("msg", text)
            hint = " - set the key with `uv run vastai set api-key <KEY>`" if "login" in msg else ""
            raise VastError(f"vastai {' '.join(args[:2])}: {msg}{hint}")
    if r.returncode != 0 or (not out and err):
        raise VastError(f"vastai {' '.join(args[:2])} failed: {(err or out)[:500]}")
    return r.stdout


@dataclass
class Offer:
    id: int
    gpu: str
    dph: float
    reliability: float
    inet_down: float
    disk_gb: float
    location: str
    download_cost: float = 0.0  # USD per GB

    @classmethod
    def from_raw(cls, o: dict) -> Offer:
        return cls(int(o["id"]), str(o.get("gpu_name", "")), float(o.get("dph_total", 0.0)),
                   float(o.get("reliability2", o.get("reliability", 0.0))), float(o.get("inet_down", 0.0)),
                   float(o.get("disk_space", 0.0)), str(o.get("geolocation", "")),
                   float(o.get("inet_down_cost", 0.0) or 0.0))

    def setup_cost(self, download_gb: float) -> float:
        """USD to download the models onto this host (billed per GB on top of the hourly price)."""
        return self.download_cost * download_gb


def state_path(name: str = "main") -> Path:
    return STATE_FILE if name == "main" else STATE_DIR / f"vast-{name}.json"


@dataclass
class State:
    """One rented instance. Several can run at once (workers), each with its own name and tunnel port."""

    instance_id: int
    dph: float
    ssh_host: str = ""
    ssh_port: int = 0
    tunnel_pid: int = 0
    created_at: float = 0.0
    name: str = "main"
    local_port: int = 0

    def save(self) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state_path(self.name).write_text(json.dumps(asdict(self), indent=2))

    @staticmethod
    def load(name: str = "main") -> State | None:
        path = state_path(name)
        return State(**json.loads(path.read_text())) if path.exists() else None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.local_port}"


def all_states() -> list[State]:
    names = ["main"] + sorted(p.stem.removeprefix("vast-") for p in STATE_DIR.glob("vast-*.json"))
    return [st for n in names if (st := State.load(n))]


def offer_query(s: VastSettings) -> str:
    return (f"gpu_name={s.gpu} num_gpus=1 verified=true rentable=true direct_port_count>=1 "
            f"reliability>{s.min_reliability} inet_down>{s.min_inet_down} disk_space>={s.disk_gb} cuda_max_good>=12.8 "
            f"inet_down_cost<={s.max_download_cost}")  # >=12.4 returns nothing for RTX 5090 (API quirk); Blackwell needs 12.8 anyway


def search_offers(s: VastSettings, run: Runner = run_cli, limit: int = 5) -> list[Offer]:
    """Cheapest matching offers at or below max_dph."""
    raw = json.loads(run(["search", "offers", offer_query(s), "-o", "dph_total", "--limit", "500",
                          "--storage", str(s.disk_gb), "--raw"]))  # price incl. our disk; default limit truncates
    offers = [Offer.from_raw(o) for o in raw]
    ok = [o for o in offers if o.dph <= s.max_dph and o.download_cost <= s.max_download_cost]
    # cheapest for a ~1 h job including the model download
    return sorted(ok, key=lambda o: o.dph + o.setup_cost(s.download_gb))[:limit]


def create(offer: Offer, s: VastSettings, run: Runner = run_cli, name: str = "main", local_port: int = 0) -> State:
    if offer.dph > s.max_dph:
        raise VastError(f"offer {offer.id} costs ${offer.dph:.3f}/h, above max_dph ${s.max_dph:.2f}")
    out = json.loads(run(["create", "instance", str(offer.id), "--image", s.image, "--disk", str(s.disk_gb),
                          "--ssh", "--direct", "--label", LABEL, "--raw"]))
    if not out.get("success"):
        if out.get("new_contract"):  # Vast sometimes makes the contract and still reports a failure: do not orphan it
            run(["destroy", "instance", str(out["new_contract"]), "-y"])
        raise VastError(f"create failed: {out.get('msg') or out.get('error') or 'success=false'}")
    state = State(int(out["new_contract"]), offer.dph, created_at=time.time(), name=name,
                  local_port=local_port or s.local_port)
    state.save()
    return state


def wait_running(state: State, run: Runner = run_cli, timeout: float = 900, poll: float = 10) -> State:
    """Poll until the instance runs, then record its direct SSH endpoint."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        info = json.loads(run(["show", "instance", str(state.instance_id), "--raw"]))
        status = info.get("actual_status")
        if status == "running":
            host, port = ssh_endpoint(info)
            state.ssh_host, state.ssh_port = host, port
            state.save()
            return state
        if status in ("exited", "offline") and info.get("intended_status") == "stopped":
            raise VastError(f"instance {state.instance_id} stopped ({info.get('status_msg', '')})")
        time.sleep(poll)
    raise VastError(f"instance {state.instance_id} not running after {timeout:.0f}s")


def ssh_endpoint(info: dict) -> tuple[str, int]:
    """Direct connection (public IP + mapped port 22) when available, else Vast's SSH proxy."""
    mapped = (info.get("ports") or {}).get("22/tcp") or []
    if info.get("public_ipaddr") and mapped:
        return str(info["public_ipaddr"]).strip(), int(mapped[0]["HostPort"])
    return str(info["ssh_host"]), int(info["ssh_port"])


def ssh_base(state: State, s: VastSettings, connect_timeout: int = 15) -> list[str]:
    return ["ssh", "-i", str(Path(s.ssh_key).expanduser()), "-p", str(state.ssh_port),
            "-o", "StrictHostKeyChecking=accept-new", "-o", f"ConnectTimeout={connect_timeout}",
            "-o", "ServerAliveInterval=30", f"root@{state.ssh_host}"]


def wait_ssh(state: State, s: VastSettings, timeout: float = 300) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if subprocess.run([*ssh_base(state, s), "true"], capture_output=True, check=False).returncode == 0:
            return
        time.sleep(5)
    raise VastError("SSH did not come up")


def provision(state: State, s: VastSettings) -> None:
    """Pipe vast_setup.sh to the instance: pinned ComfyUI + models + server on 127.0.0.1:remote_port."""
    args = [s.comfy_repo, s.comfy_commit, str(s.remote_port), *s.models]
    remote = "bash -s -- " + " ".join(shlex.quote(a) for a in args)
    with SETUP_SCRIPT.open("rb") as script:
        r = subprocess.run([*ssh_base(state, s), remote], stdin=script, check=False)
    if r.returncode != 0:
        raise VastError(f"provisioning failed (exit {r.returncode})")


def tunnel_alive(state: State) -> bool:
    if not state.tunnel_pid:
        return False
    try:
        os.kill(state.tunnel_pid, 0)
    except OSError:
        return False
    return True


def open_tunnel(state: State, s: VastSettings) -> State:
    """Forward localhost:local_port -> instance 127.0.0.1:remote_port, in the background."""
    if not state.local_port:
        state.local_port = s.local_port
    if tunnel_alive(state):
        return state
    cmd = [*ssh_base(state, s)[:-1], "-N", "-o", "ExitOnForwardFailure=yes",
           "-L", f"{state.local_port or s.local_port}:127.0.0.1:{s.remote_port}", f"root@{state.ssh_host}"]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    time.sleep(2)
    if proc.poll() is not None:
        raise VastError(f"tunnel exited with {proc.returncode}; is local port {state.local_port} free?")
    state.tunnel_pid = proc.pid
    state.save()
    return state


def close_tunnel(state: State) -> None:
    if tunnel_alive(state):
        os.kill(state.tunnel_pid, signal.SIGTERM)
    state.tunnel_pid = 0


def destroy(state: State, run: Runner = run_cli) -> float:
    """Stop billing. Returns the approximate cost of the session in USD."""
    close_tunnel(state)
    run(["destroy", "instance", str(state.instance_id), "-y"])
    hours = (time.time() - state.created_at) / 3600 if state.created_at else 0.0
    state_path(state.name).unlink(missing_ok=True)
    return hours * state.dph


PROBE_URL = ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/"
             "umt5_xxl_fp8_e4m3fn_scaled.safetensors")  # one of the files provisioning fetches anyway


class SlowHost(VastError):
    pass


def download_speed(state: State, s: VastSettings, mb: int = 1024, max_seconds: int = 45) -> float:
    """MB/s the worker really gets from Hugging Face (the advertised host bandwidth says little about it)."""
    cmd = (f"curl -sL -o /dev/null -r 0-{mb * 1024 * 1024 - 1} --max-time {max_seconds} "
           f"-w '%{{speed_download}}' {PROBE_URL}")
    r = subprocess.run([*ssh_base(state, s), cmd], capture_output=True, text=True, timeout=max_seconds + 60,
                       check=False)
    try:
        return float(r.stdout.strip().splitlines()[-1]) / 1e6
    except (ValueError, IndexError):
        return 0.0


def rent_fleet(count: int, s: VastSettings, run: Runner = run_cli, log=print, spares: int = 3,
               straggler_wait: float = 480) -> list[State]:
    """Rent `count` workers from one search (cheapest incl. model download, network breaks ties) and provision
    them in parallel. Each new host first downloads 1 GB from Hugging Face; one slower than `min_download_mbs` is
    destroyed and the slot takes the next offer (up to `spares` replacements in total); so does a host that never
    boots or never opens SSH. Workers failing later (provisioning) are destroyed. Once one worker is ready, the
    others get `straggler_wait` seconds more; a slot still not ready then is dropped (destroyed as soon as its
    current step returns) so the ready cards do not sit idle and paid. Returns the healthy ones."""
    import threading

    offers = search_offers(s, run=run, limit=500)
    ranked = sorted(offers, key=lambda o: (round(o.dph + o.setup_cost(s.download_gb), 2), -o.inet_down))
    pick, reserve = ranked[:count], ranked[count:count + spares]
    if not pick:
        raise VastError(f"no {s.gpu} offer matches (max ${s.max_dph}/h, download <= ${s.max_download_cost}/GB)")
    for o in pick:
        log(f"offer {o.id} {o.gpu} ${o.dph:.3f}/h + download ${o.setup_cost(s.download_gb):.2f} "
            f"net {o.inet_down:.0f} Mb/s {o.location}")
    ok: list[State] = []
    lock = threading.Lock()
    give_up = threading.Event()

    def dropped() -> None:
        if give_up.is_set():
            raise VastError("dropped: the job started without this worker")

    def bring_up(slot: int, offer: Offer) -> None:
        name, port = f"w{slot + 1}", s.local_port + 1 + slot
        while offer is not None:
            try:
                st = create(offer, s, run=run, name=name, local_port=port)
            except VastError as e:  # offer taken meanwhile, or a refused contract: next spare
                log(f"{name}: offer {offer.id} refused ({e})")
                with lock:
                    offer = reserve.pop(0) if reserve else None
                continue
            host_fault = True  # until SSH works, a failure is the host's, not ours: try another offer
            try:
                st = wait_running(st, run=run)
                dropped()
                wait_ssh(st, s)
                dropped()
                host_fault = False
                if s.models and s.min_download_mbs > 0:
                    speed = download_speed(st, s)
                    log(f"{name}: Hugging Face download {speed:.0f} MB/s on offer {offer.id}")
                    if speed < s.min_download_mbs:
                        host_fault = True
                        raise SlowHost(f"{speed:.0f} MB/s < {s.min_download_mbs:.0f} MB/s")
                dropped()
                provision(st, s)
                if s.models:
                    st = open_tunnel(st, s)
                with lock:
                    if give_up.is_set():
                        raise VastError("too late, the job started without it")
                    ok.append(st)
                log(f"{name}: ready (ssh root@{st.ssh_host} -p {st.ssh_port})")
                return
            except Exception as e:  # noqa: BLE001 - a broken or slow worker is destroyed; the slot may retry
                cost = destroy(st, run=run)
                log(f"{name}: failed ({e}); destroyed (~${cost:.2f})")
                with lock:
                    retry = (host_fault or isinstance(e, SlowHost)) and not give_up.is_set()
                    offer = reserve.pop(0) if retry and reserve else None
                if offer is not None:
                    log(f"{name}: trying offer {offer.id} ({offer.location})")

    threads = [threading.Thread(target=bring_up, args=(i, o), daemon=True) for i, o in enumerate(pick)]
    for t in threads:
        t.start()
    first_ready = None
    while any(t.is_alive() for t in threads):
        time.sleep(2)
        with lock:
            if ok and first_ready is None:
                first_ready = time.monotonic()
            if first_ready is not None and time.monotonic() - first_ready > straggler_wait:
                give_up.set()
                late = count - len(ok)
                log(f"starting with {len(ok)} of {count} workers; {late} not ready after "
                    f"{straggler_wait / 60:.0f} more min are dropped")
                return sorted(ok, key=lambda st: st.name)
    return sorted(ok, key=lambda st: st.name)
