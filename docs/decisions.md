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
