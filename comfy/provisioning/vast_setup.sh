#!/usr/bin/env bash
# Runs ON the Vast.ai instance (piped over ssh by `tracktake vast up`).
# Installs ComfyUI pinned to the local commit, downloads the model sets, starts ComfyUI on 127.0.0.1:PORT.
# Usage: bash -s -- <comfy_repo> <commit> <port> <model_set>...
set -euo pipefail
REPO=$1; COMMIT=$2; PORT=$3; shift 3
if [ "$#" -eq 0 ]; then  # e.g. an analysis-only worker: no ComfyUI, no model downloads
  echo "no model sets requested; skipping ComfyUI"
  exit 0
fi
ROOT=/workspace/ComfyUI
HF=https://huggingface.co

models_for() {  # <set> -> lines "<models subdir> <url>"
  case $1 in
    wan22_i2v)
      local W=$HF/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files
      echo "text_encoders $HF/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"
      echo "diffusion_models $W/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"
      echo "diffusion_models $W/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors"
      echo "loras $W/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"
      echo "loras $W/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors"
      echo "vae $W/vae/wan_2.1_vae.safetensors" ;;
    zimage)
      local Z=$HF/Comfy-Org/z_image_turbo/resolve/main/split_files
      echo "diffusion_models $Z/diffusion_models/z_image_turbo_bf16.safetensors"
      echo "text_encoders $Z/text_encoders/qwen_3_4b.safetensors"
      echo "vae $Z/vae/ae.safetensors" ;;
    *) echo "unknown model set: $1" >&2; exit 2 ;;
  esac
}

fetch() {  # <subdir> <url>: resumable, skipped when already present
  local f="$ROOT/models/$1/$(basename "$2")"
  mkdir -p "$(dirname "$f")"
  [ -s "$f" ] && { echo "have $(basename "$f")"; return 0; }
  # HTTP/1.1 + retry on every error: an HTTP/2 stream reset (curl 92) mid-file is not "transient" for plain --retry
  curl -fsSL --http1.1 --retry 8 --retry-all-errors --retry-delay 3 -C - -o "$f.part" "$2" \
    && mv "$f.part" "$f" && echo "got $(basename "$f")"
}
export -f fetch
export ROOT

echo "== ComfyUI $COMMIT"
mkdir -p /workspace
[ -d "$ROOT/.git" ] || git clone --quiet "$REPO" "$ROOT"
cd "$ROOT"
git fetch --quiet origin
git checkout --quiet "$COMMIT"
# own venv: recent pytorch images use a PEP 668 "externally managed" system Python; the venv still sees its CUDA torch
PY=/workspace/venv/bin/python
if [ -x "$PY" ] && ! "$PY" -m pip --version >/dev/null 2>&1; then rm -rf /workspace/venv; fi  # half-made venv
if [ ! -x "$PY" ] && ! python3 -m venv --system-site-packages /workspace/venv; then
  echo "no venv module; installing into the system Python"
  rm -rf /workspace/venv  # ensurepip missing leaves a venv without pip behind
  PY=python3
  export PIP_BREAK_SYSTEM_PACKAGES=1
fi
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet -r requirements.txt
"$PY" -c "import torch; assert torch.cuda.is_available(), 'no CUDA'; print('torch', torch.__version__, torch.cuda.get_device_name(0))"

echo "== models: $*"
for set in "$@"; do models_for "$set"; done | xargs -P 4 -L 1 bash -c 'fetch "$0" "$1"'

echo "== start on 127.0.0.1:$PORT"
if ! curl -sf "http://127.0.0.1:$PORT/system_stats" >/dev/null; then
  setsid nohup "$PY" main.py --listen 127.0.0.1 --port "$PORT" --disable-auto-launch > /workspace/comfyui.log 2>&1 < /dev/null &
fi
for _ in $(seq 1 120); do
  curl -sf "http://127.0.0.1:$PORT/system_stats" >/dev/null && { echo "READY"; exit 0; }
  sleep 5
done
tail -50 /workspace/comfyui.log
echo "ComfyUI did not start" >&2
exit 1
