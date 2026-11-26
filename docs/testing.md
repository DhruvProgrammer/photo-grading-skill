# Testing

`python -m pytest -q` from the repo root. 86 tests, nothing skipped, no mocks of the
execution layer beyond path-policy fixtures (unit level). The analysis/critic tests skip if the
optional `[analysis]` extra (numpy + Pillow; `[critic]` is an alias) is not installed.

- **tests/test_lut.py** (16) — the 3D LUT builders: identity when empty wheels, teal
  shadows change the LUT, determinism (same wheels → same bytes), balance moves the zone
  boundaries, levels/tone-curve/WB/vibrance/HSL structure, strength scaling.
- **tests/test_model.py** (24) — request validation: valid grading / correction / LUT-apply /
  critic documents; `WHITE_BALANCE` alias resolution and restriction; a parametrized matrix of
  invalid documents (unknown fields, type errors, out-of-range, missing required LUT path,
  extension mismatch, forbidden keys, undeclared output refs); critic targets require all six
  numeric fields, reject look names and unknown keys; optimizer bounds.
- **tests/test_security.py** (7) — `PathPolicy`: inputs in/out of the workspace, output
  rules (inside, overwrite, collision with input, directory), LUT extension/size rules.
- **tests/test_contract.py** (4) — contract identity, operations table, error codes +
  aliases, and the committed `contract/contract.json` matches the code (regenerate with
  `python contract/generate.py`).
- **tests/test_critic.py** (14) — OKLab round trip and hue wrap; neutral/clipping analysis;
  M3 colourfulness and cast; measured tint hue/strength; skin mask; every score part reported;
  zero/sub-visible target tint; skin and overcooked guards; trilinear LUT interpolation vs the
  direct grade; optimizer determinism, improvement and identity fallback; `analyze_file`,
  `score_file`, `optimize_file` (JSON-serializable, LUT written).
- **tests/test_analysis.py** (9) — the shared names are the same objects in `critic` and
  `analysis`; identity LUT interpolation; tone percentiles and zone masks; neutral image has no
  tint and no skin; zone-tint hue direction on a split-toned neutral ramp; 12 hue sectors and
  seeded palette determinism; skin band; **real FFmpeg parity** (a graded 33³ LUT rendered by
  `ffmpeg lut3d` vs `apply_lut_numpy`: mean ΔE_OK < 0.01, p95 < 0.02); `analyze_file` includes
  descriptors and honours `seed`.
- **tests/test_executor.py** (6) — correction filter chains, tone LUT inclusion, HSL chain,
  LUT-argument quoting for absolute Windows paths, and DAG input wiring.
- **tests/test_transcript_tips.py** (6) — `PHOTO_GRADING.strength`, `PHOTO_LUT_APPLY.strength`
  and `PHOTO_CORRECTION.grain`.

## Real-photo validation

Beyond the unit suite, the critic/optimizer was exercised on two real files:

- **Naturalistic lake (500×889).** `analyze` and `score` produced the expected OKLab metrics;
  `optimize` moved the proxy score from 95.79 to 99.67 and the full-size render from 95.85 to
  96.71 (exposure −0.025, contrast +0.025; no tint added). The optimized output matches the
  delivered naturalistic grade closely.
- **Teal-orange leopard (221×148).** `optimize` moved the proxy score from −14.75 to 65.94 and
  the full render from −14.75 to 64.02; the delivered hand grade scores 65.59 under the same
  target and guards. The remaining gap is the skin/overcooked guard plus unreachable target
  contrast, not a regression.
- **DAG.** A request with `PHOTO_ANALYZE` → `PHOTO_SCORE` on the lake source produced a
  lossless 16-bit pass-through output and a `report` on both operations; the score report
  measured the source against the project source (median L 0.7548, score 94.16 at 50k samples).
- **Descriptors on real photos.** Lake: tone p01 0.1605 / p50 0.7548 / p99 0.9587, zone tints
  136.7° / 280.0° / 341.2° (mag < 0.015), five palette colours, skin not detected. Leopard:
  median L 0.8970, zone tints 71.3° / 252.7° / 250.8°, five palette colours, skin band detected
  at 3.16% of the sample (mean hue 68.0°). Both runs are byte-stable for a given `seed`.

`photo-grading run` on a real photo produces a validated output with real before/after
measurements (e.g. `{"before": {"yavg": 112, "uavg": 115, "vavg": 112},
"after": {"yavg": 106, "uavg": 128, "vavg": 127}}`), and a second run reuses the
intermediate (`"reused": true`).
