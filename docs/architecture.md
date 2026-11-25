# Architecture — photo-grading-skill

How the skill works, end to end. A photo request (`photo-grading/request@1`) is parsed and
validated (`src/photo_grading/model.py`), executed through typed operations by
`src/photo_grading/executor.py` using **FFmpeg's photo filters**, and every artifact is
re-probed and validated. No AI, no look judgement, no guessing values: the operations are typed,
parameter ranges are enforced, and measurements are recorded as OBSERVED values in
provenance. The critic measures distance to a target the caller supplies as numbers; that is
measurement, not judgment.

## The request pipeline

```
photo-grading/request@1 (stdin)
  -> parse_request()            typed validation, aliases, forbidden keys  (model.py)
  -> Executor.response()                                                (executor.py)
       -> run_project()                                                 (executor.py)
            per operation:
              _apply()          dispatch: FFmpeg filter chain for grading/correction/
                                HSL/LUT ops; critic report for ANALYZE/SCORE;
                                proxy loop + LUT render for OPTIMIZE
              build_chain()     typed ffmpeg filter chain (FFmpeg ops)     (executor.py)
              signalstats()     ffmpeg -vf signalstats,showinfo         (executor.py)
            outputs: bind each to its op's artifact, check_output()
  -> photo-grading/response@1 (stdout)
```

## Operations

| Type | Parameters | Execution |
|---|---|---|
| `PHOTO_GRADING` | `shadows_*/midtones_*/highlights_*/global_*` (hue 0-360, saturation 0-100, luminance -100..100), `blending` (0-100, default 50), `balance` (-100..100, default 0), `strength` (0..1, default 1.0) | A 3D `.cube` LUT built from the wheels (`buildlut.build_wheel_lut`), applied with `ffmpeg lut3d` |
| `PHOTO_CORRECTION` | `white_balance_temperature` (2500-10000), `white_balance_tint` (-100..100), `exposure` (-10..10), `contrast` (-100..100), `highlights`/`shadows`/`blacks`/`whites` (-100..100), `saturation` (-100..100), `vibrance` (-100..100), `sharpness` (0..100), `clarity` (0..100), `grain` (0..50, default 0), `tone_blacks`/`tone_shadows`/`tone_midtones`/`tone_highlights`/`tone_whites` (0..2, defaults 0, 0.15, 0.5, 0.85, 1.0) | `ffmpeg eq` + a white-balance LUT (`buildlut.build_wb_lut`, normalized channel gains, black-preserving) + a vibrance LUT (`build_vibrance_lut`, weighted, low-chroma gated) + a levels LUT (`build_levels_lut`) + a tone-curve LUT (`build_tone_curve_lut`, piecewise-linear anchors on BT.709 luma) via `lut3d` + `unsharp` (sharpness) + `cas` (clarity) + `noise=alls=N` (film grain) |
| `PHOTO_LUT_APPLY` | `lut_path` (required, `.cube`), `strength` (0..1, default 1.0) | `ffmpeg lut3d` on the caller's LUT (scaled toward identity via `buildlut.scale_lut_strength` when `strength < 1`) |
| `PHOTO_HSV` (user feedback #4: per-color HSL tuning) | `red_*`, `orange_*`, `yellow_*`, `green_*`, `cyan_*`, `blue_*`, `magenta_*` (`_hue` -100..100 = -40..40 degrees, `_saturation` -100..100, `_luminance` -100..100; defaults 0/0/0 per family) | HSL per-hue-family tweaks via `buildlut.build_hsl_lut`: normalized soft Gaussian family weights (no hard mask edges), applied only above ~30% saturation so neutral texture is never tinted; soft-headroom saturation/luminance via `lut3d` |
| `PHOTO_ANALYZE` | `max_pixels` (1000..5,000,000, default 250,000) | Pass-through: re-encode the input losslessly, attach an OKLab `report` (`critic.analyze_file`). No pixels change |
| `PHOTO_SCORE` | `target` (six required numbers: `shadow_hue`, `highlight_hue`, `tint_mag`, `colorfulness`, `median_L`, `spread`), `max_pixels` | `PHOTO_ANALYZE` plus `critic.score_metrics`: 0..100, every penalty term with measured value, target and tolerance |
| `PHOTO_OPTIMIZE` | `target`, `iterations` (1..200, default 40), `proxy_size` (64..1024, default 384), `lut_size` (17/33/65, default 33) | `critic.optimize_file`: deterministic coordinate descent on a proxy, bake the winner into a `.cube` LUT, rescore the proxy through numpy trilinear interpolation, render once at full size via `lut3d`, re-check the full render and fall back to an identity LUT if it would regress |
| `WHITE_BALANCE` (alias) | temperature/tint only, resolved to `PHOTO_CORRECTION` at validation | same as `PHOTO_CORRECTION` |

### Wheel semantics (PHOTO_GRADING)

Zones are BT.709 luma bands (shadows/midtones/highlights). The `balance` slider moves the
boundaries: positive balance widens midtones, negative moves shadows into them.

Each wheel carries (hue, saturation, luminance):
- A pixel in a wheel's zone gets its hue rotated by the wheel's hue and its saturation
  scaled by saturation/100 (a no-op when saturation is 0); luminance lifts/lowers channels
  by luminance/100 * 0.6. Near-black zone pixels get v=0.02 so the tint is visible.
- `blending` mixes the tinted LUT back toward identity: `out = tinted*(blending/100) + identity*(1-blending/100)`; 0 = no wheels.
- The `global` wheel applies to every pixel after the zone tints.

### LUT generation (deterministic, stdlib math)

`buildlut.build_wheel_lut` writes a `.cube` file: `LUT_3D_SIZE 64` with a full Adobe Cube 1.0
header (`TITLE`, `LUT_3D_SIZE`, `DOMAIN_MIN/MAX`), and the data lines are **0-1 floats**
(ffmpeg reads them as 0..1; 0-255 ints clip to white). Data lines are ordered **red fastest,
blue slowest**, as the Adobe Cube specification requires; one shared `_cube_points` iterator
is the only place that order is defined. Writing R-slowest/B-fastest made ffmpeg read every
LUT with R and B transposed — the false-color orange/blue blocks in the 1.5/10 audit.
`scale_lut_strength` uses the same order when it maps entry index back to an input color.

`buildlut.build_levels_lut` builds the correction LUT: shadows lift the dark band,
highlights/blacks/whites lift the corresponding bands. `build_tone_curve_lut` remaps BT.709
luma through piecewise-linear anchors and adds the delta to all three channels.
`build_wb_lut` applies normalized per-channel gains (largest gain = 1, so no channel clips,
and black stays black). `build_vibrance_lut` scales saturation with a weight that fades out
below ~30% saturation, so compressed texture and near-neutral surfaces are left alone.
`build_hsl_lut` blends the seven hue families with normalized soft Gaussian weights instead
of assigning a pixel to its nearest family.

HSV→RGB uses the standard six-sector table and is covered by a round-trip test: the original
table had all six sectors scrambled, which corrupted every hue rotation in the skill.

## Critic and optimizer (optional `critic` extra)

`critic.py` implements the measurement loop. It needs `numpy` and `Pillow` (the `[critic]`
extra); importing the module does not import either, so the core operations keep working
without the extra.

- **Target.** Six required numbers, no look names. Hue is an OKLab hue angle (0 = red/magenta,
  90 = yellow, 180 = green, 270 = blue; teal ~200, orange ~55), absolute — unlike a wheel hue,
  which is a rotation of the pixel's existing hue.
- **Analysis.** Decode to sRGB, sample by stride (`max_pixels`, no resize), convert to OKLab,
  and report median L, p05/p95, clipping, near-neutral cast, M3 colourfulness, shadow and
  highlight tint (mean chroma delta of the reference's L quartiles), skin-hue shift and mean
  OKLab distance. Cast is reported, never penalized.
- **Score.** `100 + Σ penalties`; each part carries `penalty`, `measured`, `target`,
  `tolerance`. Guards: skin hue free up to 6°, overcooked free up to 0.10 mean OKLab distance.
  A target tint below 0.005 is treated as no tint.
- **Optimizer.** Eight parameters (`exposure`, `contrast`, `saturation`, `sh_hue`, `sh_amt`,
  `hi_hue`, `hi_amt`, `balance`), fixed bounds, fixed order, shrinking step, no RNG, accepted
  steps only. Runs on a ~384 px proxy; bakes the winner into a 33³ LUT; re-scores the proxy
  through numpy trilinear interpolation (matching `lut3d`); escalates to 65³ if the LUT score
  is >0.5 below the direct grade; falls back to identity if the LUT path scores below it.
  The executor renders the LUT once at full size and re-checks the full render, re-rendering
  with an identity LUT if it would regress.
- **DAG semantics.** `PHOTO_ANALYZE`/`PHOTO_SCORE` measure their input against the project
  source, so a score describes the grade at that point. Standalone `analyze`/`score` default
  the reference to the image itself.

The optimizer is deterministic and safe, not globally optimal: coordinate descent can stop in
a local optimum. The score is distance to the supplied target under the guards, not a claim
about quality.

## Objective inspection (`photo-grading inspect`)

`quality.inspect_image` decodes the first frame to raw RGB and computes exact statistics:
luma percentiles, highlight/shadow clipping, mean and p95 saturation, neon-pixel share, hue
family shares, and white-balance cast measured on **near-neutral pixels only** (a green
landscape is not a color cast). It returns conservative warnings, not a score, so a grade
can be checked against measurable limits before it is posted.

## Execution details

- Every value reaching an argv is a fixed flag or a path this skill resolved itself:
  cwd-relative LUT paths, or quoted absolute paths with the drive colon escaped
  (`lut3d=file='C\:/...'`). No user-supplied filter strings.
- Each operation's declared `input` is honored (`source` or `op:<id>`): operations form a
  DAG, not an implicit linear chain. A second branch from `source` is never graded on top of
  the first branch — that bug produced the false-color candidate images in the 1.5/10 audit.
- Intermediates are always lossless 16-bit PNG (`rgb48be`) inside `.photo-grading/`; the
  requested output format is encoded exactly once at the end (PNG/TIFF keep 16 bits, JPEG
  uses `-q:v 2`, WebP `-quality 95`). A multi-op chain therefore never accumulates JPEG
  re-compression or 8-bit rounding between steps.
- Every artifact is re-probed: photo stream exists, width/height unchanged (tolerance 1px),
  readable, `size > 0`.
- Before/after measurements: `ffmpeg -vf signalstats,showinfo` (showinfo prints
  `mean:[Y U V]` of the first frame) recorded in `measurements.before/after` — OBSERVED
  values, never judged. 16-bit plane means are normalized to the 8-bit scale so before/after
  and 8-bit/16-bit sources stay comparable.
- Tool failures report the **tail** of ffmpeg's stderr (the banner is skipped), so the real
  cause is visible instead of "ffmpeg failed".

## Determinism & reuse

Identity = sha256 over canonical JSON of `{type, parameters, input_hash, tool_versions,
skill_version, pipeline fingerprint}`. `input_hash` is the hash of that operation's actual
input artifact (not the original source), so changing an upstream op invalidates every
downstream cache entry. The pipeline fingerprint is a hash of `buildlut.py`, `executor.py`
and `model.py`: upgrading the engine invalidates cached intermediates instead of silently
reusing artifacts produced by an older, buggy pipeline. `--no-reuse` disables reuse for a
run (it was parsed but ignored before the 1.5/10 audit).

A run writes a `.photo-grading/<op>.stamp.json` with the identity and result; on a matching
re-run, the intermediate is reused (`reused: true`). LUT filenames are
`sha256(content)[:16]` — deterministic per parameter values.

## Validation of outputs (post-run)

`Executor._check_geometry_unchanged`: re-probes and compares width/height vs the source
(tolerance `GEOMETRY_TOLERANCE` px). `_check_readable`: the file opens for reading.

## Path policy (`security.py`)

- Inputs/LUTs: regular files (symlinks resolved); inside allowed roots (default: the
  workspace; `--allowed-input`, `--allowed-lut` widen). LUTs additionally must be `.cube`,
  ≤ 10 MiB.
- Outputs: inside the workspace, never an existing file unless `overwrite: true`
  (mutates_input is false), no traversal, no symlink escapes.
- No shell, no `eval`, no network.
