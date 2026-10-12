#!/usr/bin/env bash
# One-screen status of the full-video pipeline. Usage: bash scripts/full_status.sh <full_dir>
FULL=$1
count() { ls "$1" 2>/dev/null | grep -c "$2"; }
echo "time        $(date +%H:%M:%S)"
echo "pipeline    $(grep '^==' /tmp/sunomv/pipeline.log 2>/dev/null | tail -1)"
echo "codex keys  $(count "$FULL/codex/keys" '\.png$')/90"
echo "comfy keys  $(count "$FULL/comfy/keys" '\.png$')/90"
echo "codex clips $(count "$FULL/codex/clips" '\.json$')/90"
echo "comfy clips $(count "$FULL/comfy/clips" '\.json$')/90"
echo "fleet       $(grep -cE ' at http' /tmp/sunomv/fleet.log 2>/dev/null)/4 ready; $(grep -E 'failed|ERROR' /tmp/sunomv/fleet.log 2>/dev/null | tail -1)"
for k in codex comfy; do
  [ -f "$FULL/$k/render_report.json" ] && echo "render $k  done: $(ls "$FULL/$k"/teledysk_*preview.mp4 2>/dev/null | xargs -n1 basename | tr '\n' ' ')"
done
