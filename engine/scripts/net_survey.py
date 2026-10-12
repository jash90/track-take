"""Network survey: on one cheap host of every suitable GPU model, time the start and a 1 GB Hugging Face download.

The advertised `inet_down` of a Vast offer says little about the real model download, so this measures it. Every
host is rented in parallel and destroyed right after its probe (Vast bills only the running minutes). Results are
appended to data/net_survey.jsonl (one line per host) and printed as a table.

Usage: uv run python scripts/net_survey.py [--max-dph 8] [--gpus RTX_4090,RTX_5090] [--region any]
         [--offers 123,456] [--repeat 2] [--streams 4]
--offers probes exactly these offers; --repeat measures the single-connection download several times on the same
host (is the speed a property of the host or luck?); --streams adds a parallel download like the real model fetch.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import threading
import time
from datetime import UTC, datetime

from tracktake import cli, vast
from tracktake.config import REPO_ROOT
from tracktake.vast import PROBE_URL

OUT = REPO_ROOT / "data" / "net_survey.jsonl"
RUN = f"net{int(time.time()) % 100_000}"


def parallel_speed(st: vast.State, s, streams: int, mb_each: int = 512, max_seconds: int = 60) -> float:
    """MB/s of `streams` simultaneous ranged downloads (different byte ranges of the probe file), like the 4-way
    model fetch of provisioning."""
    py = ("import time,threading,urllib.request as u\n"
          f"N={streams};S={mb_each}*1024*1024;T={max_seconds};tot=[0]*N\n"
          "def get(i):\n"
          f" r=u.urlopen(u.Request({PROBE_URL!r},headers={{'Range':f'bytes={{i*S}}-{{(i+1)*S-1}}'}}),timeout=30)\n"
          " t=time.time()\n"
          " while time.time()-t0<T:\n"
          "  b=r.read(1<<20)\n"
          "  if not b:break\n"
          "  tot[i]+=len(b)\n"
          "t0=time.time();th=[threading.Thread(target=get,args=(i,)) for i in range(N)]\n"
          "[x.start() for x in th];[x.join() for x in th]\n"
          "print(sum(tot)/max(time.time()-t0,1e-3))")
    r = subprocess.run([*vast.ssh_base(st, s), f"python3 -c {shlex.quote(py)}"], capture_output=True, text=True,
                       timeout=max_seconds + 90, check=False)
    try:
        return round(float(r.stdout.strip().splitlines()[-1]) / 1e6, 1)
    except (ValueError, IndexError):
        return 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-dph", type=float, default=8.0, help="skip hosts above this USD/h")
    ap.add_argument("--gpus", help="only these GPU models (comma list, e.g. RTX_4090,RTX_5090)")
    ap.add_argument("--region", default="any")
    ap.add_argument("--offers", help="probe exactly these offer ids")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--streams", type=int, default=0, help="also measure N parallel connections (0 = skip)")
    args = ap.parse_args()
    s = cli._vast_settings(argparse.Namespace(region=args.region, max_dph=args.max_dph))
    s.models = ["wan22_i2v"]
    wanted = set(args.gpus.split(",")) if args.gpus else None
    picks = []
    if args.offers:
        ids = {int(x) for x in args.offers.split(",")}
        raw = json.loads(vast.run_cli(["search", "offers", "rentable=true gpu_ram>=16", "--limit", "5000",
                                       "--storage", str(s.disk_gb), "--raw"]))
        picks = [vast.Offer.from_raw(o) for o in raw if o["id"] in ids]
    for g in ([] if args.offers else cli.gpu_catalog(s)):
        if not (g["suitable"] and g["matching"]) or (wanted and g["gpu"] not in wanted):
            continue
        s1 = s.model_copy(update={"gpu": g["gpu"], "gpus": min(h["gpus"] for h in g["hosts"])})
        offers = vast.search_offers(s1, limit=1)
        if offers and offers[0].dph <= args.max_dph:
            picks.append(offers[0])
    print(f"{len(picks)} hosts to probe, ~${sum(o.dph for o in picks) * 3 / 60:.2f} for ~3 billed minutes each",
          flush=True)
    rows: list[dict] = []
    lock = threading.Lock()

    def probe(i: int, offer: vast.Offer) -> None:
        row = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "gpu": offer.gpu, "offer": offer.id,
               "machine_id": offer.machine_id, "host_id": offer.host_id,
               "location": offer.location, "country": offer.country, "dph": round(offer.dph, 3),
               "advertised_mbit": round(offer.inet_down), "advertised_mb_s": round(offer.inet_down / 8)}
        t0 = time.monotonic()
        st = None
        try:
            st = vast.create(offer, s.model_copy(update={"max_dph": args.max_dph, "gpus": offer.gpus}),
                             name=f"{RUN}-{i}", local_port=9000 + i)  # own names: surveys may overlap
            st = vast.wait_running(st)
            row["boot_s"] = round(time.monotonic() - t0)
            vast.wait_ssh(st, s)
            row["ssh_s"] = round(time.monotonic() - t0)
            runs = [round(vast.download_speed(st, s, mb=1024, max_seconds=60), 1) for _ in range(args.repeat)]
            row["measured_mb_s"] = max(runs)
            if args.repeat > 1:
                row["runs_mb_s"] = runs
            if args.streams:
                row[f"parallel{args.streams}_mb_s"] = parallel_speed(st, s, args.streams)
            row["ratio"] = round(row["measured_mb_s"] / max(row["advertised_mb_s"], 1), 2)
        except Exception as e:  # noqa: BLE001 - a host that never starts is a result too
            row["error"] = str(e)[:160]
        finally:
            if st:
                row["usd"] = round(vast.destroy(st), 3)
        with lock:
            rows.append(row)
            OUT.parent.mkdir(parents=True, exist_ok=True)
            with OUT.open("a") as f:
                f.write(json.dumps(row) + "\n")
            print(json.dumps(row), flush=True)

    threads = [threading.Thread(target=probe, args=(i, o)) for i, o in enumerate(picks)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"\n{'GPU':20} {'location':26} {'API MB/s':>8} {'measured':>9} {'ratio':>6} {'start s':>7}")
    for r in sorted(rows, key=lambda r: -r.get("measured_mb_s", -1)):
        print(f"{r['gpu']:20} {r['location'][:26]:26} {r['advertised_mb_s']:>8} "
              f"{r.get('measured_mb_s', '-'):>9} {r.get('ratio', '-'):>6} {r.get('ssh_s', r.get('error', '-'))!s:>7}")


if __name__ == "__main__":
    main()
