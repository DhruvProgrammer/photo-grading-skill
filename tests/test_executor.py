import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from photo_grading.executor import Executor  # noqa: E402
from photo_grading.model import ColorOperation  # noqa: E402


def _executor():
    return object.__new__(Executor)


def test_executor_tone_lut_in_correction_chain(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    op = ColorOperation("c", "PHOTO_CORRECTION", "source", {"tone_blacks": 0.3})
    chain = Executor._photo_correction_filter(_executor(), op)
    assert any("tone_curve" in f for f in chain), chain


def test_executor_no_tone_lut_when_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    op = ColorOperation("c", "PHOTO_CORRECTION", "source", {"exposure": 0.5})
    chain = Executor._photo_correction_filter(_executor(), op)
    assert not any("tone_curve" in f for f in chain), chain


def test_executor_hsl_chain(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    op = ColorOperation("h", "PHOTO_HSV", "source", {"green_hue": 30, "blue_luminance": -15})
    chain = Executor.build_chain(_executor(), op, tmp_path)
    assert any("hsl_" in f for f in chain), chain


def test_executor_hsv_chain_all_families(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_GRADING_SCRATCH", str(tmp_path))
    params = {f"{fam}_hue": 10 for fam in ("red", "orange", "yellow", "green", "cyan", "blue", "magenta")}
    op = ColorOperation("h", "PHOTO_HSV", "source", params)
    chain = Executor.build_chain(_executor(), op, tmp_path)
    assert chain, chain
