# Changelog

All notable changes to photo-grading-skill are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

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
- CLI `analyze`, `score`, `optimize`; optional `[critic]` extra (`numpy`, `Pillow`).
- `write_cube(..., directory=...)` and a quoted absolute-path form for `lut3d`.

### Changed

- Critic targets below 0.005 tint are treated as no tint, so the optimizer does not chase
  invisible hue noise.
- The README states explicitly that scoring against a caller-supplied target is measurement,
  not judgment; the skill still never decides a look.

### Tests

- 77 unit tests, including 14 critic/optimizer tests.

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
