"""Tests for transcript-derived tips implemented in the skill (from the video review):
- PHOTO_GRADING.strength: the overall grade dial (effective blend = blending/100 * strength).
- PHOTO_LUT_APPLY.strength: scale a user LUT toward identity via scale_lut_strength.
- PHOTO_CORRECTION.grain: film grain via the noise filter.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from photo_grading import buildlut, model  # noqa: E402

LUT_SIZE = 64


def _lut_values(path):
    lines = open(path, encoding="ascii").read().splitlines()
    return [tuple(map(float, l.split())) for l in lines[3:]]


def _identity_lut_points(n=LUT_SIZE):
    # identity LUT: entry i == (r, g, b) of point i; file order is R-slowest/B-fastest:
    # i = r*n^2 + g*n + b, r = i // (n*n), g = (i // n) % n, b = i % n
    return [(i // (n * n) / (n - 1), (i // n) % n / (n - 1), i % n / (n - 1)) for i in range(n ** 3)]


def test_wheel_lut_strength_zero_is_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    wheels = {"shadows": {"hue": 190, "saturation": 40, "luminance": 0},
              "highlights": {"hue": 40, "saturation": 20, "luminance": 0}}
    vals = _lut_values(buildlut.build_wheel_lut(wheels, blending=100, strength=0.0))
    want = _identity_lut_points()
    assert all(abs(a - b) < 1e-5 for va, vb in zip(vals, want) for a, b in zip(va, vb))


def test_wheel_lut_strength_dials_down(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    wheels = {"shadows": {"hue": 190, "saturation": 40, "luminance": 0},
              "highlights": {"hue": 40, "saturation": 20, "luminance": 0}}
    full = _lut_values(buildlut.build_wheel_lut(wheels, blending=100, strength=1.0))
    half = _lut_values(buildlut.build_wheel_lut(wheels, blending=100, strength=0.5))
    none = _lut_values(buildlut.build_wheel_lut(wheels, blending=100, strength=0.0))
    assert full != half != none, "different strengths must produce different LUTs"


def test_scale_lut_strength_scales_toward_identity(tmp_path):
    src = buildlut.build_wheel_lut({"shadows": {"hue": 190, "saturation": 40, "luminance": 0},
                                    "highlights": {"hue": 40, "saturation": 20, "luminance": 0}}, blending=100, strength=1.0)
    vals_src = _lut_values(src)
    identity = _identity_lut_points()
    assert any(abs(a - b) > 1e-5 for va, vb in zip(vals_src, identity) for a, b in zip(va, vb)), "source should differ from identity"
    scaled = buildlut.scale_lut_strength(src, 0.5, str(tmp_path))
    vals_scaled = _lut_values(scaled)
    assert any(a != b for va, vb in zip(vals_src, vals_scaled) for a, b in zip(va, vb)), "scaled LUT differs from source"
    scaled0 = buildlut.scale_lut_strength(src, 0.0, str(tmp_path))
    vals0 = _lut_values(scaled0)
    assert all(abs(a - b) < 1e-5 for va, vb in zip(vals0, identity) for a, b in zip(va, vb)), "strength 0 -> identity"


def test_model_accepts_new_params():
    doc = {"schema": "photo-grading/request@1",
           "project": {"project_id": "t", "source": {"source_id": "s.jpg", "path": "s.jpg"},
                       "operations": [{"op_id": "g", "type": "PHOTO_GRADING", "input": "source",
                                        "parameters": {"strength": 0.5, "shadows_hue": 190}},
                                       {"op_id": "c", "type": "PHOTO_CORRECTION", "input": "op:g",
                                        "parameters": {"grain": 10, "exposure": 0.5}}],
                       "outputs": [{"output_id": "o", "operation": "op:c", "path": "o.jpg", "format": "jpg"}]}}
    p = model.parse_request(doc)
    assert p.operations[0].parameters["strength"] == 0.5
    assert p.operations[1].parameters["grain"] == 10

    # ranges: strength out of range is rejected
    doc2 = {"schema": "photo-grading/request@1",
            "project": {"project_id": "t", "source": {"source_id": "s.jpg", "path": "s.jpg"},
                        "operations": [{"op_id": "g", "type": "PHOTO_GRADING", "input": "source",
                                         "parameters": {"strength": 1.5}}],
                        "outputs": [{"output_id": "o", "operation": "op:g", "path": "o.jpg", "format": "jpg"}]}}
    try:
        model.parse_request(doc2)
        raise AssertionError("strength 1.5 must be rejected")
    except model.PhotoError:
        pass


def test_model_lut_apply_strength_param():
    doc = {"schema": "photo-grading/request@1",
           "project": {"project_id": "t", "source": {"source_id": "s.jpg", "path": "s.jpg"},
                       "operations": [{"op_id": "l", "type": "PHOTO_LUT_APPLY", "input": "source",
                                        "parameters": {"lut_path": "a.cube", "strength": 0.5}}],
                       "outputs": [{"output_id": "o", "operation": "op:l", "path": "o.jpg", "format": "jpg"}]}}
    p = model.parse_request(doc)
    assert p.operations[0].parameters["strength"] == 0.5


def test_executor_grain_filter_emitted():
    from photo_grading.executor import Executor
    from photo_grading.model import ColorOperation
    op = ColorOperation("g", "PHOTO_CORRECTION", "source", {"grain": 10})
    ex = object.__new__(Executor)
    chain = Executor._photo_correction_filter(ex, op)
    assert any("noise=alls=10" in f for f in chain), chain
