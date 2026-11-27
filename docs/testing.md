# Testing

`python -m pytest -q` from the repo root. 104 tests, nothing skipped, no mocks of the
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
- **tests/test_executor.py** (7) — correction filter chains, tone LUT inclusion, HSL chain,
  LUT-argument quoting for absolute Windows paths (and the inverse used by provenance),
  and DAG input wiring.
- **tests/test_transcript_tips.py** (6) — `PHOTO_GRADING.strength`, `PHOTO_LUT_APPLY.strength`
  and `PHOTO_CORRECTION.grain`.
- **tests/test_rea_roundtrip.py** (11) — Phase 2 acceptance: the vectorized wheel model vs
  `build_wheel_lut` on a 17³ grid (max difference < 1e-5), identity fit, five known pure
  grades fitted on one balanced scene and applied to a different held-out scene (mean ΔE_OK
  < 0.01, p95 < 0.03), parameter deviations above 10% of range must be named in
  `identifiability_warnings`, determinism, clipped-pixel reporting, and input validation.
- **tests/test_rea_lut_probe.py** (6) — Mode C: the probe set's sizes/seed determinism, an
  identity LUT is a reported no-op, a known 33³ wheel LUT recovers its main params, a
  per-channel gamma LUT is reported as not expressible with the `PHOTO_LUT_APPLY` message,
  missing/malformed `.cube` errors, and the red-fastest cube axis order.

The two Phase 2 files take about 30 seconds because several tests run the real fit. They are
not mocked: a fitted parameter set is applied to a different image and measured in OKLab.

## Reverse-engineering results (Phase 2)

Measured by `tests/test_rea_roundtrip.py` and `tests/test_rea_lut_probe.py` (and reproduced in
`docs/decisions.md` ADR-10):

- Model/builder parity: max absolute difference 5e-7 on a 17³ grid (the builder writes six
  decimal places).
- Identity: the fit returns all wheel params 0, blending 50/100 (both identity here), and an
  output difference of exactly 0.
- Pure grades, fit on one balanced 64×80 scene, applied to a different seed:
  global 0.0024/0.0061, shadows 0.0013/0.0066, highlights 0.0007/0.0059, teal
  0.0041/0.0081, warm 0.0055/0.0098 (mean/p95 ΔE_OK).
- Mode C on a 33³ warm LUT: shadows 210/18/−6, highlights 40/32/7, global 30/9/3, blending
  80, balance 11 (truth 210/22/−5, 40/30/8, 30/12/3, 80, 10); held-out mean/p95
  0.0075/0.0201. On a 33³ teal LUT: 0.0087/0.0121.
- A per-channel gamma LUT: not expressible as wheels, held-out mean 0.0425, message points
  at `PHOTO_LUT_APPLY`.

Known limits: shadow saturation is often weakly identified on these synthetic scenes (a
near-saturated dark pixel barely changes when the wheel saturation scales), so the fit flags
it instead of claiming an exact slider value. The existing `eq`-based `PHOTO_CORRECTION` is
not part of this fit; it is Phase 3.

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
