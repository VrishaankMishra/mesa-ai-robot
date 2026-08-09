# Models

Weights are **not committed** (gitignored; large and regenerable). This documents the
actual model inventory as of 2026-08-09 and how to reproduce it.

## Current inventory (on iMac `models/` and Pi `~/mesa-ai-robot/models/`)

| File | Arm | Training data | Held-out test mAP@50 | Status |
|------|-----|---------------|----------------------|--------|
| `best.pt` | **v2 — deployed champion** | v1 evening round + v2 daylight round (Roboflow v2) | **0.953** | powers `main.py --live` |
| `best_v1_backup.pt` | v1 | evening round only | 0.95 (val) | study baseline arm |
| `best_v3syn.pt` | v3syn | v2 + synthetic white-balance ×3 | 0.979 (val) | **negative-result arm** — do NOT deploy (loses every off-domain condition; see `docs/eval/`) |
| `vosk-model-small-en-us/` | — | — | — | offline STT (see below) |

**Deployment rule:** validation mAP cannot pick between these arms (0.95–0.98 for all
three) — deployed-condition results in `docs/eval/domain_shift_results.csv` can, and
they say v2. **Verify model files by hash, not filename or recency** — a stale download
nearly shipped as v3 once:

```bash
md5 models/best.pt   # compare against the training run you think it is
```

## Reproducing a model

`notebooks/train_yolov8.ipynb` on Colab (T4). The hard-won Colab rules, in order:
run the pip cell → **Runtime → Restart session** (numpy ABI) → Roboflow cell (your
snippet, correct `version(N)`) → optional in-notebook cells (drop-tray, synthetic
lighting) → training cell → **download `best.pt` immediately** (Colab recycles idle
VMs and takes the weights with it). Never "Run all" after a restart.

## Getting the Vosk model
```bash
cd models
curl -LO https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
mv vosk-model-small-en-us-0.15 vosk-model-small-en-us
```
Paths are configurable in `config.yaml` (`detection.model_path`, `voice.vosk_model_path`).
If STT accuracy is poor, swap to whisper-tiny behind the same `SpeechRecognizer` interface.
