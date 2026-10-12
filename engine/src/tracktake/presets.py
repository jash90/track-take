"""Three ready-made render choices ("cheapest", "recommended", "fastest") instead of GPU / machines / price fields.

Computed from the live GPU catalog (vast.gpu_catalog) with the same cost model as cli._estimate, so they need no
extra searches. Only cards with a measured speed are used while any of them is on offer (estimated speeds from Vast's
DLPerf are a fallback, discounted); the "fastest" choice may cost at most ~3x the cheapest, so it never jumps to a
$30/h machine.
"""

from __future__ import annotations

TIME_VALUE_USD_PER_H = 1.0  # "recommended": every hour saved is worth about a dollar
UNMEASURED_SPEED = 0.85  # trust an estimated speed a bit less than a measured one
MULTI_GPU_VERIFIED = True  # one ComfyUI per GPU on one host (provisioning starts one per GPU)
DOWNLOAD_USD = 0.12  # models per machine on hosts that pass the download-price filter (<= $0.006/GB, ~41 GB)


def options(catalog: list[dict], clips: int, clip_s: float, setup_h: float, render_h: float) -> list[dict]:
    """Every (card, GPUs per machine, machines) choice. Only measured cards when any of them has offers: a preset
    is a promise, and estimated cards (and hosts) have surprised us - they stay available in the advanced picker."""
    measured = [g for g in catalog if g["speed_measured"] and g["suitable"] and g["matching"]]
    out = []
    for g in measured or catalog:
        if not (g["suitable"] and g["matching"] and g["speed"]):
            continue
        speed = g["speed"] * (1.0 if g["speed_measured"] else UNMEASURED_SPEED)
        sizes = {h["gpus"] for h in g["hosts"] if h["gpus"] in ((1, 2, 4, 8) if MULTI_GPU_VERIFIED else (1,))}
        for host in g["hosts"]:
            n, dph = host["gpus"], host["min_dph"]
            if n not in sizes:
                continue
            work_h = clips * clip_s / speed / 3600 / n  # host-hours of clip generation
            # several GPUs in ONE machine first: one start, one model download, no copying clips between machines.
            # Separate single-GPU machines only for GPU counts no single machine of this card offers.
            for machines in (1, 2, 4):
                if machines > host["offers"] or (machines > 1 and (n > 1 or n * machines in sizes)):
                    continue
                hours = setup_h + work_h / machines + render_h
                usd = machines * (setup_h * dph + DOWNLOAD_USD) + work_h * dph + render_h * dph
                out.append({"gpu": g["gpu"], "label": g["label"], "gpus": n, "workers": machines,
                            "minutes": round(hours * 60), "usd": round(usd, 2), "speed": g["speed"],
                            "speed_measured": g["speed_measured"],
                            "max_dph": round(dph / n * 1.15, 3)})  # per GPU, with room for the next offers
    return out


def pick(opts: list[dict]) -> list[dict]:
    if not opts:
        return []
    floor = min(o["usd"] for o in opts)
    # within 10 % of the lowest price, the faster option is "the cheapest" (saving cents is not worth an extra hour)
    cheapest = min((o for o in opts if o["usd"] <= floor * 1.1), key=lambda o: (o["minutes"], o["usd"]))
    cap = max(cheapest["usd"] * 3, cheapest["usd"] + 1.5)
    fastest = min((o for o in opts if o["usd"] <= cap), key=lambda o: (o["minutes"], o["usd"]))
    def value(o: dict) -> float:
        return o["usd"] + TIME_VALUE_USD_PER_H * o["minutes"] / 60

    def same(a: dict, b: dict) -> bool:
        return (a["gpu"], a["gpus"], a["workers"]) == (b["gpu"], b["gpus"], b["workers"])

    recommended = min(opts, key=value)
    if same(recommended, cheapest) or same(recommended, fastest):  # three different choices when possible
        middle = [o for o in opts if fastest["minutes"] < o["minutes"] < cheapest["minutes"] and o["usd"] <= cap]
        recommended = min(middle, key=value) if middle else recommended
    return [dict(cheapest, id="cheapest"), dict(recommended, id="recommended"), dict(fastest, id="fastest")]


def presets(catalog: list[dict], clips: int, clip_s: float, setup_h: float, render_h: float) -> list[dict]:
    return pick(options(catalog, clips, clip_s, setup_h, render_h))
