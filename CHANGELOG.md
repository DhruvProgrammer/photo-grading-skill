# Changelog

All notable changes to photo-grading-skill are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
