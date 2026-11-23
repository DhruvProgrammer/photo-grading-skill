import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from photo_grading import buildlut  # noqa: E402

LUT_SIZE = 64


def _cube_vals(path):
    lines = Path(path).read_text(encoding="ascii").splitlines()
    assert lines[0].startswith("TITLE")
    assert any(line == f"LUT_3D_SIZE {LUT_SIZE}" for line in lines)
    # data starts after the header (TITLE / LUT_3D_SIZE / DOMAIN_*): take the first
    # run of numeric 3-tuples, so the test does not depend on the exact header length.
    body = []
    for line in lines:
        try:
            vals = tuple(float(v) for v in line.split())
        except ValueError:
            continue
        if len(vals) == 3:
            body.append(vals)
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
    # .cube file order (Adobe spec 1.0): red fastest, blue slowest; i = b*n^2 + g*n + r
    return [((i % n) / (n - 1), ((i // n) % n) / (n - 1), (i // (n * n)) / (n - 1)) for i in range(n ** 3)]


def test_hsv_round_trip_identity():
    """HSV -> RGB -> HSV must be the identity: a wrong sector table in hsv_to_rgb scrambled
    every hue rotation (the false-color bug behind the 1.5/10 audit)."""
    colors = [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0),
              (0.45, 0.68, 0.74), (0.9, 0.6, 0.2), (0.2, 0.6, 0.9), (0.5, 0.5, 0.5)]
    for r, g, b in colors:
        h, s, v = buildlut.rgb_to_hsv(r, g, b)
        out = buildlut.hsv_to_rgb(h, s, v)
        assert all(abs(a - b2) < 1e-6 for a, b2 in zip((r, g, b), out)), (r, g, b, out)


def test_cube_axis_order_red_fastest(tmp_path, monkeypatch):
    """Regression: .cube data lines are red-fastest/blue-slowest. With the old transposed
    order ffmpeg swapped R and B, producing the false-color orange/blue blocks of the
    1.5/10 audit. A blue-only tweak must hit the LAST entry (input 0,0,1); entry n-1 is
    input (1,0,0) and must stay pure red."""
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    vals = _cube_vals(buildlut.build_hsl_lut({"blue": {"hue": 0, "saturation": 0, "luminance": -50}}))
    red = vals[LUT_SIZE - 1]          # input (1,0,0)
    # soft Gaussian family weights leak ~1.7% of blue's tweak onto red; that is intended
    # (no hard mask edges), so assert "essentially untouched", not bit-exact identity.
    assert red[0] > 0.99 and red[1] == 0.0 and red[2] == 0.0, f"entry n-1 is input (1,0,0): {red}"
    blue = vals[LUT_SIZE ** 2]        # input (0,0,1): i = b*n^2 + g*n + r
    assert blue[2] < 0.95, f"input (0,0,1) must be darkened by blue luminance: {blue}"
    assert vals[-1] == (1.0, 1.0, 1.0), "last entry is input (1,1,1): neutral white, untouched"


def test_vibrance_lut_identity_on_neutrals(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    vals = _cube_vals(buildlut.build_vibrance_lut(60))
    for i in (0, LUT_SIZE * LUT_SIZE + LUT_SIZE + 1, LUT_SIZE ** 3 - 1):
        r, g, b = vals[i]
        assert abs(r - g) < 1e-6 and abs(g - b) < 1e-6, "neutral pixels must stay neutral"


def test_vibrance_lut_leaves_low_chroma_texture_alone(tmp_path, monkeypatch):
    """Regression: a 20-30%-saturated boulder was the noisiest area of the 1.5/10 audit.
    Boosting muted texture amplifies compression blocks into visible color mottling, so
    vibrance must be inert below the HSL gate and active on genuinely colorful pixels."""
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    vals = _cube_vals(buildlut.build_vibrance_lut(60))
    n = LUT_SIZE

    def at(r, g, b):
        return vals[b * n * n + g * n + r]

    rock_in = (32 / (n - 1), 36 / (n - 1), 28 / (n - 1))       # ~22% saturation
    rock_out = at(32, 36, 28)
    assert all(abs(a - b) < 1e-6 for a, b in zip(rock_in, rock_out)), "low-chroma texture must not move"

    green_in = (13 / (n - 1), 38 / (n - 1), 6 / (n - 1))      # ~84% saturation
    green_out = at(13, 38, 6)
    sat_in = (green_in[1] - green_in[2]) / green_in[1]
    sat_out = (green_out[1] - green_out[2]) / green_out[1]
    assert sat_out > sat_in + 0.01, (sat_in, sat_out)


def test_wb_lut_identity_at_neutral(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    vals = _cube_vals(buildlut.build_wb_lut(6500, 0))
    assert all(abs(a - b) < 1e-5 for va, vb in zip(vals, _identity_lut_points()) for a, b in zip(va, vb))


def test_wb_lut_warm_moves_red_up_blue_down(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    vals = _cube_vals(buildlut.build_wb_lut(9000, 0))
    assert vals[0] == (0.0, 0.0, 0.0), "black must stay black (no lifted-shadow cast)"
    assert vals[-1][2] < 0.99, "warm must lower blue"
    mid_gray = vals[(LUT_SIZE // 2) * (LUT_SIZE * LUT_SIZE + LUT_SIZE + 1)]
    assert mid_gray[0] > mid_gray[2], "warm must raise red above blue"


def test_wb_lut_black_preserved_at_every_setting(tmp_path, monkeypatch):
    """Regression: the old WB LUT added headroom to every channel, so (0,0,0) became
    (0.04,0,0) and dark pixels turned into red/orange speckles (1.5/10 audit)."""
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    for temp, tint in ((2500, 0), (10000, 0), (6500, 100), (6800, 10)):
        vals = _cube_vals(buildlut.build_wb_lut(temp, tint))
        assert vals[0] == (0.0, 0.0, 0.0), (temp, tint, vals[0])


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
