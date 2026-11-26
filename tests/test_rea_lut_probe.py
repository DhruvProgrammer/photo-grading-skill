"""Mode C: probe a .cube LUT, report readable facts, and fit wheel params when the LUT is
expressible as the skill's own wheel model."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("numpy")

from photo_grading import buildlut  # noqa: E402
from photo_grading.analysis import fit_params, probe_lut  # noqa: E402
from photo_grading.errors import PhotoError  # noqa: E402


def _np():
    import numpy as np
    return np


def _base(**over):
    params = {name: 0.0 for name in fit_params.PARAM_NAMES}
    params["blending"] = 100.0
    params.update(over)
    return params


WARM = _base(shadows_hue=210.0, shadows_saturation=22.0, shadows_luminance=-5.0,
             highlights_hue=40.0, highlights_saturation=30.0, highlights_luminance=8.0,
             global_hue=30.0, global_saturation=12.0, global_luminance=3.0,
             blending=80.0, balance=10.0)


def _write_wheels(tmp_path, params, size=33):
    path = buildlut.build_wheel_lut(fit_params.params_to_wheels(params),
                                    params["blending"], params["balance"], size=size)
    return path


def test_probe_points_are_deterministic_and_sized():
    np = _np()
    a = probe_lut.probe_points(seed=0)
    b = probe_lut.probe_points(seed=0)
    c = probe_lut.probe_points(seed=1)
    assert a["sizes"] == {"neutral": 64, "hue_patches": 108, "uniform": 4096}
    assert len(a["points"]) == 64 + 108 + 4096
    for key in ("points", "neutral", "hue_patches", "hue_centers"):
        assert np.array_equal(a[key], b[key])
    assert np.array_equal(a["uniform"], c["uniform"]) is False
    assert np.allclose(a["neutral"][:, 0], a["neutral"][:, 1])
    assert np.allclose(a["neutral"][:, 1], a["neutral"][:, 2])


def test_probe_identity_lut_is_a_no_op(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    path = buildlut.build_wheel_lut({})
    report = probe_lut.probe_lut(path, seed=0)
    assert report["expressible_as_wheels"] is True
    assert report["fit"]["mean_delta_E_OK"] < 0.005
    assert report["facts"]["neutral_no_op"] is True
    assert report["facts"]["neutral_max_delta_E_OK"] < 0.005
    assert report["facts"]["black_lift"] == [0.0, 0.0, 0.0]
    assert report["facts"]["white_rolloff"] == [1.0, 1.0, 1.0]
    for wheel in fit_params.WHEELS:
        assert report["params"][f"{wheel}_saturation"] == 0
    assert report["measurements"] == "OBSERVED"
    json.dumps(report)


def test_probe_recovers_a_known_wheel_lut(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    path = _write_wheels(tmp_path, WARM, size=33)
    report = probe_lut.probe_lut(path, seed=0)
    assert report["expressible_as_wheels"] is True, report["message"]
    assert report["lut"]["size"] == 33
    assert report["fit"]["source"] == "heldout"
    assert report["fit"]["mean_delta_E_OK"] <= probe_lut.RESIDUAL_THRESHOLD
    assert report["fit"]["p95_delta_E_OK"] < 0.03
    assert report["fit"]["probe_points"] == 64 + 108 + 4096
    params = report["params"]
    assert abs(params["shadows_hue"] - 210) <= 10
    assert abs(params["highlights_hue"] - 40) <= 10
    assert abs(params["global_hue"] - 30) <= 10
    assert abs(params["blending"] - 80) <= 5
    assert abs(params["balance"] - 10) <= 3
    assert report["facts"]["neutral_no_op"] is False
    assert len(report["facts"]["neutral_ramp"]["input"]) == 64
    assert len(report["facts"]["hue_sectors"]) == 12
    assert all("chroma_ratio" in s and "hue_shift_deg" in s
               for s in report["facts"]["hue_sectors"])
    json.dumps(report)


def test_probe_says_a_non_wheel_lut_is_not_expressible(tmp_path, monkeypatch):
    """A per-channel gamma curve is a real grade, but not a wheel grade. The report must
    still return its best fit while saying plainly that the LUT is not expressible."""
    np = _np()
    n = 17
    axis = np.linspace(0.0, 1.0, n)
    bb, gg, rr = np.meshgrid(axis, axis, axis, indexing="ij")
    table = np.stack([bb, gg, rr], axis=-1)  # cube order [b, g, r]
    table[..., 2] = rr ** 2                  # red is squared, a non-wheel tone curve
    report = probe_lut.probe_table(table, n, seed=0)
    assert report["expressible_as_wheels"] is False
    assert report["fit"]["mean_delta_E_OK"] > probe_lut.RESIDUAL_THRESHOLD
    assert "not expressible as wheels" in report["message"]
    assert "PHOTO_LUT_APPLY" in report["message"]
    assert set(report["params"]) == set(fit_params.PARAM_NAMES)
    json.dumps(report)


def test_probe_rejects_missing_and_malformed_cube(tmp_path):
    with pytest.raises(PhotoError) as exc:
        probe_lut.probe_lut(str(tmp_path / "missing.cube"))
    assert exc.value.code == "INVALID_INPUT"

    no_size = tmp_path / "no_size.cube"
    no_size.write_text("TITLE broken\n" + "\n".join(["0.1 0.2 0.3"] * 10))
    with pytest.raises(PhotoError) as exc:
        probe_lut.probe_lut(str(no_size))
    assert exc.value.code == "UNSUPPORTED_FORMAT"

    short = tmp_path / "short.cube"
    short.write_text("LUT_3D_SIZE 2\n" + "\n".join(["0 0 0"] * 7))
    with pytest.raises(PhotoError) as exc:
        probe_lut.probe_lut(str(short))
    assert exc.value.code == "UNSUPPORTED_FORMAT"
    assert "expected 8" in exc.value.message

    non_finite = tmp_path / "non_finite.cube"
    non_finite.write_text("LUT_3D_SIZE 2\n" + "\n".join(["0 0 0"] * 7 + ["nan 0 0"]))
    with pytest.raises(PhotoError) as exc:
        probe_lut.probe_lut(str(non_finite))
    assert exc.value.code == "UNSUPPORTED_FORMAT"
    assert "not finite" in exc.value.message


def test_read_cube_orders_red_fastest(tmp_path):
    """Regression pin for the cube axis order: entry 1 is input (1/1, 0, 0) = red. The parser
    also accepts a UTF-8 BOM, full-line comments and trailing comments."""
    path = tmp_path / "axis.cube"
    rows = []
    n = 2
    for b in range(n):
        for g in range(n):
            for r in range(n):
                rows.append(f"{r} {g} {b}  # r g b")
    path.write_text("# a comment\nTITLE axis\nLUT_3D_SIZE 2\n" + "\n".join(rows) + "\n",
                    encoding="utf-8-sig")
    cube = probe_lut.read_cube(str(path))
    np = _np()
    # table is [b, g, r, 3]; entry (0, 0, 1) is input red, (0, 1, 0) green, (1, 0, 0) blue.
    assert np.array_equal(cube["table"][0, 0, 1], np.array([1.0, 0.0, 0.0]))
    assert np.array_equal(cube["table"][0, 1, 0], np.array([0.0, 1.0, 0.0]))
    assert np.array_equal(cube["table"][1, 0, 0], np.array([0.0, 0.0, 1.0]))
