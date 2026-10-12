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

from tracktake import nethistory
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
    gpus: int = 1
    machine_id: int = 0
    host_id: int = 0
    ram_gb: float = 0.0

    @property
    def country(self) -> str:
        return country_of(self.location)

    @classmethod
    def from_raw(cls, o: dict) -> Offer:
        return cls(int(o["id"]), str(o.get("gpu_name", "")), float(o.get("dph_total", 0.0)),
                   float(o.get("reliability2", o.get("reliability", 0.0))), float(o.get("inet_down", 0.0)),
                   float(o.get("disk_space", 0.0)), str(o.get("geolocation", "")),
                   float(o.get("inet_down_cost", 0.0) or 0.0), int(o.get("num_gpus", 1) or 1),
                   int(o.get("machine_id") or 0), int(o.get("host_id") or 0), float(o.get("cpu_ram") or 0) / 1024)

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
    gpus: int = 1  # one ComfyUI per GPU, on remote_port + i

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
    return (f"gpu_name={s.gpu} num_gpus={s.gpus} verified=true rentable=true direct_port_count>=1 "
            f"reliability>{s.min_reliability} inet_down>{s.min_inet_down} disk_space>={s.disk_gb} cuda_max_good>=13.0 "
            f"inet_down_cost<={s.max_download_cost}")  # >=12.4 returns nothing for RTX 5090 (API quirk); Blackwell needs 12.8 anyway


RAM_PER_GPU_GB = 32  # each GPU runs its own ComfyUI, which stages ~30 GB of Wan weights in RAM
MIN_VRAM_GB = 24  # Wan 2.2 14B fp8 with its text encoder needs ~22 GB of VRAM
DLPERF_4090 = 92.0  # Vast's median DLPerf per RTX 4090, the card the clip timings were measured on


def country_of(location: str) -> str:
    """'North Carolina, US' -> 'US'."""
    return location.rsplit(",", 1)[-1].strip().upper() if location else ""


def in_regions(location: str, s: VastSettings) -> bool:
    return not s.regions or country_of(location) in {r.upper() for r in s.regions}


def matches(o: dict, s: VastSettings) -> bool:
    """The host filters of offer_query, applied to a raw offer (GPU model and count aside)."""
    return (o.get("direct_port_count", 0) >= 1 and o.get("reliability2", o.get("reliability", 0)) > s.min_reliability
            and o.get("inet_down", 0) > s.min_inet_down and o.get("disk_space", 0) >= s.disk_gb
            and (o.get("cuda_max_good") or 0) >= 13.0 and (o.get("inet_down_cost") or 0) <= s.max_download_cost
            and (not o.get("cpu_ram") or o["cpu_ram"] / 1024 >= RAM_PER_GPU_GB * max(1, int(o.get("num_gpus") or 1)) * 0.95))


def gpu_catalog(s: VastSettings, speeds: dict[str, float], run: Runner = run_cli) -> list[dict]:
    """Every GPU model on offer right now, for choosing the card: how many offers pass our host filters, prices per
    host size (1, 2, 4, 8 GPUs), VRAM and the clip speed relative to an RTX 4090 (measured where known, else
    estimated from DLPerf, damped because Wan inference gains less than Vast's training benchmark)."""
    raw = json.loads(run(["search", "offers", "rentable=true verified=true gpu_ram>=16", "-o", "dph_total",
                          "--limit", "3000", "--storage", str(s.disk_gb), "--raw"]))
    groups: dict[str, list[dict]] = {}
    for o in raw:
        groups.setdefault(str(o.get("gpu_name", "?")), []).append(o)
    out = []
    for label, offers in groups.items():
        key = label.replace(" ", "_")
        good = [o for o in offers if matches(o, s)]
        near = [o for o in good if in_regions(str(o.get("geolocation", "")), s)]
        good = near or good  # same fallback as search_offers: the region first, anywhere when it has none
        per_gpu = sorted(o["dph_total"] / max(1, o["num_gpus"]) for o in (good or offers))
        dlperf = sorted(o.get("dlperf", 0) / max(1, o["num_gpus"]) for o in offers)[len(offers) // 2]
        hosts: dict[int, list[float]] = {}
        for o in good:
            hosts.setdefault(int(o["num_gpus"]), []).append(o["dph_total"])
        vram = round(max(o.get("gpu_ram", 0) for o in offers) / 1024)
        cc = max(int(o.get("compute_cap") or 0) for o in offers)  # 800 = Ampere; older cards lack fast fp8/bf16 paths
        speed = speeds[key] if key in speeds else (dlperf / DLPERF_4090) ** 0.7 if dlperf else 0.0
        out.append({
            "gpu": key, "label": label, "in_region": bool(near), "vram_gb": vram, "suitable": vram >= MIN_VRAM_GB and cc >= 800,
            "offers": len(offers), "matching": len(good),
            "min_dph_per_gpu": round(per_gpu[0], 3), "median_dph_per_gpu": round(per_gpu[len(per_gpu) // 2], 3),
            "hosts": [{"gpus": n, "offers": len(p), "min_dph": round(min(p), 3)} for n, p in sorted(hosts.items())],
            "speed": round(speed, 2), "speed_measured": key in speeds,
            # what one RTX-4090-hour of clip work costs on this card: the "cheapest video" ranking
            "usd_per_4090_hour": round(per_gpu[0] / speed, 3) if speed else None,
        })
    return sorted(out, key=lambda g: (not g["suitable"], -g["matching"], -g["offers"]))


_SEARCH_CACHE: dict[tuple, tuple[float, list]] = {}
SEARCH_TTL = 60.0  # an estimate asks for 1/2/4 cards in a row; offers barely move within a minute


def search_offers(s: VastSettings, run: Runner = run_cli, limit: int = 5) -> list[Offer]:
    """Cheapest matching offers at or below max_dph."""
    key = (offer_query(s), s.disk_gb)
    hit = _SEARCH_CACHE.get(key) if run is run_cli else None
    if hit and time.monotonic() - hit[0] < SEARCH_TTL:
        raw = hit[1]
    else:
        raw = json.loads(run(["search", "offers", offer_query(s), "-o", "dph_total", "--limit", "500",
                              "--storage", str(s.disk_gb), "--raw"]))  # price incl. our disk; default limit truncates
        if run is run_cli:
            _SEARCH_CACHE[key] = (time.monotonic(), raw)
    offers = [Offer.from_raw(o) for o in raw]
    ok = [o for o in offers if o.dph <= s.max_dph * max(1, s.gpus) and o.download_cost <= s.max_download_cost
          and (not o.ram_gb or o.ram_gb >= RAM_PER_GPU_GB * max(1, o.gpus) * 0.95)]
    # a host measured below the download threshold would fail the probe again (Oregon 71063: 15 MB/s twice)
    speeds = nethistory.history().host_speed
    ok = [o for o in ok if speeds.get(o.machine_id, s.min_download_mbs) >= s.min_download_mbs]
    # preferred regions first (the model download is the slowest part of a worker's start); anywhere as a fallback
    near = [o for o in ok if in_regions(o.location, s)]
    return sorted(near or ok, key=lambda o: offer_cost(o, s))[:limit]


def offer_cost(o: Offer, s: VastSettings) -> float:
    """What picking this host costs beyond the work itself: an hour of its price (a ~1 h job), the download fee,
    the paid minutes spent waiting for the models at the speed expected from this host or its region, and a
    penalty for hosts that failed to start before."""
    hist = nethistory.history()
    wait_h = s.download_gb * 1000 / max(hist.expected_mb_s(o.machine_id, o.location), 1.0) / 3600
    return o.dph + o.setup_cost(s.download_gb) + o.dph * wait_h + nethistory.FAIL_PENALTY_USD * hist.fails(o.machine_id)


def create(offer: Offer, s: VastSettings, run: Runner = run_cli, name: str = "main", local_port: int = 0) -> State:
    if offer.dph > s.max_dph * max(1, offer.gpus):
        raise VastError(f"offer {offer.id} costs ${offer.dph:.3f}/h, above max_dph ${s.max_dph:.2f} per GPU")
    out = json.loads(run(["create", "instance", str(offer.id), "--image", s.image, "--disk", str(s.disk_gb),
                          "--ssh", "--direct", "--label", LABEL, "--raw"]))
    if not out.get("success"):
        if out.get("new_contract"):  # Vast sometimes makes the contract and still reports a failure: do not orphan it
            run(["destroy", "instance", str(out["new_contract"]), "-y"])
        raise VastError(f"create failed: {out.get('msg') or out.get('error') or 'success=false'}")
    state = State(int(out["new_contract"]), offer.dph, created_at=time.time(), name=name,
                  local_port=local_port or s.local_port, gpus=offer.gpus)
    state.save()
    return state


def wait_running(state: State, run: Runner = run_cli, timeout: float = 600, poll: float = 10) -> State:
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
    """Stop billing. Returns the approximate cost of the session in USD. An instance that is already gone (destroyed
    by another path, or by Vast) counts as destroyed: cleanup must never stop half-way and orphan the next card."""
    close_tunnel(state)
    try:
        run(["destroy", "instance", str(state.instance_id), "-y"])
    except VastError as e:
        if "not found" not in str(e).lower() and "404" not in str(e):
            raise
    hours = (time.time() - state.created_at) / 3600 if state.created_at else 0.0
    state_path(state.name).unlink(missing_ok=True)
    return hours * state.dph


PROBE_URL = ("https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/"
             "umt5_xxl_fp8_e4m3fn_scaled.safetensors")  # one of the files provisioning fetches anyway


class SlowHost(VastError):
    pass


def download_speed(state: State, s: VastSettings, mb: int = 1024, max_seconds: int = 45) -> float:
    """MB/s the worker really gets from Hugging Face (the advertised host bandwidth says little about it)."""
    # python3, not curl: the runtime image has no curl until provisioning installs it
    py = (f"import time,urllib.request as u;r=u.urlopen(u.Request({PROBE_URL!r},headers={{'Range':'bytes=0-"
          f"{mb * 1024 * 1024 - 1}'}}),timeout=30);t=time.time();n=0\n"
          f"while time.time()-t<{max_seconds}:\n b=r.read(1<<20)\n if not b:break\n n+=len(b)\n"
          f"print(n/max(time.time()-t,1e-3))")
    cmd = f"python3 -c {shlex.quote(py)}"
    r = subprocess.run([*ssh_base(state, s), cmd], capture_output=True, text=True, timeout=max_seconds + 60,
                       check=False)
    try:
        return float(r.stdout.strip().splitlines()[-1]) / 1e6
    except (ValueError, IndexError):
        return 0.0


def rent_fleet(count: int, s: VastSettings, run: Runner = run_cli, log=print, spares: int = 3,
               straggler_wait: float = 480, prefix: str = "", tunnel: bool = True) -> list[State]:
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
    if len(pick) < count:
        log(f"only {len(pick)} matching {s.gpu} offer(s) for {count} machines: running on {len(pick)}")
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
        name, port = f"{prefix}w{slot + 1}", s.local_port + 1 + slot  # prefix: concurrent jobs never share names
        while offer is not None:
            try:
                started = time.monotonic()
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
                    nethistory.record(offer, speed, ssh_s=round(time.monotonic() - started))
                    if speed < s.min_download_mbs:
                        host_fault = True
                        raise SlowHost(f"{speed:.0f} MB/s < {s.min_download_mbs:.0f} MB/s")
                dropped()
                provision(st, s)
                if s.models and tunnel:  # remote jobs talk to ComfyUI on the worker itself, no tunnel needed
                    st = open_tunnel(st, s)
                with lock:
                    if give_up.is_set():
                        raise VastError("too late, the job started without it")
                    ok.append(st)
                log(f"{name}: ready (ssh root@{st.ssh_host} -p {st.ssh_port})")
                return
            except Exception as e:  # noqa: BLE001 - a broken or slow worker is destroyed; the slot may retry
                if host_fault and not isinstance(e, SlowHost):  # never started / no SSH: remember the host
                    nethistory.record(offer, error=str(e))
                try:
                    cost = destroy(st, run=run)
                except Exception as gone:  # noqa: BLE001 - the job's final cleanup retries every saved state
                    log(f"{name}: could not free {st.instance_id}: {gone}")
                    cost = 0.0
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
