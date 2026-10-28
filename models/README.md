# Models

Weights are **not committed** (gitignored; large and regenerable). This documents the
actual model inventory as of 2026-08-09 and how to reproduce it.

Per-arm training records, the Roboflow-version → model map, and SHA-256 checksums:
[`training-metadata/`](training-metadata/) and [`../docs/training/`](../docs/training/).

## Current inventory (on iMac `models/` and Pi `~/mesa-ai-robot/models/`)

| File | Arm | Training data | mAP@50 (split) | Status |
|------|-----|---------------|----------------|--------|
| `best.pt` | **v2 — deployed champion** | v1 evening round + v2 daylight round (Roboflow v2) | 0.95–0.98 band (validation, Colab); no held-out test run on record | powers `main.py --live` |
| `best_v1_backup.pt` | v1 | evening round only | **0.953** (held-out test, 92 images, Aug 6 — `docs/eval/eval-report-v1.md`); 0.95 (validation) | study baseline arm |
| `best_v3syn.pt` | v3syn | v2 + synthetic white-balance ×3 | 0.979 (validation) | **negative-result arm** — do NOT deploy (loses every off-domain condition; see `docs/eval/`) |

The 0.953 is the v1 round's number: `eval-report-v1.md` scored the weights that were
`best.pt` on Aug 6, before the Aug 7 daylight retrain replaced them (they are the file now
kept as `best_v1_backup.pt`). An earlier revision of this table carried 0.953 against v2;
that run does not exist. Re-scoring v2 and v3syn on the test split needs the Roboflow export
(`datasets/data.yaml`), which is not kept in the repo.
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

## Getting the Whisper model (open-vocabulary STT, VOX-008)

Vosk-small cannot emit a word outside its compiled lexicon, so medication names like
`omeprazole` are unrepresentable to it. `voice.stt_engine: whisper-tiny` switches to
faster-whisper, which has no such limit. **The model downloads on first use — do this at
home, on a network, before any demo.** The demo room may have no internet, and a first
press that hangs on a download is a failed demo.

```bash
.venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('tiny', device='cpu', compute_type='int8'); print('cached')"
```

That caches `Systran/faster-whisper-tiny` under `~/.cache/huggingface/`. To pin a copy
inside the repo instead, point `voice.whisper.model_path` at a directory containing it.
