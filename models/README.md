# Models (placeholder)

Trained model weights live here but are **not committed** (gitignored — they're large and
regenerable). Expected files:

| File | Produced by | Used by |
|------|-------------|---------|
| `best.pt` | `notebooks/train_yolov8.ipynb` (Colab, VIS-004) | detection (`mesa/vision/detector.py`, `scripts/detect_live.py`) |
| `vosk-model-small-en-us/` | download from https://alphacephei.com/vosk/models | STT (`mesa/audio/stt.py`, `scripts/voice_loop.py`) |

## Getting the Vosk model
```bash
cd models
curl -LO https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
mv vosk-model-small-en-us-0.15 vosk-model-small-en-us
```
Paths are configurable in `config.yaml` (`detection.model_path`, `voice.vosk_model_path`).
If accuracy is poor, swap to whisper-tiny behind the same `SpeechRecognizer` interface.
