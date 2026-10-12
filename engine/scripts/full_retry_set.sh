#!/usr/bin/env bash
# Re-run the clips of one keyframe set on a fresh Vast fleet; GPUs are freed only when no clip is missing
# (or after two passes). Usage (from engine/): bash scripts/full_retry_set.sh <full_dir> <analysis> <song> <set> <count>
set -uo pipefail
FULL=$1; ANALYSIS=$2; SONG=$3; SET=$4; COUNT=${5:-4}
step() { echo "== $(date +%H:%M:%S) $*"; }
missing() { python3 - "$FULL" "$SET" <<'PY'
import json, sys, pathlib
full, kind = pathlib.Path(sys.argv[1]), sys.argv[2]
sb = json.loads((full / "storyboard.json").read_text())
print(sum(1 for s in sb["shots"] for o in ("landscape", "portrait")
          if not (full / kind / "clips" / f"{s['id']}_{o}.json").exists()))
PY
}

step "fleet x$COUNT"
uv run tracktake vast fleet --count "$COUNT" --min-net 900 --max-dph 0.5 --yes
URLS=$(python3 -c "import glob, json, os; print(' '.join(sorted('http://127.0.0.1:%d' % json.load(open(p))['local_port'] for p in glob.glob(os.path.expanduser('~/.config/tracktake/vast-*.json')))))")
[ -z "$URLS" ] && { step "no workers"; exit 1; }
step "workers: $URLS"

for pass in 1 2; do
  step "clips $SET pass $pass ($(missing) missing)"
  uv run python scripts/full_clips.py "$FULL" "$SET" $URLS
  [ "$(missing)" = "0" ] && break
done

step "missing after passes: $(missing); freeing the GPUs"
uv run tracktake vast down --all

step "render $SET"
uv run python scripts/full_render.py "$FULL" "$ANALYSIS" "$SONG" "$SET" > "$FULL/render_$SET.log" 2>&1
step "DONE (render exit $?)"
