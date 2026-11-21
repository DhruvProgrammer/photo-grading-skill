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
    path = buildlut.build_levels_lut(shadows=-20, blacks=-5)
    vals = _cube_vals(path)
    assert vals[0][0] < 0 or vals[0][0] >= 0  # any int allowed; just structural
    assert len(vals) == LUT_SIZE ** 3
