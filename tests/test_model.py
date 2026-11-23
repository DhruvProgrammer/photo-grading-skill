import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

from photo_grading.errors import PhotoError  # noqa: E402
from photo_grading.model import (OPERATION_ALIASES, OPERATION_TYPES, PHOTO_HSV_PARAMS,  # noqa: E402
                                  parse_request)

SCHEMA = "photo-grading/request@1"


def _doc(**overrides):
    doc = {
        "schema": SCHEMA,
        "project": {
            "project_id": "grade-1",
            "source": {"source_id": "photo.jpg", "path": "photos/a.jpg"},
            "operations": [{"op_id": "g", "type": "PHOTO_GRADING", "input": "source",
                            "parameters": {"shadows_hue": 190, "shadows_saturation": 25,
                                           "highlights_hue": 40, "highlights_saturation": 20}}],
            "outputs": [{"output_id": "graded", "operation": "op:g", "path": "out/graded.jpg", "format": "jpg"}],
        },
    }
    for k, v in overrides.items():
        doc[k] = v
    return doc


def test_valid_grading_request():
    p = parse_request(_doc())
    assert p.project_id == "grade-1"
    assert p.source.path == "photos/a.jpg"
    assert p.operations[0].type == "PHOTO_GRADING"
    assert p.operations[0].parameters["shadows_hue"] == 190
    assert p.outputs[0].format == "jpg"
    assert p.options["reuse_intermediates"] is True


def test_correction_request_with_white_balance():
    doc = _doc()
    doc["project"]["operations"] = [{"op_id": "c", "type": "PHOTO_CORRECTION", "input": "source",
                                     "parameters": {"white_balance_temperature": 5500, "exposure": 0.5,
                                                    "shadows": -20, "blacks": -5, "sharpness": 30}}]
    doc["project"]["outputs"][0]["operation"] = "op:c"
    p = parse_request(doc)
    assert p.operations[0].type == "PHOTO_CORRECTION"
    assert p.operations[0].parameters["sharpness"] == 30


def test_lut_apply_requires_cube_path():
    doc = _doc()
    doc["project"]["operations"] = [{"op_id": "l", "type": "PHOTO_LUT_APPLY", "input": "source",
                                     "parameters": {"lut_path": "luts/look.cube"}}]
    doc["project"]["outputs"][0]["operation"] = "op:l"
    p = parse_request(doc)
    assert p.operations[0].type == "PHOTO_LUT_APPLY"
    assert p.operations[0].parameters["lut_path"] == "luts/look.cube"

    doc["project"]["operations"][0]["parameters"]["lut_path"] = "luts/look.png"
    with pytest.raises(PhotoError):
        parse_request(doc)


def test_alias_white_balance_resolves_and_restricts():
    for alias in ("WHITE_BALANCE", "PHOTO_WHITE_BALANCE"):
        doc = _doc()
        doc["project"]["operations"] = [{"op_id": "wb", "type": alias, "input": "source",
                                         "parameters": {"white_balance_temperature": 5200, "white_balance_tint": -5}}]
        doc["project"]["outputs"][0]["operation"] = "op:wb"
        p = parse_request(doc)
        assert p.operations[0].type == "PHOTO_CORRECTION"
        assert p.operations[0].parameters["white_balance_temperature"] == 5200
        # restricted: a white-balance op may not carry non-white-balance params
        doc["project"]["operations"][0]["parameters"]["exposure"] = 0.2
        with pytest.raises(PhotoError):
            parse_request(doc)


@pytest.mark.parametrize("mut", [
    {"top": 1},                                            # unknown top-level field
    lambda d: d["project"].update({"extra": 1}),           # unknown project field
    lambda d: d["project"]["operations"][0].update({"f": 1}),
    lambda d: d["project"]["operations"][0]["parameters"].update({"shadows_hue": "red"}),
    lambda d: d["project"]["operations"][0]["parameters"].update({"shadows_hue": 400}),
    lambda d: d["project"]["operations"][0]["parameters"].update({"nope": 1}),
    lambda d: d["project"]["operations"][0].update({"type": "PHOTO_BLUR"}),
    lambda d: d["project"]["operations"][0].update({"type": "FILTER", "command": "rm -rf /"}),
    lambda d: d["project"]["outputs"][0].update({"format": "exe"}),
    lambda d: d["project"]["outputs"][0].update({"path": "out/graded.png"}),  # ext mismatch with jpg
    lambda d: d["project"].update({"outputs": []}),
])
def test_invalid_documents(mut):
    doc = _doc()
    if callable(mut):
        mut(doc)
    else:
        doc.update(mut)
    with pytest.raises(PhotoError):
        parse_request(doc)


def test_forbidden_keys_anywhere():
    for key in ("command", "argv", "shell", "filter", "ffmpeg", "script", "exec"):
        doc = _doc()
        doc["project"]["operations"][0]["parameters"][key] = "x"
        with pytest.raises(PhotoError):
            parse_request(doc)


def test_output_operation_must_be_declared():
    doc = _doc()
    doc["project"]["outputs"][0]["operation"] = "op:nope"
    with pytest.raises(PhotoError):
        parse_request(doc)


def test_operation_types_and_aliases_lists():
    assert OPERATION_TYPES == ("PHOTO_GRADING", "PHOTO_CORRECTION", "PHOTO_LUT_APPLY", "PHOTO_HSV")
    assert OPERATION_ALIASES["WHITE_BALANCE"] == "PHOTO_CORRECTION"


def test_photo_hsv_op():
    doc = {"schema": SCHEMA,
           "project": {"project_id": "h", "source": {"source_id": "s.png", "path": "s.png"},
                       "operations": [{"op_id": "h", "type": "PHOTO_HSV", "input": "source",
                                        "parameters": {"green_hue": 100, "green_luminance": -15,
                                                       "blue_hue": -40, "blue_saturation": 20}}],
                       "outputs": [{"output_id": "o", "operation": "op:h", "path": "o.png", "format": "png"}]}}
    p = parse_request(doc)
    assert p.operations[0].type == "PHOTO_HSV"
    assert p.operations[0].parameters["green_hue"] == 100
    assert p.operations[0].parameters["blue_saturation"] == 20
    # all families present
    for fam in ("red", "orange", "yellow", "green", "cyan", "blue", "magenta"):
        assert f"{fam}_hue" in PHOTO_HSV_PARAMS
    # ranges
    doc["project"]["operations"][0]["parameters"]["green_hue"] = 400
    with pytest.raises(PhotoError):
        parse_request(doc)
    doc["project"]["operations"][0]["parameters"]["green_hue"] = 100
    doc["project"]["operations"][0]["parameters"]["red_luminance"] = 101
    with pytest.raises(PhotoError):
        parse_request(doc)


def test_photo_correction_tone_params():
    doc = {"schema": SCHEMA,
           "project": {"project_id": "c", "source": {"source_id": "s.jpg", "path": "s.jpg"},
                       "operations": [{"op_id": "c", "type": "PHOTO_CORRECTION", "input": "source",
                                        "parameters": {"tone_blacks": 0.2, "tone_shadows": 0.3,
                                                       "tone_midtones": 0.6, "tone_highlights": 0.9,
                                                       "tone_whites": 0.95}}],
                       "outputs": [{"output_id": "o", "operation": "op:c", "path": "o.jpg", "format": "jpg"}]}}
    p = parse_request(doc)
    assert p.operations[0].type == "PHOTO_CORRECTION"
    assert p.operations[0].parameters["tone_blacks"] == 0.2
    assert p.operations[0].parameters["tone_highlights"] == 0.9
    # out of range rejected
    doc["project"]["operations"][0]["parameters"]["tone_blacks"] = 2.5
    with pytest.raises(PhotoError):
        parse_request(doc)
