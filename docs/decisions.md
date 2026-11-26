# Decisions (ADRs)

## ADR-01 — PHOTO_GRADING is a generated 3D LUT + `lut3d`

Executing the 3-way wheels via a generated `.cube` LUT and `ffmpeg lut3d` keeps the wheel
semantics in Python (deterministic, stdlib math) instead of translating them into fragile
filter chains. The LUT is data; never a filter string.

**Why**: the wheel model (zone split by BT.709 luma, hue/saturation/luminance per zone,
global wheel, blending/balance) is cleanly expressible as a pure LUT function, and `lut3d`
is the most accurate available executor. Zone semantics: shadows = luma < lo, highlights =
luma > hi, midtones between; balance moves lo/hi (positive = more midtones). Each wheel with
saturation > 0 tints its zone: rotate hue, scale saturation by saturation/100; near-black
zone pixels get v = 0.02 so the tint is visible. `blending` mixes the tinted LUT back
toward identity; the global wheel applies after the zone tints.

## ADR-02 — PHOTO_CORRECTION via `eq` + `hue` + `unsharp` + levels LUT

White balance: temperature → `hue=h=<rot>` rotation around the wheel (neutral 6500 → 0,
range ±180, clamped); tint → `hue=s=<scale>` (tint -100..100 → s = 1 - tint/100). Base:
`eq=brightness:contrast:saturation` (exposure → brightness/10, contrast → 1+c/100,
saturation → 1+s/100, clamped to the filter ranges). Tonal bands (shadows/highlights/
blacks/whites): generated LUT via `build_levels_lut`. Sharpness: `unsharp=la.size=3:amount=`.

**Why**: `eq`, `hue` and `unsharp` are the classic, stable FFmpeg photo filters; the
equations above are simple, deterministic and range-checked.

## ADR-03 — WHITE_BALANCE is an alias, not a type

`WHITE_BALANCE` resolves to `PHOTO_CORRECTION` at validation; at request level the alias is
restricted to `white_balance_temperature` + `white_balance_tint` (video-skill ADR-20 style).

## ADR-04 — Measurements are OBSERVED, never judged

Before/after stats come from `ffmpeg -vf signalstats,showinfo` (showinfo prints
`mean:[Y U V]` of the first frame); the skill records them in `measurements.before/after`
and reports what it saw. It never calls a result "good", "cinematic", or "failed" based on
them — the response says what was measured; the caller decides.

## ADR-05 — `.cube` data lines are 0-1 floats; LUT filenames are deterministic

The `.cube` spec/ffmpeg reads data values as 0-1 floats (`0.5` → 127); writing 0-255 ints
clips everything to white. LUT filenames are `sha256(content)[:16]`, so identical wheels
produce identical filenames across runs/machines.

## ADR-06 — Path policy defaults to the workspace

Without explicit `--allowed-input`/`--allowed-lut`, inputs, LUTs and outputs must resolve
inside the workspace (the video skill allows anywhere by default; photos are edited, so the
workspace default matches the product).

## ADR-07 — Reuse is by content identity

Re-running the same request reuses the intermediate when the stamp's identity matches:
`sha256({type, parameters, input_identity, tool_versions})`, no timestamps, no UUIDs
(matches the video skill's determinism rule).

## ADR-08 — The critic scores a caller-supplied target; it does not judge

`PHOTO_ANALYZE`, `PHOTO_SCORE` and `PHOTO_OPTIMIZE` measure in OKLab. A target is exactly six
numbers (`shadow_hue`, `highlight_hue`, `tint_mag`, `colorfulness`, `median_L`, `spread`), with
no look names or presets. The score is `100 + Σ penalties`; every part reports its measured
value, target and tolerance, and cast is reported but never penalized. Skin-hue shift and mean
OKLab distance are guards, not look targets.

**Why**: the caller decides the look; the skill measures distance to it. This keeps the
"never judges a photo cinematic" rule while still allowing an automated loop. The optimizer is
deterministic coordinate descent (fixed order, fixed step schedule, no RNG), accepts only
improving steps, bakes the winner into a LUT, re-scores through the LUT path and re-checks the
full render with an identity fallback. It is safe, not globally optimal; a learned aesthetic
score would reintroduce judgment and is excluded (if added, ranking candidates of the same
image only).

## ADR-09 — Analysis lives in `analysis/`; descriptors describe, they do not grade

`src/photo_grading/analysis/` owns the shared colour math (`colorspace.py`), the trilinear LUT
interpolator (`lutio.py`) and the target-free descriptors (`descriptors.py`). `critic.py`
imports and re-exports those names, so existing imports and tests keep working; there is one
implementation, not a copy in each module. `[analysis]` is the extra (numpy + Pillow), and
`[critic]` stays as a compatibility alias.

The LUT interpolator is checked against real FFmpeg `lut3d` in the test suite: mean ΔE_OK
< 0.01 and p95 < 0.02. That threshold is the contract that lets the optimizer trust a proxy
score for a full-size render.

`PHOTO_ANALYZE` adds descriptors with no fitting and no target: OKLab L percentiles
1/5/25/50/75/95/99, zone tints (zone mean (a,b) minus the whole-image mean, so a global cast is
removed but the scene's own colour is not), mean/p90 chroma, M3, 12 fixed 30° hue sectors, a
seeded five-colour palette and rough skin-band stats. The palette is k-means++ in OKLab —
clustering on a/b handles the circular hue, and centres are reported in OKLCH — with up to
20k evenly-spaced samples, 50 iterations, and output sorted by weight so cluster-label order
cannot change the report. `seed` (default 0) makes it reproducible. Descriptors run only in
`analyze_file`/`PHOTO_ANALYZE`, never per optimizer iteration.

**Why**: the reverse-engineering work needs one measured vocabulary before any fitting, and a
descriptor is an observation, not a recommendation. A palette from one photo is not a grade to
copy onto another; it is evidence a caller can use to build a target by hand.

## ADR-10 — Phase 2 fits wheels in integer space; the thresholds below are the tuned values

The Phase 2 reverse-engineering work adds two internal modules, with no new operation yet:

- `analysis/fit_params.py`: a vectorized NumPy port of the `PHOTO_GRADING` wheel transform,
  pinned to `build_wheel_lut` at 17³ (max difference 5e-7, the builder's 6-decimal rounding),
  plus a deterministic fit.
- `analysis/probe_lut.py`: Mode C. It parses a 3D `.cube` with `lutio.read_cube`, measures a
  fixed probe set, and explains the result as wheel params.

**Wheels only, for now.** `PHOTO_CORRECTION`'s `eq` stage runs in YUV inside FFmpeg, so it
cannot be reproduced faithfully in sRGB. Measured: `eq=brightness=0.1` shifts a neutral gray
ramp by 0.1137 and `eq=saturation=1.5` adds ±0.004 chroma noise. A model that claims to match
it would be wrong. Correction-stage fitting and the residual LUT are Phase 3; until then the
pair fit and Mode C explain the wheel stage and report the residual honestly.

**Integer space, not float space.** The request contract accepts integers only. A float
`shadows_saturation` of 0.02 keeps the shadow zone wheel active (`saturation != 0` in
`buildlut`), while rounding it to 0 routes shadow pixels through the midtones wheel. On a 33³
warm LUT that rounding turned a 0.005 fit into a 0.020 fit. The search therefore clamps and
rounds every candidate before evaluating it, so the reported fit is the fit of the exact
integers a caller will send. Hue 360 is normalized to 0.

**Tuned test budgets and thresholds.** Starting values from the spec were kept unless the
round-trip suite showed a reason to move them:

| Setting | Value | Why |
|---|---|---|
| Huber δ | 0.02 ΔE_OK | One JND; outliers (clipping, local edits) cannot dominate |
| L2 pull to identity | 1e-5 | Breaks ties toward the simplest wheels without changing a real fit |
| Train/hold-out | 80/20, seeded | The reported fit is held-out; no fitting on the test pixels |
| Max fit samples | 8,000 | Enough for 15 params; keeps a fit at a few seconds |
| Clipped pixels | drop `≤ 0.004` / `≥ 0.996` | A clipped pixel carries no usable colour difference |
| Coordinate descent | 45 sweeps, step ×0.9, stop < 1 unit | Integer steps; the schedule cannot oscillate |
| Coarse wheel seed | 12 hues × 5 strengths, global first | Escapes the zero-saturation hue deadlock |
| Weak effect | RMS ΔE_OK < 0.0015 for a 5%-of-range step | Flags a parameter the pair does not constrain |
| Correlation warning | \|corr\| ≥ 0.95 on active parameters | Flags parameter trade-offs, not off wheels |
| "Expressible as wheels" | held-out mean ΔE_OK ≤ 0.02 | One JND; above it the LUT needs `PHOTO_LUT_APPLY` |
| Probe set | 64 neutral, 108 patches, 4,096 seeded colors | Matches the spec; covers neutrals, hue sectors and the full cube |
| LUT size cap | 10 MiB, size 2..256, 3D only | Same policy as the existing LUT path |

**Why these choices**: the wheel model is deliberately the skill's own transform, so the
result can be re-applied with `PHOTO_GRADING` and checked with the existing LUT path. The
integer search and the coarse seed were added after diagnostics, not guessed: the float fit
looked better but returned a zone wheel that disappeared on rounding, and a pure statistics
seed could not start a wheel whose hue was far from 0. The weak-effect warning exists because
saturation on near-saturated shadow pixels can be visually inert (the same image fits at
saturation 24 or 50); reporting that is more honest than pretending the parameter is unique.

**Acceptance measured by the suite** (`tests/test_rea_roundtrip.py`, `tests/test_rea_lut_probe.py`):
parity 5e-7; identity exact; five pure grades on a held-out scene mean 0.0007–0.0055, p95 at
most 0.0098; a 33³ warm LUT probes back with held-out mean/p95 0.0075/0.0201; a 33³ teal LUT
0.0087/0.0121; a per-channel gamma LUT is reported as not expressible. Parameters off by more
than 10% of their range (10° for hue) must be named in `identifiability_warnings` — on the
synthetic scenes that is mainly shadow saturation, and it is flagged.

Not claimed: unique parameters. Wheels trade off (global vs midtones, saturation vs
luminance), and a weak direction on one scene may split differently on another. The fit
reports the image-space residual and the warning; it does not claim to recover the original
artist's slider values.

