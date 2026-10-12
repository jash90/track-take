"""Shared CLI filters for the full-video scripts, so one Vast worker can take a slice of the job."""

from __future__ import annotations

ORIENTATIONS = ("landscape", "portrait")


def split_args(argv: list[str]) -> tuple[list[str], dict[str, str]]:
    """Positional args plus `--name value` options (only the flags the scripts know)."""
    pos, opts, i = [], {}, 0
    while i < len(argv):
        if argv[i].startswith("--") and i + 1 < len(argv):
            opts[argv[i][2:]] = argv[i + 1]
            i += 2
        else:
            pos.append(argv[i])
            i += 1
    return pos, opts


def wanted(opts: dict[str, str]) -> tuple[set[str] | None, tuple[str, ...]]:
    """(shot ids or None for all, orientations) from --shots s01,s02 and --orient landscape|portrait."""
    shots = set(opts["shots"].split(",")) if opts.get("shots") else None
    orients = (opts["orient"],) if opts.get("orient") else ORIENTATIONS
    for o in orients:
        if o not in ORIENTATIONS:
            raise ValueError(f"--orient must be one of {ORIENTATIONS}")
    return shots, orients
