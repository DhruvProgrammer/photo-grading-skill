# Changelog

All notable changes to photo-grading-skill are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- `src/photo_grading/analysis/`: `colorspace.py` (shared OKLab/OKLCH math), `lutio.py`
  (trilinear `.cube` interpolation) and `descriptors.py` (target-free look measurements).
  `critic.py` re-exports the names, so existing imports keep working.
- `PHOTO_ANALYZE` look descriptors: OKLab L percentiles 1/5/25/50/75/95/99, zone tints,
  mean/p90 chroma and 12 hue sectors, a seeded five-colour OKLab palette with weights, and
  rough skin-band stats. New `seed` parameter (default 0) for the palette.
- `PHOTO_ANALYZE`: pass-through OKLab measurement (median L, p05/p95 spread, clipping,
  near-neutral cast, Hasler-Süsstrunk M3, shadow/highlight tint, skin-hue shift, mean OKLab
  distance).
- `PHOTO_SCORE`: `PHOTO_ANALYZE` plus a 0..100 score against a caller-supplied target look
  (six required numbers: `shadow_hue`, `highlight_hue`, `tint_mag`, `colorfulness`,
  `median_L`, `spread`), with every penalty term reported.
- `PHOTO_OPTIMIZE`: deterministic coordinate descent over eight grade parameters on a ~384 px
  proxy; bakes the winner into a 3D `.cube` LUT, re-scores through numpy trilinear
  interpolation and renders once at full size. Accepted steps only; identity fallback; never
  worse than the untouched image.
- CLI `analyze`, `score`, `optimize`; optional `[analysis]` extra (`numpy`, `Pillow`);
  `[critic]` is kept as a compatibility alias. `analyze --seed`.
- `write_cube(..., directory=...)` and a quoted absolute-path form for `lut3d`.
- `analysis/fit_params.py`: a vectorized NumPy port of the `PHOTO_GRADING` wheel transform
  (pinned to `build_wheel_lut` on a 17³ grid, max difference 5e-7) and a deterministic
  integer-space fit. It seeds from OKLab statistics, searches a coarse (hue, saturation) grid,
  then runs coordinate descent on a Huber ΔE_OK loss with a small L2 pull and an 80/20
  train/hold-out split. Reports integer params, train/held-out mean and p95 ΔE_OK, the
  dropped clipped fraction, settings, and `identifiability_warnings` (bound, weak effect,
  correlation).
- `analysis/probe_lut.py`: Mode C. Parses a 3D `.cube` with the new `lutio.read_cube`, probes
  64 neutral grays + 12 hues × 3 chroma × 3 luma patches + 4,096 seeded colors, reports the
  neutral ramp, black lift, white roll-off, tint versus luma and per-sector chroma/hue shift,
  and fits the same wheel model. Says "not expressible as wheels" above 0.02 held-out mean
  ΔE_OK and points at `PHOTO_LUT_APPLY`.
- `lutio.read_cube`: a size-checked 3D `.cube` parser (10 MiB cap, size 2..256, comments and
  the standard header, dense `[b, g, r, 3]` table).

### Changed

- Critic targets below 0.005 tint are treated as no tint, so the optimizer does not chase
  invisible hue noise.
- The README states explicitly that scoring against a caller-supplied target is measurement,
  not judgment; the skill still never decides a look.
- Colour math and LUT interpolation moved out of `critic.py` into `analysis/`; the critic
  imports them instead of keeping a second copy.

### Fixed

- `PHOTO_GRADING` runs failed with `FileNotFoundError` after `_lut_arg` started quoting LUT
  paths: the provenance step hashed the filter argument (`'grading_wheels_….cube'`, quotes
  included) instead of the filesystem path. `_lut_file_value` now inverts `_lut_arg`, with a
  round-trip test for relative and absolute Windows paths.

### Tests

- 104 unit tests, including 14 critic/optimizer tests, 9 analysis tests and 17 reverse-
  engineering tests. The analysis tests include a real-FFmpeg `lut3d` parity check: mean
  ΔE_OK < 0.01, p95 < 0.02. The reverse-engineering tests add a model/builder parity check
  (5e-7), pure-grade round-trips on a held-out scene (mean < 0.01, p95 < 0.03), identity and
  determinism, and Mode C on known and deliberately non-wheel LUTs.

## [0.1.0] — 2026-11-22

### Added

- Deterministic photo color grading / photo color correction execution Skill.
- `PHOTO_GRADING`: 3-way Color Grading wheels (Shadows / Midtones / Highlights / Global:
  hue, saturation, luminance), `blending` and `balance`, executed via a generated 3D `.cube`
  LUT + FFmpeg `lut3d` (ADR-01).
- `PHOTO_CORRECTION`: typed corrections (white balance temperature/tint, exposure, contrast,
  highlights, shadows, blacks, whites, saturation, sharpness), executed via `eq` + `hue` +
  `unsharp` + a generated levels LUT (ADR-02).
- `PHOTO_LUT_APPLY`: 3D `.cube` LUT application via `lut3d`.
- `WHITE_BALANCE` alias of `PHOTO_CORRECTION` (temperature/tint only, ADR-03).
- Machine-readable contract (`photo-grading skill --json`, `contract/contract.json`),
  environment diagnosis (`photo-grading doctor --json`), `validate`, `plan`, `run`.
- Validation: re-probe every output (photo stream, width/height unchanged, readable);
  OBSERVED before/after measurements via `signalstats,showinfo` (ADR-04).
- Reuse: content-addressed identity + intermediate reuse (ADR-07).
- Path policy: inputs/LUTs/outputs inside the workspace by default, symlink resolution,
  forbidden-field rejection (ADR-06).
- Research dump: `knowledge.md` — photo color grading sources and techniques (Teal &
  Orange, complementary colors, HSL, curves, skin protection, ...).

### Tests

- 34 unit tests (LUT builder, model validation, path policy, contract) in `tests/`.
