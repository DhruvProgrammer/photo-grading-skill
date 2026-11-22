import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from photo_grading import buildlut  # noqa: E402

LUT_SIZE = 64


def _cube_vals(path):
    lines = Path(path).read_text(encoding="ascii").splitlines()
    assert lines[0] == "TITLE PHOTO_GRADING_WHEELS" or lines[0].startswith("TITLE")
    assert lines[1] == f"LUT_3D_SIZE {LUT_SIZE}"
    body = [tuple(float(v) for v in line.split()) for line in lines[3:]]
    assert len(body) == LUT_SIZE ** 3
    assert all(len(v) == 3 and all(0.0 <= x <= 1.0 for x in v) for v in body)
    return body


def test_wheel_lut_identity_when_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    path = buildlut.build_wheel_lut({})
    vals = _cube_vals(path)
    # no saturation anywhere -> identity
    assert vals[0] == (0.0, 0.0, 0.0)
    assert vals[-1] == (1.0, 1.0, 1.0)


def test_wheel_lut_teal_shadows_changes_only_shadows(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    empty = _cube_vals(buildlut.build_wheel_lut({}))
    tuned = _cube_vals(buildlut.build_wheel_lut({"shadows": {"hue": 190, "saturation": 30, "luminance": 0},
                                                 "highlights": {"hue": 40, "saturation": 20, "luminance": 0}}))
    assert tuned != empty, "wheels with saturation should change the LUT"
    changed = [i for i in range(len(tuned)) if tuned[i] != empty[i]]
    assert changed, "expected some pixels to change"
    # tints add color spread where they apply
    assert any(len(set(tuned[i])) > 1 for i in changed)


def test_wheel_lut_deterministic(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    wheels = {"shadows": {"hue": 190, "saturation": 30, "luminance": -10},
              "midtones": {"hue": 0, "saturation": 0, "luminance": 0},
              "highlights": {"hue": 40, "saturation": 20, "luminance": 10},
              "global": {"hue": 0, "saturation": 0, "luminance": 0}}
    a = Path(buildlut.build_wheel_lut(wheels)).read_text(encoding="ascii")
    b = Path(buildlut.build_wheel_lut(wheels)).read_text(encoding="ascii")
    assert a == b


def test_wheel_lut_balance_moves_boundaries(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    wheels = {"shadows": {"hue": 190, "saturation": 30, "luminance": 0},
              "midtones": {"hue": 0, "saturation": 0, "luminance": 0},
              "highlights": {"hue": 40, "saturation": 0, "luminance": 0},
              "global": {"hue": 0, "saturation": 0, "luminance": 0}}
    hi = _cube_vals(buildlut.build_wheel_lut(wheels, balance=-100))
    lo = _cube_vals(buildlut.build_wheel_lut(wheels, balance=100))
    assert hi != lo


def test_levels_lut(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    empty = _cube_vals(buildlut.build_levels_lut())
    tuned = _cube_vals(buildlut.build_levels_lut(shadows=-20, blacks=-5))
    assert len(tuned) == LUT_SIZE ** 3
    assert all(0.0 <= x <= 1.0 for v in tuned for x in v)
    changed = [i for i in range(len(tuned)) if tuned[i] != empty[i]]
    assert changed, "levels should change the LUT where the bands lift/darken"
    # shadow-band points strictly darker: shadows=-20 in the shadows band, blacks=-5 below 0.25
    darker = [i for i in changed if all(tuned[i][c] < empty[i][c] - 1e-9 for c in range(3))]
    assert darker, "expected strictly darker points in the shadows/black bands"


def _identity_lut_points(n=LUT_SIZE):
    # file order: R-slowest/B-fastest; i = r*n^2 + g*n + b
    return [(i // (n * n) / (n - 1), (i // n) % n / (n - 1), i % n / (n - 1)) for i in range(n ** 3)]


def test_tone_curve_lut_defaults_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    vals = _cube_vals(buildlut.build_tone_curve_lut())
    assert all(abs(a - b) < 1e-5 for va, vb in zip(vals, _identity_lut_points()) for a, b in zip(va, vb))


def test_tone_curve_lut_lifts_blacks(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    vals = _cube_vals(buildlut.build_tone_curve_lut(blacks=0.2))
    assert vals[0] == (0.2, 0.2, 0.2), "L=0 should map to the blacks anchor"
    assert vals[-1] == (1.0, 1.0, 1.0), "L=1 identity"


def test_hsl_lut_green_hue_shift(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    empty = _cube_vals(buildlut.build_hsl_lut({}))
    tuned = _cube_vals(buildlut.build_hsl_lut({"green": {"hue": 30, "saturation": 0, "luminance": -10}}))
    assert tuned != empty, "green tweaks should change the LUT"
    assert any(tuned[i] != empty[i] for i in range(len(tuned))), "some pixels changed"


def test_hsl_lut_blue_luminance(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    empty = _cube_vals(buildlut.build_hsl_lut({}))
    tuned = _cube_vals(buildlut.build_hsl_lut({"blue": {"hue": 0, "saturation": 0, "luminance": -20}}))
    assert any(tuned[i] != empty[i] for i in range(len(tuned))), "blue luminance should darken blue pixels"
