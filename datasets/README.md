# Datasets

Image data is **not committed** (large, regenerable, and privacy-sensitive — frames show
home context). This README documents what exists and where it lives.

## Training data (exists — captured Jul 18 + Aug 7, 2026)

| Round | Condition | Images | Where |
|---|---|---|---|
| v1 | evening (bright/dim/mixed), old camera geometry | 924 | Pi `datasets/raw_v1_uploaded/`, Roboflow |
| v2 daylight | daylight, deployed (taped) geometry | 308 | iMac `datasets/raw_v2_daylight/`, Pi, Roboflow |
| discarded | two flawed passes (parked-bottle contamination) | 616 | Pi `raw_v1_discarded/`, `raw_v2_dim_corner/` |

- **Roboflow:** workspace `vrishaank-mishra`, project `medication-safety-object-detecti`
  (v1 = first round; v2 = both rounds; 2,218+ images after ×3 augmentation).
- All labels hand-drawn (Label Assist rejected — it mislabels in the model's own blind
  spots). **Annotations are ground truth; filenames are not** (capture-swap artifacts).
- Capture tooling: `scripts/capture.py` (laptop, GUI) and `scripts/capture_guided.py`
  (Pi, voice-guided, hands-free). Protocol: `docs/capture-protocol.md`.

## Classes (keep ids in sync with training `data.yaml`)

| id | label | | id | label |
|----|-------|-|----|-------|
| 0 | advil | | 5 | mylanta (carton) |
| 1 | ashwagandha | | 6 | omeprazole |
| 2 | bayer_aspirin | | 7 | tray |
| 3 | cvs_allergy | | 8 | vitamin_d3 |

(Roboflow export order — alphabetical. The Benadryl carton is deliberately untrained:
it's the wrong-medication demo probe. `tray` removal is planned future work — see the
drop-tray cell in `notebooks/train_yolov8.ipynb`.)

## Evaluation data (exists — domain-shift study, Aug 8–9, 2026)

`eval_data/<condition>/<session>/` (gitignored): 8 conditions × 216 captured frames =
1,728 captured + manifests, produced by `scripts/eval_capture.py` (scripted placement =
ground truth by construction; zero manual labels). Lives on the Pi and iMac. The first
frame of each cell is dropped uniformly (it catches the previous container mid-swap),
so **1,584 frames per arm are scored** — that is the number to quote, not 1,728. Scored
results are committed: `docs/eval/domain_shift_results.csv` (4,752 rows = 1,584 × 3 arms).

## YOLO export structure (what training consumes)

```
datasets/
├── data.yaml            # names/paths — see data.yaml.template
├── train/{images,labels}
├── valid/{images,labels}
└── test/{images,labels}
```
