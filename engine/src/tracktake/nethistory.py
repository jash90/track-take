"""What we know about Vast hosts' real model-download speed and start reliability, to rank offers by it.

Every 1 GB Hugging Face probe (scripts/net_survey.py, and each worker rented by vast.rent_fleet) is a line in
data/net_survey.jsonl. A host measured before is expected to repeat its speed (repeats differed by 2-30 %); a host
never measured gets the median of its region. Location predicts the speed far better than the offer's advertised
`inet_down` (Virginia ~345 MB/s, rest of the US ~116, Europe ~76, Asia/Africa/Oceania ~26 in the 2026-10-12 survey),
and a host that failed to start before is likely to fail again.
"""

from __future__ import annotations

import json
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

from tracktake.config import REPO_ROOT

HISTORY = REPO_ROOT / "data" / "net_survey.jsonl"
US_EAST = {"virginia", "north carolina", "south carolina", "new york", "new jersey", "pennsylvania", "maryland",
           "delaware", "district of columbia", "georgia", "ohio", "massachusetts", "connecticut", "rhode island",
           "new hampshire", "vermont", "maine", "west virginia"}
EUROPE = {"NL", "DE", "IE", "CZ", "GB", "FR", "SE", "NO", "FI", "DK", "BE", "PL", "ES", "IT", "PT", "AT", "CH", "HU",
          "BG", "RO", "SK", "SI", "HR", "EE", "LV", "LT", "IS", "LU", "GR"}
# fallbacks from the first survey, used until the history holds a few hosts of a region
DEFAULT_MB_S = {"us-east": 300.0, "us": 116.0, "ca": 81.0, "eu": 76.0, "other": 26.0}
DEFAULT_BOOT_S = {"us-east": 191.0, "us": 130.0, "ca": 100.0, "eu": 137.0, "other": 168.0}  # rent -> SSH
INSTALL_MIN = 2.5  # tools + ComfyUI + Python packages; the models download in parallel with it
SAMPLE = {"us-east": "Virginia, US", "us": "Texas, US", "ca": "Quebec, CA", "eu": "Germany, DE", "other": "Japan, JP"}
FAIL_PENALTY_USD = 0.5  # a host that did not start costs a spare's wait and a retry


def region(location: str) -> str:
    """'Richmond, Virginia, US' / 'Virginia, US' -> 'us-east'; 'Berlin, DE' -> 'eu'."""
    parts = [p.strip() for p in location.split(",")]
    country = parts[-1].upper() if parts else ""
    state = parts[-2].lower() if len(parts) >= 2 else ""
    if country == "US":
        return "us-east" if state in US_EAST else "us"
    if country == "CA":
        return "ca"
    return "eu" if country in EUROPE else "other"


class History:
    def __init__(self, path: Path | None = None):
        path = path or HISTORY
        self.rows: list[dict] = []
        if path.exists():
            for line in path.read_text().splitlines():
                try:
                    self.rows.append(json.loads(line))
                except ValueError:
                    continue
        by_region: dict[str, list[float]] = {}
        boots: dict[str, list[float]] = {}
        self.host_speed: dict[int, float] = {}
        self.host_fails: dict[int, int] = {}
        for r in self.rows:
            machine = r.get("machine_id")
            if r.get("ssh_s"):
                boots.setdefault(region(r.get("location", "")), []).append(r["ssh_s"])
            if r.get("measured_mb_s"):
                by_region.setdefault(region(r.get("location", "")), []).append(r["measured_mb_s"])
                if machine:
                    self.host_speed[machine] = r["measured_mb_s"]  # the latest measurement wins
            elif r.get("error") and machine:
                self.host_fails[machine] = self.host_fails.get(machine, 0) + 1
        self.region_speed = {k: statistics.median(v) for k, v in by_region.items() if len(v) >= 2}
        self.region_boot = {k: statistics.median(v) for k, v in boots.items() if len(v) >= 2}

    def expected_mb_s(self, machine_id: int, location: str) -> float:
        if machine_id in self.host_speed:
            return self.host_speed[machine_id]
        reg = region(location)
        return self.region_speed.get(reg, DEFAULT_MB_S[reg])

    def setup_minutes(self, machine_id: int, location: str, download_gb: float) -> float:
        """Rent -> worker ready: the host's start for its region, then the install and the model download, which
        run side by side (the longer one counts). Measured for a Virginia H100: 6.0 min; this gives 5.7."""
        reg = region(location)
        boot = self.region_boot.get(reg, DEFAULT_BOOT_S[reg]) / 60
        models = download_gb * 1000 / max(self.expected_mb_s(machine_id, location), 1.0) / 60
        return boot + max(INSTALL_MIN, models)

    def typical_setup_minutes(self, regions: list[str], download_gb: float) -> float:
        """For presets, before an offer is picked: the slowest region the rental may land in (US -> rest of the US,
        US,CA -> Canada, anywhere -> Europe; the ranking keeps far, slow hosts out)."""
        keys = set()
        for r in regions or []:
            r = r.upper()
            keys |= {"us", "us-east"} if r == "US" else {"ca"} if r == "CA" else {"eu" if r in EUROPE else "other"}
        return max(self.setup_minutes(0, SAMPLE[k], download_gb) for k in (keys or {"us", "eu"}))

    def fails(self, machine_id: int) -> int:
        return self.host_fails.get(machine_id, 0)


_CACHE: tuple[float, History] | None = None


def history(max_age: float = 60) -> History:
    global _CACHE
    if _CACHE is None or time.monotonic() - _CACHE[0] > max_age:
        _CACHE = (time.monotonic(), History())
    return _CACHE[1]


def record(offer, measured_mb_s: float | None = None, error: str | None = None, **extra) -> None:
    """Append one probe (or a failed start) of a rented host to the history."""
    row = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "gpu": offer.gpu, "offer": offer.id,
           "machine_id": offer.machine_id, "host_id": offer.host_id, "location": offer.location,
           "country": offer.country, "dph": round(offer.dph, 3), "advertised_mb_s": round(offer.inet_down / 8)}
    if measured_mb_s is not None:
        row["measured_mb_s"] = round(measured_mb_s, 1)
    if error:
        row["error"] = error[:160]
    row.update(extra)
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a") as f:
        f.write(json.dumps(row) + "\n")
    global _CACHE
    _CACHE = None
