#!/usr/bin/env bash
# MeSA 2.0 — one-command environment setup (INFRA-001).
#
# Works identically on Intel macOS, Apple Silicon macOS, and Linux. The only thing that
# differs across machines is the Python interpreter, so this script finds a compatible one
# and refuses the ones that don't work — which is the single most common setup failure.
#
#   bash scripts/setup_env.sh            # create .venv + install the laptop stack
#   bash scripts/setup_env.sh --pi       # also install requirements-pi.txt (run on the Pi)
#
# Why a version guard: the pinned vision stack (mediapipe==0.10.14) ships wheels only for
# CPython 3.11 and 3.12 — there is no 3.13 wheel. A plain `python3 -m venv` grabs whatever
# `python3` is (often 3.13), and `pip install` then fails confusingly. This script picks
# 3.12/3.11 explicitly so the same steps work on your build machine and the demo MacBook.

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # repo root

INSTALL_PI=0
[[ "${1:-}" == "--pi" ]] && INSTALL_PI=1

# --- find a compatible interpreter (3.12 preferred, then 3.11) ---
PY=""
for cand in python3.12 python3.11; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done

if [[ -z "$PY" ]]; then
  echo "✗ No compatible Python found. MeSA needs Python 3.11 or 3.12 (not 3.13 — the"
  echo "  pinned mediapipe has no 3.13 wheel)."
  echo
  if command -v python3 >/dev/null 2>&1; then
    echo "  You have: $(python3 --version) at $(command -v python3)"
  fi
  echo "  Install one:"
  echo "    macOS (Homebrew):   brew install python@3.12"
  echo "    macOS (python.org): https://www.python.org/downloads/release/python-3128/"
  echo "    Linux (deadsnakes): sudo apt install python3.12 python3.12-venv"
  exit 1
fi

echo "==> Using $($PY --version) ($(command -v $PY)) on $(uname -m)"

# --- create the venv ---
if [[ -d .venv ]]; then
  echo "==> .venv already exists; reusing it (delete it to start fresh)"
else
  "$PY" -m venv .venv
  echo "==> created .venv"
fi
VENV_PY=".venv/bin/python"

# --- install ---
echo "==> upgrading pip"
"$VENV_PY" -m pip install --quiet --upgrade pip

echo "==> installing requirements.txt (this pulls torch via ultralytics; first run is slow)"
"$VENV_PY" -m pip install -r requirements.txt

if [[ "$INSTALL_PI" == "1" ]]; then
  if command -v apt-get >/dev/null 2>&1; then
    # sounddevice needs the system PortAudio lib; pyttsx3 2.90 dlopens the LEGACY
    # libespeak.so.1 (libespeak1), not espeak-ng's lib — install both to be safe.
    # None are pip-installable, so pip alone leaves audio broken at runtime.
    echo "==> installing system audio libs (libportaudio2, espeak-ng, libespeak1)"
    sudo apt-get install -y libportaudio2 espeak-ng libespeak1
  fi
  echo "==> installing requirements-pi.txt (Pi hardware libs)"
  "$VENV_PY" -m pip install -r requirements-pi.txt
fi

echo "==> installing mesa (editable) so imports + console scripts work"
"$VENV_PY" -m pip install --quiet -e .

# --- verify ---
echo "==> verifying the stack imports"
"$VENV_PY" - <<'PY'
import cv2, mediapipe, ultralytics, vosk, pyttsx3, sounddevice, streamlit, numpy, yaml
from mesa.hardware.outputs import build_output_hub
print(f"   ok: opencv {cv2.__version__}, mediapipe {mediapipe.__version__}")
PY

cat <<'DONE'

✓ Environment ready.

Next:
  .venv/bin/python -m pytest          # all tests green
  .venv/bin/python main.py --demo     # synthetic event sequence, end-to-end

macOS notes (Intel or Apple Silicon — same steps):
  • First camera/mic use prompts for permission: System Settings → Privacy & Security.
  • If audio can't find a backend:  brew install portaudio
DONE
