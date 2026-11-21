# Architecture — photo-grading-skill

How the skill works, end to end. A photo request (`photo-grading/request@1`) is parsed and
validated (`src/photo_grading/model.py`), executed through typed operations by
`src/photo_grading/executor.py` using **FFmpeg's photo filters**, and every artifact is
re-probed and validated. No AI, no judgement, no guessing values: the operations are typed,
parameter ranges are enforced, and measurements are recorded as OBSERVED values in
provenance.

## The request pipeline

```
photo-grading/request@1 (stdin)
  -> parse_request()            typed validation, aliases, forbidden keys  (model.py)
  -> Executor.response()                                                (executor.py)
       -> run_project()                                                 (executor.py)
            per operation:
              build_chain()     typed ffmpeg filter chain                (executor.py)
              _apply()          ffmpeg run; probe; validate geometry    (executor.py)
              signalstats()     ffmpeg -vf signalstats,showinfo         (executor.py)
            outputs: bind each to its op's artifact, check_output()
  -> photo-grading/response@1 (stdout)
```

## Operations

| Type | Parameters | Execution |
|---|---|---|
| `PHOTO_GRADING` | `shadows_*/midtones_*/highlights_*/global_*` (hue 0-360, saturation 0-100, luminance -100..100), `blending` (0-100, default 50), `balance` (-100..100, default 0) | A 3D `.cube` LUT built from the wheels (`buildlut.build_wheel_lut`), applied with `ffmpeg lut3d` |
| `PHOTO_CORRECTION` | `white_balance_temperature` (2500-10000), `white_balance_tint` (-100..100), `exposure` (-10..10), `contrast` (-100..100), `highlights`/`shadows`/`blacks`/`whites` (-100..100), `saturation` (-100..100), `sharpness` (0..100) | `ffmpeg eq` + `hue` (white balance) + `unsharp` (sharpness) + a levels LUT (`buildlut.build_levels_lut`) via `lut3d` |
| `PHOTO_LUT_APPLY` | `lut_path` (required, `.cube`) | `ffmpeg lut3d` on the caller's LUT |
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

`buildlut.build_wheel_lut` writes a `.cube` file: `LUT_3D_SIZE 64`, and the data lines are
**0-1 floats** (ffmpeg reads them as 0..1; 0-255 ints clip to white). LUT entries are written
in R-slowest/B-fastest order, matching ffmpeg's `lut3d` read convention.

`buildlut.build_levels_lut` builds the correction LUT: shadows lift the dark band,
highlights/blacks/whites lift the corresponding bands.

## Execution details

- Every value reaching an argv is a fixed flag or a path this skill resolved itself:
  cwd-relative LUT paths (the LUT is written into the cwd), or POSIX-style absolute paths
  with `:`-escaping. No user-supplied filter strings.
- Outputs keep the source photo's extension (ffmpeg can't infer the muxer from `.out`).
- Every artifact is re-probed: photo stream exists, width/height unchanged (tolerance 1px),
  readable, `size > 0`.
- Before/after measurements: `ffmpeg -vf signalstats,showinfo` (showinfo prints
  `mean:[Y U V]` of the first frame) recorded in `measurements.before/after` — OBSERVED
  values, never judged.

## Determinism & reuse

Identity = sha256 over canonical JSON of `{type, parameters, input_identity (sha256 of the
file), tool_versions}` — no timestamps, no UUIDs. A run writes a `.photo-grading/<op>.stamp.json`
with the identity and result; on a matching re-run, the intermediate is reused (`reused: true`).
LUT filenames are `sha256(content)[:16]` — deterministic per wheel values.

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
