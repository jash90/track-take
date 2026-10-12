#!/usr/bin/env bash
# Runs ON a Vast worker (piped over ssh by sunomv.remote): what the engine scripts need besides ComfyUI.
# Usage: bash -s -- <remote_root> [analysis]
set -euo pipefail
ROOT=$1; WITH_ANALYSIS=${2:-}
mkdir -p "$ROOT/logs"

# same interpreter as ComfyUI when it has a venv, else the system one (PEP 668 images need the override)
if /workspace/venv/bin/python -m pip --version >/dev/null 2>&1; then PY=/workspace/venv/bin/python; else PY=python3; export PIP_BREAK_SYSTEM_PACKAGES=1; fi
printf '#!/usr/bin/env bash\n%sexec %s "$@"\n' \
  "$([ "$PY" = python3 ] && echo 'export PIP_BREAK_SYSTEM_PACKAGES=1; ')" "$PY" > "$ROOT/py"
chmod +x "$ROOT/py"

need=""
command -v ffmpeg >/dev/null || need="$need ffmpeg"
command -v rsync >/dev/null || need="$need rsync"
[ -f /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf ] || need="$need fonts-dejavu-core"
if [ -n "$need" ]; then
  apt-get update -qq >/dev/null
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $need >/dev/null
fi

"$PY" -m pip install --quiet --disable-pip-version-check pydantic httpx websockets opencv-python-headless pillow numpy
if [ "$WITH_ANALYSIS" = analysis ]; then
  "$PY" -m pip install --quiet --disable-pip-version-check librosa soundfile scipy demucs stable-ts openai-whisper \
    "beat-this @ git+https://github.com/CPJKU/beat_this.git"
fi

nvenc=$(ffmpeg -hide_banner -encoders 2>/dev/null | grep -c nvenc || true)
echo "RUNTIME_OK python=$("$PY" -V 2>&1 | cut -d' ' -f2) nvenc_encoders=$nvenc"
