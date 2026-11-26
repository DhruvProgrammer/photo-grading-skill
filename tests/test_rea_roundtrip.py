"""Phase 2 acceptance: the wheel model matches the builder, and known pure-parametric
grades round-trip through the fit onto a held-out synthetic scene."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("numpy")

from photo_grading import buildlut  # noqa: E402
from photo_grading.analysis import fit_params  # noqa: E402
from photo_grading.analysis.lutio import read_cube  # noqa: E402
from photo_grading.errors import PhotoError  # noqa: E402


def _np():
    import numpy as np
    return np


def _base(**over):
    params = {name: 0.0 for name in fit_params.PARAM_NAMES}
    params["blending"] = 100.0
    params.update(over)
    return params


# Five pure-parametric grades: one global, one per zone, and two split-tone looks.
GRADES = {
    "global": _base(global_hue=30.0, global_saturation=40.0),
    "shadows": _base(shadows_hue=200.0, shadows_saturation=50.0),
    "highlights": _base(highlights_hue=55.0, highlights_saturation=40.0),
    "teal": _base(shadows_hue=200.0, shadows_saturation=40.0, highlights_hue=55.0,
                  highlights_saturation=35.0, global_saturation=5.0),
    "warm": _base(shadows_hue=210.0, shadows_saturation=22.0, shadows_luminance=-5.0,
                  highlights_hue=40.0, highlights_saturation=30.0, highlights_luminance=8.0,
                  global_hue=30.0, global_saturation=12.0, global_luminance=3.0,
                  blending=80.0, balance=10.0),
}


def _scene(seed, h=64, w=80):
    """Balanced bands of shadow, midtone and highlight colors, plus skin/foliage/sky
    patches. Different seeds change the colors but keep the same zone structure."""
    np = _np()
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(h):
        y = i / (h - 1)
        band = 0 if y < 1 / 3 else (1 if y < 2 / 3 else 2)
        if band == 0:
            value = 0.04 + 0.13 * rng.random(w)
            chroma = (0.25 + 0.5 * rng.random(w)) * 0.4
        elif band == 1:
            value = 0.32 + 0.36 * rng.random(w)
            chroma = 0.25 + 0.5 * rng.random(w)
        else:
            value = 0.86 + 0.12 * rng.random(w)
            chroma = 0.25 + 0.5 * rng.random(w)
        rows.append(fit_params.hsv_to_rgb(rng.random(w) * 360.0, np.clip(chroma, 0, 1),
                                          np.clip(value, 0, 1)))
    img = np.stack(rows, axis=0)
    img[8:20, 8:20] = [0.72, 0.52, 0.40]
    img[8:20, 32:44] = [0.18, 0.42, 0.22]
    img[36:48, 8:20] = [0.22, 0.38, 0.62]
    img[52:60, 40:60] = [0.93, 0.90, 0.86]
    return np.clip(img, 0.004, 0.996)


def _delta(before, truth, params):
    np = _np()
    got = fit_params.apply_wheel_grade(before.reshape(-1, 3), params)
    want = truth.reshape(-1, 3)
    d = np.linalg.norm(fit_params.rgb_to_oklab(got) - fit_params.rgb_to_oklab(want), axis=1)
    return float(d.mean()), float(np.percentile(d, 95))


def _circular_diff(a, b):
    return abs((float(a) - float(b) + 180.0) % 360.0 - 180.0)


def _tolerance(name):
    if name.endswith("_hue"):
        return 10.0
    if name == "blending":
        return 15.0
    if name.endswith("_saturation"):
        return 10.0
    if name.endswith("_luminance"):
        return 20.0
    if name == "balance":
        return 20.0
    raise AssertionError(f"unexpected parameter {name}")


def test_wheel_model_matches_the_builder(tmp_path, monkeypatch):
    """The fit must not use a lookalike: apply_wheel_grade has to reproduce the exact
    grid build_wheel_lut writes (6-decimal formatting is the only difference)."""
    np = _np()
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    truth = GRADES["warm"]
    path = buildlut.build_wheel_lut(fit_params.params_to_wheels(truth), truth["blending"],
                                    truth["balance"], size=17)
    cube = read_cube(path)
    n = cube["size"]
    ib, ig, ir = np.meshgrid(np.arange(n), np.arange(n), np.arange(n), indexing="ij")
    grid = np.stack([ir.ravel(), ig.ravel(), ib.ravel()], axis=-1) / (n - 1)
    direct = fit_params.apply_wheel_grade(grid, truth)
    diff = np.abs(direct - cube["table"].reshape(-1, 3))
    assert diff.max() < 1e-5, f"model/builder mismatch {diff.max():.3e}"


def test_identity_fit_is_a_no_op():
    np = _np()
    scene = _scene(0)
    report = fit_params.fit_wheel_grade(scene, scene, seed=0)
    params = report["params"]
    for wheel in fit_params.WHEELS:
        assert params[f"{wheel}_saturation"] == 0
        assert params[f"{wheel}_luminance"] == 0
        assert params[f"{wheel}_hue"] == 0
    assert params["blending"] in (50, 100)
    out = fit_params.apply_wheel_grade(scene, params)
    assert np.abs(out - scene).max() < 1e-12
    assert report["fit"]["heldout"]["mean_delta_E_OK"] == 0.0


@pytest.mark.parametrize("label", sorted(GRADES))
def test_pure_parametric_grade_round_trip(label, tmp_path, monkeypatch):
    """Fit a known grade on one scene, then apply the recovered params to a different
    scene and compare with the truth grade. The acceptance is image-space: mean below
    0.01, p95 below 0.03. Parameter recovery is checked only where the pair of scenes
    constrains it; otherwise the fit must say so in identifiability_warnings."""
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    truth = GRADES[label]
    train_scene = _scene(1)
    held_scene = _scene(2)
    target = fit_params.apply_wheel_grade(train_scene, truth)

    report = fit_params.fit_wheel_grade(train_scene, target, seed=0)
    params = report["params"]
    assert report["settings"]["seed"] == 0
    assert set(params) == set(fit_params.PARAM_NAMES)
    for name, (lo, hi) in fit_params.param_bounds().items():
        assert lo <= params[name] <= hi, name

    held_truth = fit_params.apply_wheel_grade(held_scene, truth)
    mean, p95 = _delta(held_scene, held_truth, params)
    assert mean < 0.01, f"{label}: held-out mean {mean:.5f}\n{report}"
    assert p95 < 0.03, f"{label}: held-out p95 {p95:.5f}\n{report}"

    warnings = " | ".join(report["identifiability_warnings"])
    for name in fit_params.PARAM_NAMES:
        diff = (_circular_diff(params[name], truth[name]) if name.endswith("_hue")
                else abs(params[name] - truth[name]))
        if diff > _tolerance(name):
            assert name in warnings, f"{label}: {name} off by {diff:g} without a warning\n{report}"
    json.dumps(report)


def test_fit_is_deterministic():
    truth = GRADES["global"]
    scene = _scene(3)
    target = fit_params.apply_wheel_grade(scene, truth)
    a = fit_params.fit_wheel_grade(scene, target, seed=7, max_samples=2500)
    b = fit_params.fit_wheel_grade(scene, target, seed=7, max_samples=2500)
    assert a == b


def test_fit_reports_clipped_pixels():
    np = _np()
    scene = _scene(4)
    target = fit_params.apply_wheel_grade(scene, GRADES["global"])
    blown = target.copy()
    blown[:8] = 1.0
    report = fit_params.fit_wheel_grade(scene, blown, seed=0, max_samples=2500)
    assert report["fit"]["dropped_clipped_fraction"] > 0.0
    assert report["fit"]["train_pixels"] > 0


def test_fit_rejects_too_few_pixels():
    np = _np()
    px = np.linspace(0.2, 0.8, 12).reshape(4, 3)
    with pytest.raises(PhotoError) as exc:
        fit_params.fit_wheel_grade(px, px, seed=0)
    assert exc.value.code == "INVALID_INPUT"


def test_fit_requires_the_same_shape():
    np = _np()
    with pytest.raises(PhotoError) as exc:
        fit_params.fit_wheel_grade(np.zeros((10, 3)), np.zeros((11, 3)), seed=0)
    assert exc.value.code == "INVALID_REQUEST"
