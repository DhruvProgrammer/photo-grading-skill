# Testing

`python -m pytest -q` from the repo root. 34 tests, nothing skipped, no mocks of the
execution layer beyond path-policy fixtures (unit level).

- **tests/test_lut.py** (5) — the 3D-wheel LUT builder: identity when empty wheels, teal
  shadows change the LUT, determinism (same wheels → same bytes), balance moves the zone
  boundaries, levels LUT structure.
- **tests/test_model.py** (11) — request validation: valid grading / correction / LUT-apply
  documents; `WHITE_BALANCE` alias resolution and restriction; a parametrized matrix of
  invalid documents (unknown fields, type errors, out-of-range, missing required LUT path,
  extension mismatch, forbidden keys, undeclared output refs); output operation refs.
- **tests/test_security.py** (7) — `PathPolicy`: inputs in/out of the workspace, output
  rules (inside, overwrite, collision with input, directory), LUT extension/size rules.
- **tests/test_contract.py** (4) — contract identity, operations table, error codes +
  aliases, and the committed `contract/contract.json` matches the code (regenerate with
  `python contract/generate.py`).

The CLI is exercised by smoke tests in `tests/` indirectly (via `parse_request` +
`Executor`); end-to-end behavior is verified by the smoke run used during development:
`photo-grading run` on a real photo produces a validated output with real before/after
measurements (e.g. `{"before": {"yavg": 112, "uavg": 115, "vavg": 112},
"after": {"yavg": 106, "uavg": 128, "vavg": 127}}`), and a second run reuses the
intermediate (`"reused": true`).
