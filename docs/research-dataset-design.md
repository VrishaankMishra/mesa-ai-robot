# MeSA 2.0 — Research Dataset Design & Schema

Companion to: `MeSA-2_0-Research-Extension-Plan.pdf` (the locked research strategy) and the
10-week build plan. This document turns the strategy into a concrete dataset definition and
the SQLite + on-disk schema that the capture instrument (DATA-001 / RES-001) will write.

It is also the seed of the **"datasheet for datasets"** required by DATA-004 — keep it in
sync as the schema lands.

> **Status:** Design v1 (schema proposed, not yet implemented).
> **Privacy invariant (Decision R1):** features only — pose/landmark/detection vectors, never
> raw video — so the dataset can be opened and real-person collection stays consent-feasible.

---

## 1. What the lit review dictates

Each referenced paper constrains the schema. Verified during the June 2026 lit review.

| Source | Constraint on our dataset |
|---|---|
| **Koppula & Saxena** (CAD-120) — the paper to position against | A credible anticipation dataset stores **tracked object bounding boxes + human skeletons + temporal segments**, each segment carrying a label. They report top-3 anticipation **75.4 / 69.2 / 58.1 %** at **1 / 3 / 10 s** — the numbers our lead-time curve is compared to. |
| **Hu, Bestick, Englebienne, Bajcsy, Kröse** — closest to Task B | Reach-intent is predicted from skeletal pose via **object-reachability** and **motion-cost** features (skeleton → each object). ⟹ we must be able to compute **per-object distance from the wrist/hand**. |
| **ST-GCN** (Yan, Xiong, Lin, AAAI 2018) — primary model | Input is a 5-D tensor **`(N, C, T, V, M)`**: `C = 3` channels = **(x, y, confidence)**, `T` frames, `V` joints, `M = 1` person. ⟹ every stored frame needs **all joints + a confidence/visibility value**, fixed joint order, fixed `T`. |
| **MediaPipe Pose / Hands** — our feature extractor | Pose = **33 landmarks** `(x, y, z, visibility)`; Hands = **21 landmarks/hand**. MediaPipe's `visibility` *is* ST-GCN's confidence channel — free. |
| **Belardinelli** gaze review; **History-Repeats-Itself** | Framing only. Head/gaze vector (derived from pose) is a known strong early cue; motion-attention is the heavier optional baseline. Neither changes the schema. |

**Positioning (anti-over-claim):** our distinctive contribution is *auto-labeled,
privacy-clean, cheap-hardware, real-setting* human ADL data — **not** beating CAD-120 on
accuracy. Single webcam + MediaPipe (2.5-D) will not match Kinect motion-capture.

---

## 2. What the code already gives us (and the one gap)

| Needed | Already in repo | Gap |
|---|---|---|
| `taken` label source | `ComplianceTracker.observe()` logs `taken` (`mesa/engine/compliance.py`) | none — this is the RES-001 anchor |
| Bottle bbox + class | `Detection{label, confidence, box=(x1,y1,x2,y2)}` (`mesa/vision/detector.py`) | bbox exists but is **not on the event bus** |
| Full pose | `scripts/pose_live.py` extracts MediaPipe landmarks | keeps only a **named 2-D subset**; drops `z` + `visibility`. Research needs **all 33 × (x,y,z,visibility)** |
| Storage | `events / medications / schedule` tables (`mesa/data/database.py`) | no `sessions` / `clips` tables, no clip files |

**Implication:** the capture instrument cannot reuse the posture `Landmarks` dict — it must
tap the **raw 33-landmark MediaPipe output** before posture classification discards `z` and
`visibility`, and it must put bbox/positions on the bus (or read them from a shared frame
context). This is the core plumbing of DATA-001.

---

## 3. Dataset structure — three nested levels

The **unit of release is the labeled pre-event clip**. Storage is split:

- **SQLite = catalog + labels** (small, queryable): `sessions`, `clips`. Purely additive to
  the existing DB — existing tables and tests are untouched.
- **On disk = the heavy feature arrays**, one compressed `.npz` per clip, referenced by path.
  Row-per-frame blobs in SQLite would bloat and slow the DB; arrays belong in files.

```
events.db                      sessions ─1:N─ clips ──path──▶ data/clips/<session_id>/<clip_id>.npz
                                                  │
                                  anchor_event_id └─▶ events(id)   (positives only)
```

### 3.1 Per-frame feature record (the atom, lives inside the clip file)

| Field | Shape / type | Notes |
|---|---|---|
| `pose` | `float32 (T, 33, 4)` | x, y, z, **visibility**. Normalized MediaPipe image space (publishable). |
| `hands` | `float32 (T, 2, 21, 3)` *(optional, RES-002)* | x, y, z per hand; `NaN` when a hand is absent. Gated by config. |
| `objects` | `float32 (T, K, 6)` | per bottle slot: `class_id, confidence, x1, y1, x2, y2`. Padded to `K` (max bottles); empty slots = `NaN`, unknown class = `-1`. |
| `frame_ts` | `float64 (T,)` | epoch seconds. |
| `t_rel` | `float32 (T,)` | seconds relative to the clip anchor (`0` at the event; negative before). |

**Derived features are *not* stored.** Reachability (wrist→object distance), head/torso
orientation, velocities — all computed at train time by a **versioned `featurize()`** from
`pose + objects`. Rationale: keeps the released dataset minimal and authentic (R1), and lets
derived features evolve without re-collecting data. The Hu-style object-reachability feature
is the first such derived feature.

### 3.2 Per-clip (`clips` table + one `.npz`)

One training example: a buffered window ending at an anchor, plus its labels and review state.

### 3.3 Per-session (`sessions` table)

One collection sitting. Carries the consent + tier metadata that makes a clip publishable.
**No clip exists without a session, and no session without a consent record** (DATA-002).

---

## 4. SQLite schema (additive migration)

Appended to `SCHEMA` in `mesa/data/database.py`. All `CREATE TABLE IF NOT EXISTS`, so
existing `events.db` files upgrade transparently with no destructive migration.

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,          -- uuid4 hex
    participant     TEXT,                       -- pseudonymous id, never a real name
    tier            INTEGER NOT NULL,           -- 1 self / 2 consented participants / 3 deployed home
    consent_flag    INTEGER NOT NULL DEFAULT 0, -- 0 until consent recorded; Tier>=2 requires 1
    consent_version TEXT,                        -- which consent form/version was signed
    conditions      TEXT,                        -- JSON: lighting, distance_m, n_bottles, notes
    fps             REAL,                        -- nominal capture fps for this session
    started_at      REAL NOT NULL,               -- epoch seconds
    ended_at        REAL
);

CREATE TABLE IF NOT EXISTS clips (
    id              TEXT PRIMARY KEY,            -- uuid4 hex
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    path            TEXT NOT NULL,               -- relative path to the .npz feature file
    anchor_ts       REAL,                        -- epoch of the taken/contact event (NULL = negative)
    anchor_event_id INTEGER REFERENCES events(id),  -- link to the taken row (positives only)
    window_seconds  REAL NOT NULL,               -- buffered window length actually stored
    n_frames        INTEGER NOT NULL,
    label_a         TEXT NOT NULL,               -- 'interact' | 'no_interaction'
    label_b         TEXT,                        -- med_name; NULL for negatives / unknown bottle
    label_source    TEXT NOT NULL DEFAULT 'auto',-- 'auto' | 'manual'
    review_status   TEXT NOT NULL DEFAULT 'auto',-- 'auto' | 'confirmed' | 'relabeled' | 'discarded'
    split           TEXT,                         -- 'train' | 'val' | 'test' (set at packaging, DATA-004)
    created_at      REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clips_session ON clips(session_id);
CREATE INDEX IF NOT EXISTS idx_clips_label   ON clips(label_a, review_status);
```

New DAO methods (mirroring the existing `log_event` style): `create_session(...)`,
`end_session(...)`, `add_clip(...)`, `update_clip_review(...)`, `get_clips(session_id=, label_a=, review_status=, split=)`.

---

## 5. On-disk clip file

- **Location:** `research.clips_dir` (default `data/clips/`), **git-ignored**; never committed
  raw, only the packaged release (DATA-004) is shared.
- **Path:** `data/clips/<session_id>/<clip_id>.npz` — `numpy.savez_compressed`.
- **Keys:** `pose`, `hands` (optional), `objects`, `frame_ts`, `t_rel`, plus a `meta` JSON
  string mirroring the `clips` row so each file is self-describing when packaged.
- **Coordinates:** normalized MediaPipe space (resolution/camera-agnostic, publishable).
- **Raw frames:** never persisted by default. A `research.persist_video` flag (default
  `false`) may save raw clips *separately* for debugging consented Tier-1 only; these are
  **never** part of a release.

### ST-GCN adapter (documented, for RES-003)

`clip_to_stgcn(npz) -> ndarray (C=3, T, V=33, M=1)`:

1. take `pose[:, :, [0, 1, 3]]` → channels (x, y, visibility);
2. transpose to `(3, T, 33)`, add the `M=1` axis;
3. pad/truncate `T` to a fixed length defined in the dataset spec;
4. joint order = MediaPipe's canonical 33-index order (table in the datasheet);
5. graph adjacency = MediaPipe `POSE_CONNECTIONS` remapped to the 33-joint index.

---

## 6. Labeling — fully automatic (the whole point)

- **Positive clip** ← every `taken` event (`compliance.observe`) is an anchor. RES-001's ring
  buffer dumps the pre-event window as one clip; `label_a = interact`, `label_b =` the bottle
  that went absent, `anchor_event_id` → the `events` row.
- **Negative clip** ← a window where the person is present but **no `taken` occurs within a
  guard band**; `label_a = no_interaction`, `label_b = NULL`.

**Pinned decision — clean-negative rule:** a window qualifies as a negative only if no `taken`
event falls within `±guard` seconds of it, with `guard = 2 × N`. Sample at most `R` negatives
per session (default `R` ≈ positives/session) to keep Task A roughly balanced. *(Tunable;
revisit after first Tier-1 data.)*

---

## 7. Decisions pinned here (resolving Extension-Plan §10)

| Decision | Value (v1) | Why |
|---|---|---|
| **Store features, not derived** | raw `pose/hands/objects` only; derive at train time | minimal authentic release; derived features can change without recapture |
| **`N` (window length)** | **buffer 6 s, sweep 1–5 s offline** | store more than the max sweep so `N` is chosen *offline* without re-collecting (lead-time curve needs multiple `N`). Lock the headline `N` after first Tier-1 data. |
| **Clean-negative rule** | no event within `±2N`; ≤ `R` per session | balanced, leakage-free Task-A negatives |
| **Object slots `K`** | config `research.max_bottles` (default 5) | fixed-shape `objects` array; matches the 5+ bottle MED demo |
| **Split** | assigned at packaging (DATA-004), **by session** | prevents same-session leakage across train/val/test |
| **Storage split** | SQLite catalog + `.npz` arrays | DB stays small/queryable; arrays stay ST-GCN-shaped |

Still open (need data first): **Task A vs B as the headline** (both ship); confirm Hu et al.
exact citation + BlazePose citation before write-up; ethics route by ~Week 4.

---

## 8. Config additions (`config.yaml`)

```yaml
research:
  enabled: false              # master switch; off => zero overhead on the build/demos
  clips_dir: data/clips
  buffer_seconds: 6           # ring-buffer length (RES-001); >= max sweep window
  max_bottles: 5              # K, object-array slots
  capture_hands: false        # RES-002 toggle; records FPS impact when on
  persist_video: false        # debug only, consented Tier-1; never released
  negative_guard_factor: 2    # guard band = factor x N for clean negatives
```

`enabled: false` by default so the research layer is **opt-in** and can never jeopardize the
five core demos or the fall-detection FPS budget (Extension-Plan §6, Week 5 gate).

---

## 9. Ticket mapping

| Ticket | This doc covers |
|---|---|
| **DATA-001** feature logging | §3.1 frame record, §2 the raw-landmark plumbing gap |
| **RES-001** pre-event buffer | §6 anchor on `taken`, §7 buffer-6s decision |
| **DATA-002** consent/session schema | §4 `sessions` table |
| **DATA-003** label-review view | §4 `clips.review_status` lifecycle (auto→confirmed/relabeled/discarded) |
| **RES-002** hands (optional) | §3.1 `hands` array, §8 `capture_hands` toggle |
| **RES-003** baselines | §5 ST-GCN adapter; rule-based floor = wrist→nearest-bottle (Hu-style derived feature) |
| **RES-004** eval + lead-time | §1 the 1/3/10 s comparison; sweep `N` offline (§7) |
| **DATA-004** packaging + datasheet | this doc is the datasheet seed; §7 split-by-session |

---

## 10. Implementation order (next steps)

1. **Schema migration** — add §4 tables + DAO methods to `mesa/data/database.py`; unit-test
   the new methods with `:memory:`. *(Additive; existing tests stay green.)*
2. **Feature record + clip I/O** — `mesa/research/` module: frame-record dataclass, ring
   buffer, `.npz` writer, ST-GCN adapter. Pure/testable, no camera.
3. **Plumb raw features** — tap full 33-landmark pose + bbox into the capture path behind
   `research.enabled` (DATA-001 core).
4. **Wire the anchor** — on `compliance.observe` → `taken`, dump the buffer as a labeled clip
   (RES-001).
5. **Review view** — Streamlit page on the existing dashboard (DATA-003).

Steps 1–2 are pure data-layer work with no hardware/camera dependency — the right place to
start.
