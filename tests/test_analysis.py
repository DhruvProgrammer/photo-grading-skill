"""Tests for the analysis package: shared colour math, LUT parity with FFmpeg, descriptors."""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("numpy")
pytest.importorskip("PIL")

from photo_grading import critic  # noqa: E402
from photo_grading.analysis import colorspace, descriptors, lutio  # noqa: E402


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


def test_colorspace_is_shared_with_the_critic():
    np = _np()
    rgb = np.array([[0.2, 0.4, 0.3], [0.9, 0.85, 0.8], [0.05, 0.06, 0.07]])
    assert critic.rgb_to_oklab is colorspace.rgb_to_oklab
    assert critic.apply_lut_numpy is lutio.apply_lut_numpy
    back = colorspace.oklab_to_rgb(colorspace.rgb_to_oklab(rgb))
    assert np.max(np.abs(back - rgb)) < 1e-6
    lch = colorspace.oklab_to_oklch(colorspace.rgb_to_oklab(rgb))
    back_lch = colorspace.oklab_to_rgb(colorspace.oklch_to_oklab(lch))
    assert np.max(np.abs(back_lch - rgb)) < 1e-6


def test_identity_lut_interpolation_is_near_identity():
    np = _np()
    lut = critic.build_grade_lut({}, size=17)
    rng = np.random.default_rng(1)
    rgb = rng.uniform(0.05, 0.95, (2000, 3))
    out = lutio.apply_lut_numpy(rgb, lut["table"], lut["size"])
    assert np.abs(out - rgb).mean() < 0.003


def test_descriptors_tone_percentiles():
    d = descriptors.describe(_ramp(128, 32))
    t = d["tone"]
    assert t["p01"] <= t["p05"] <= t["p25"] <= t["p50"] <= t["p75"] <= t["p95"] <= t["p99"]
    assert t["black_point"] == t["p01"]
    assert t["white_rolloff"] == t["p99"]
    assert t["spread_p95_p5"] == pytest.approx(t["p95"] - t["p05"], abs=1e-6)
    for zone in ("shadows", "midtones", "highlights"):
        assert d["zone_tint"][zone]["pixels"] > 0
    assert len(d["saturation"]["hue_sectors"]) == 12
    assert sum(s["share"] for s in d["saturation"]["hue_sectors"]) == pytest.approx(1.0, abs=1e-4)


def test_descriptors_neutral_has_no_tint_or_skin():
    np = _np()
    gray = np.repeat(np.linspace(0.02, 0.98, 500)[:, None], 3, axis=1)
    d = descriptors.describe(gray)
    for zone in ("shadows", "midtones", "highlights"):
        assert d["zone_tint"][zone]["mag"] < 1e-6
    assert d["saturation"]["mean_chroma"] < 1e-6
    assert d["skin"]["detected"] is False
    # A uniform image is one palette colour; the ramp above is five L levels.
    uniform = np.full((100, 3), 0.5)
    assert len(descriptors.describe(uniform)["palette"]["colors"]) == 1


def test_descriptors_zone_tint_hue():
    np = _np()
    # Neutral ramp: the only colour is the split tone, so the measured hue is not mixed with
    # the scene's own cast. The global-mean subtraction still rotates it a little, so assert
    # the direction (closer to teal than orange, and vice versa) rather than an exact angle.
    gray = np.repeat(np.linspace(0.02, 0.98, 500)[:, None], 3, axis=1)
    lab = critic.rgb_to_oklab(gray)
    graded = critic.oklab_to_rgb(critic.apply_grade(lab, {"sh_hue": 200, "sh_amt": 0.06,
                                                         "hi_hue": 55, "hi_amt": 0.06}))
    d = descriptors.describe(graded)
    shadow_hue = d["zone_tint"]["shadows"]["hue"]
    highlight_hue = d["zone_tint"]["highlights"]["hue"]
    assert d["zone_tint"]["shadows"]["mag"] > 0.005
    assert d["zone_tint"]["highlights"]["mag"] > 0.005
    assert critic.hue_diff(shadow_hue, 200) < critic.hue_diff(shadow_hue, 55)
    assert critic.hue_diff(highlight_hue, 55) < critic.hue_diff(highlight_hue, 200)


def test_descriptors_hue_sectors_and_palette_are_deterministic():
    np = _np()
    hues = np.arange(12) * 30.0 + 15.0
    lch = np.stack([np.full(12, 0.6), np.full(12, 0.09), hues], axis=-1)
    rgb = critic.oklab_to_rgb(colorspace.oklch_to_oklab(lch))
    img = np.repeat(rgb, 200, axis=0)
    a = descriptors.describe(img, seed=3)
    b = descriptors.describe(img, seed=3)
    assert a == b
    assert all(s["share"] > 0 for s in a["saturation"]["hue_sectors"])
    palette = a["palette"]
    assert palette["k"] == 5
    assert 1 <= len(palette["colors"]) <= 5
    assert sum(c["weight"] for c in palette["colors"]) == pytest.approx(1.0, abs=1e-4)
    assert all(c["C"] > 0 for c in palette["colors"])
    json.dumps(a)


def test_descriptors_skin_band():
    np = _np()
    skin_rgb = critic.oklab_to_rgb(np.array([0.65, 0.05, 0.05]))
    img = np.tile(skin_rgb, (80, 80, 1)).reshape(-1, 3)
    d = descriptors.describe(img)
    assert d["skin"]["detected"] is True
    assert d["skin"]["share"] > 0.9
    assert d["skin"]["mean_hue"] is not None


def test_numpy_lut_matches_ffmpeg_lut3d(tmp_path):
    np = _np()
    from PIL import Image
    from photo_grading.executor import _lut_arg

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg is not available")

    src_rgb = _ramp(48, 64).reshape(48, 64, 3)
    src = tmp_path / "src.png"
    Image.fromarray(np.round(src_rgb * 255).astype("uint8")).save(src)
    lut = critic.build_grade_lut({"exposure": 0.05, "contrast": 0.1, "saturation": 0.1,
                                  "sh_hue": 200, "sh_amt": 0.03, "hi_hue": 55, "hi_amt": 0.03,
                                  "balance": 0.02}, size=33, directory=str(tmp_path))
    dst = tmp_path / "ffmpeg.png"
    proc = subprocess.run([ffmpeg, "-nostdin", "-y", "-i", str(src), "-vf",
                           f"lut3d=file={_lut_arg(lut['path'])}", "-pix_fmt", "rgb24", str(dst)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode == 0, proc.stderr[-2000:]

    got = np.asarray(Image.open(dst).convert("RGB"), dtype=np.float64).reshape(-1, 3) / 255.0
    # Compare against the same 8-bit source pixels FFmpeg saw, not the float original.
    src8 = np.asarray(Image.open(src).convert("RGB"), dtype=np.float64).reshape(-1, 3) / 255.0
    expected = lutio.apply_lut_numpy(src8, lut["table"], lut["size"])
    delta = np.linalg.norm(critic.rgb_to_oklab(got) - critic.rgb_to_oklab(expected), axis=-1)
    assert float(delta.mean()) < 0.01
    assert float(np.percentile(delta, 95)) < 0.02


def test_analyze_file_includes_descriptors(tmp_path):
    np = _np()
    from PIL import Image

    Image.fromarray(np.round(_ramp(64, 64).reshape(64, 64, 3) * 255).astype("uint8")).save(
        tmp_path / "ramp.png")
    report = critic.analyze_file(str(tmp_path / "ramp.png"), seed=7)
    assert report["kind"] == "analyze"
    assert report["descriptors"]["settings"]["seed"] == 7
    assert report["descriptors"]["tone"]["p50"] > 0
    json.dumps(report)
