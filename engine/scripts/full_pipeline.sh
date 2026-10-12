#!/usr/bin/env bash
# Full music video: waits for the Vast fleet and the Codex keyframes, then runs every step and frees the GPUs.
# Usage (from engine/): bash scripts/full_pipeline.sh <full_dir> <analysis.json> <song> <fleet_log> <codex_log>
set -uo pipefail
FULL=$1; ANALYSIS=$2; SONG=$3; FLEET_LOG=$4; CODEX_LOG=$5
step() { echo "== $(date +%H:%M:%S) $*"; }

step "waiting for the fleet"
until grep -q "^exit" "$FLEET_LOG"; do sleep 10; done
# workers that came up keep a state file; failed ones were destroyed together with theirs
URLS=$(python3 -c "import glob, json, os; print(' '.join(sorted('http://127.0.0.1:%d' % json.load(open(p))['local_port'] for p in glob.glob(os.path.expanduser('~/.config/sunomv/vast-*.json')))))")
if [ -z "$URLS" ]; then step "fleet failed"; exit 1; fi
step "fleet ready: $URLS"

step "comfy keyframes (Z-Image)"
uv run python scripts/full_keys_comfy.py "$FULL" $URLS

step "waiting for codex keyframes"
until grep -q "^done in" "$CODEX_LOG"; do sleep 10; done

step "clips: codex set"
uv run python scripts/full_clips.py "$FULL" codex $URLS
step "render: codex (in background)"
uv run python scripts/full_render.py "$FULL" "$ANALYSIS" "$SONG" codex > "$FULL/render_codex.log" 2>&1 &
RENDER_CODEX=$!

step "clips: comfy set"
uv run python scripts/full_clips.py "$FULL" comfy $URLS

step "freeing the GPUs"
uv run sunomv vast down --all

step "render: comfy"
uv run python scripts/full_render.py "$FULL" "$ANALYSIS" "$SONG" comfy > "$FULL/render_comfy.log" 2>&1
wait $RENDER_CODEX
step "ALL DONE"
