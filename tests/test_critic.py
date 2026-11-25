"""Tests for the deterministic critic/optimizer (numpy + Pillow)."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("numpy")
pytest.importorskip("PIL")

from photo_grading import critic  # noqa: E402

TARGET = {"shadow_hue": 200, "highlight_hue": 55, "tint_mag": 0.035,
          "colorfulness": 45, "median_L": 0.55, "spread": 0.45}


def _np():
    import numpy as np
    return np


def _ramp(h=64, w=64):
    """A smooth greenish luma ramp with enough shadow and highlight pixels."""
    np = _np()
    y = np.linspace(0.0, 1.0, h)[:, None]
    x = np.linspace(0.0, 1.0, w)[None, :]
    r = 0.10 + 0.62 * y + 0.03 * x
    g = 0.20 + 0.58 * y + 0.02 * x
    b = 0.12 + 0.50 * y + 0.01 * x
    return np.clip(np.stack([r + 0 * x, g + 0 * x, b + 0 * x], axis=-1), 0, 1).reshape(-1, 3)


def test_oklab_round_trip_and_hue_wrap():
    np = _np()
    rgb = np.array([[0.2, 0.4, 0.3], [0.9, 0.85, 0.8], [0.05, 0.06, 0.07], [0.5, 0.5, 0.5]])
    back = critic.oklab_to_rgb(critic.rgb_to_oklab(rgb))
    assert np.max(np.abs(back - rgb)) < 1e-6
    assert critic.hue_diff(359, 1) == pytest.approx(2.0)
    assert critic.hue_diff(10, 350) == pytest.approx(20.0)


def test_analyze_neutral_and_clipping():
    np = _np()
    gray = np.full((100, 3), 0.5)
    m = critic.analyze_rgb(gray)
    assert m["median_L"] == pytest.approx(0.599, abs=0.02)   # OKLab L of sRGB 0.5
    assert abs(m["cast_a"]) < 1e-6 and abs(m["cast_b"]) < 1e-6
    assert m["colorfulness_m3"] == pytest.approx(0.0, abs=1e-6)
    assert m["black_clip_pct"] == 0.0 and m["white_clip_pct"] == 0.0

    blocks = np.zeros((400, 3))
    blocks[:100] = 1.0
    m = critic.analyze_rgb(blocks)
    assert m["white_clip_pct"] == pytest.approx(25.0)
    assert m["black_clip_pct"] == pytest.approx(75.0)


def test_analyze_colorfulness_and_cast():
    np = _np()
    colorful = np.tile(np.array([[0.9, 0.1, 0.1], [0.1, 0.8, 0.2], [0.1, 0.2, 0.9]]), (100, 1))
    m = critic.analyze_rgb(colorful)
    assert m["colorfulness_m3"] > 30
    green = np.tile(np.array([0.2, 0.5, 0.2]), (100, 1))
    m = critic.analyze_rgb(green)
    assert m["cast_a"] < -0.05       # green is -a in OKLab
    assert m["cast_b"] >= 0.0        # and slightly +b (yellowish green)


def test_measure_tint_hue_and_strength():
    np = _np()
    ramp = _ramp(128, 8)
    lab = critic.rgb_to_oklab(ramp)
    graded = critic.oklab_to_rgb(critic.apply_grade(lab, {"sh_hue": 200, "sh_amt": 0.04,
                                                         "hi_hue": 55, "hi_amt": 0.04}))
    m = critic.analyze_rgb(graded, ramp)
    assert m["shadow_tint_mag"] > 0.01
    assert m["highlight_tint_mag"] > 0.01
    assert critic.hue_diff(m["shadow_tint_hue"], 200) < 8
    assert critic.hue_diff(m["highlight_tint_hue"], 55) < 8


def test_skin_mask_and_shift():
    np = _np()
    skin = critic.oklab_to_rgb(np.array([0.65, 0.05, 0.05]))
    img = np.tile(skin, (80, 80, 1)).reshape(-1, 3)
    m = critic.analyze_rgb(img)
    assert m["skin_pixels"] >= 50
    lab = critic.rgb_to_oklab(img)
    graded = critic.oklab_to_rgb(critic.apply_grade(lab, {"hi_hue": 300, "hi_amt": 0.08}))
    shifted = critic.analyze_rgb(graded, img)
    assert shifted["skin_hue_shift_deg"] > 2.0


def test_score_perfect_and_every_penalty_is_reported():
    np = _np()
    m = critic.analyze_rgb(_ramp())
    perfect = {"shadow_hue": 0, "highlight_hue": 0, "tint_mag": 0.0,
               "colorfulness": m["colorfulness_m3"], "median_L": m["median_L"],
               "spread": m["spread_p95_p5"]}
    s = critic.score_metrics(m, perfect)
    assert s["score"] == pytest.approx(100.0)
    assert set(s["parts"]) == {"exposure", "contrast", "clipping", "colorfulness", "shadow_hue",
                               "highlight_hue", "tint_strength", "skin", "overcooked"}
    for part in s["parts"].values():
        assert part["penalty"] == pytest.approx(0.0)
        assert "measured" in part and "target" in part and "tolerance" in part

    wrong = dict(perfect, median_L=perfect["median_L"] + 0.25)
    s = critic.score_metrics(m, wrong)
    assert s["parts"]["exposure"]["penalty"] == pytest.approx(-40.0)
    assert s["score"] < 100.0

    wrong = dict(perfect, tint_mag=0.04)
    s = critic.score_metrics(m, wrong)
    assert s["parts"]["shadow_hue"]["penalty"] < 0.0
    assert s["parts"]["tint_strength"]["penalty"] < 0.0


def test_score_skips_hue_when_target_tint_is_zero():
    np = _np()
    m = critic.analyze_rgb(_ramp())
    target = {"shadow_hue": 200, "highlight_hue": 55, "tint_mag": 0.0,
              "colorfulness": m["colorfulness_m3"], "median_L": m["median_L"],
              "spread": m["spread_p95_p5"]}
    s = critic.score_metrics(m, target)
    assert s["parts"]["shadow_hue"]["penalty"] == 0.0
    assert s["parts"]["highlight_hue"]["penalty"] == 0.0


def test_sub_visible_target_tint_is_treated_as_no_tint():
    """A tint under 0.005 OKLab chroma is below the visible floor; its hue is noise, so the
    critic must not chase it (otherwise the optimizer adds tint just to satisfy a hue)."""
    np = _np()
    m = critic.analyze_rgb(_ramp())
    target = {"shadow_hue": 121.7, "highlight_hue": 46.9, "tint_mag": 0.0016,
              "colorfulness": m["colorfulness_m3"], "median_L": m["median_L"],
              "spread": m["spread_p95_p5"]}
    s = critic.score_metrics(m, target)
    assert s["parts"]["shadow_hue"]["penalty"] == 0.0
    assert s["parts"]["highlight_hue"]["penalty"] == 0.0
    assert s["parts"]["tint_strength"]["penalty"] == 0.0


def test_lingering_skin_and_overcooked_guards():
    np = _np()
    m = critic.analyze_rgb(_ramp())
    base = {"shadow_hue": 0, "highlight_hue": 0, "tint_mag": 0.0,
            "colorfulness": m["colorfulness_m3"], "median_L": m["median_L"],
            "spread": m["spread_p95_p5"]}
    m2 = dict(m, skin_hue_shift_deg=26.0, mean_delta_oklab=0.20)
    s = critic.score_metrics(m2, base)
    assert s["parts"]["skin"]["penalty"] == pytest.approx(-30.0)
    assert s["parts"]["overcooked"]["penalty"] == pytest.approx(-30.0)


def test_lut_trilinear_matches_direct_grade():
    np = _np()
    lut = critic.build_grade_lut({"exposure": 0.06, "contrast": 0.1, "saturation": 0.1,
                                  "sh_hue": 200, "sh_amt": 0.03, "hi_hue": 55, "hi_amt": 0.03,
                                  "balance": 0.02}, size=33)
    rng = np.random.default_rng(7)
    rgb = rng.uniform(0.08, 0.92, size=(4000, 3))
    via_lut = critic.apply_lut_numpy(rgb, lut["table"], lut["size"])
    direct = critic.oklab_to_rgb(critic.apply_grade(critic.rgb_to_oklab(rgb), {
        "exposure": 0.06, "contrast": 0.1, "saturation": 0.1,
        "sh_hue": 200, "sh_amt": 0.03, "hi_hue": 55, "hi_amt": 0.03, "balance": 0.02}))
    err = np.abs(via_lut - direct)
    assert err.mean() < 0.003
    assert err.max() < 0.035       # a 33^3 grid cannot interpolate a curved transform exactly


def test_optimizer_improves_and_is_deterministic():
    proxy = _ramp(64, 64)
    a = critic.optimize_proxy(proxy, TARGET, iterations=12)
    b = critic.optimize_proxy(proxy, TARGET, iterations=12)
    assert a["params"] == b["params"]
    assert a["best"]["score"] == b["best"]["score"]
    assert a["best"]["score"] >= a["baseline"]["score"]
    assert a["improved"] is True
    assert a["best"]["score"] > a["baseline"]["score"] + 1.0
    assert a["best"]["score"] <= 100.0


def test_optimizer_never_worse_when_target_is_already_met():
    proxy = _ramp(48, 48)
    m = critic.analyze_rgb(proxy)
    target = {"shadow_hue": 0, "highlight_hue": 0, "tint_mag": 0.0,
              "colorfulness": m["colorfulness_m3"], "median_L": m["median_L"],
              "spread": m["spread_p95_p5"]}
    r = critic.optimize_proxy(proxy, target, iterations=8)
    assert r["best"]["score"] >= r["baseline"]["score"]
    assert r["params"] == critic.IDENTITY


def test_optimize_file_writes_lut_and_never_regresses(tmp_path):
    from PIL import Image
    Image.fromarray((_ramp(96, 96).reshape(96, 96, 3) * 255).astype("uint8")).save(tmp_path / "ramp.png")
    report = critic.optimize_file(str(tmp_path / "ramp.png"), TARGET, iterations=10,
                                  proxy_size=96, lut_size=17, directory=str(tmp_path))
    assert report["score_after"] >= report["score_before"]
    assert Path(report["lut"]["path"]).is_file()
    assert report["lut"]["size"] == 17
    assert "table" not in report["lut"]
    assert report["params"]["sh_hue"] == pytest.approx(report["params"]["sh_hue"])
    # JSON-serializable (the response is JSON)
    json.dumps(report)


def test_analyze_and_score_file(tmp_path):
    from PIL import Image
    Image.fromarray((_ramp(64, 64).reshape(64, 64, 3) * 255).astype("uint8")).save(tmp_path / "ramp.png")
    a = critic.analyze_file(str(tmp_path / "ramp.png"))
    assert a["kind"] == "analyze" and a["metrics"]["pixels"] > 0
    s = critic.score_file(str(tmp_path / "ramp.png"), TARGET)
    assert s["kind"] == "score" and 0.0 < s["score"] <= 100.0
    assert set(s["parts"]) == set(critic.WEIGHTS)
