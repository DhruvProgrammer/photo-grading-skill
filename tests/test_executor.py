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


def test_lut_arg_quotes_windows_absolute_path():
    from photo_grading.executor import _lut_arg
    arg = _lut_arg(r"C:\Users\someone\.photo-grading\grade.cube")
    assert arg.startswith("'") and arg.endswith("'")
    assert "\\:" in arg          # the drive-letter colon is escaped
    assert arg.count("'") == 2


def test_lut_file_value_round_trips_lut_arg():
    from photo_grading.executor import _lut_arg, _lut_file_value
    for p in ("grading_wheels_test.cube", r"C:\Users\someone\.photo-grading\grade.cube"):
        recovered = _lut_file_value("lut3d=file=" + _lut_arg(p))
        assert os.path.normcase(recovered) == os.path.normcase(p)


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


def test_run_project_honors_each_operations_declared_input(tmp_path):
    """Regression: operations form a DAG. The executor used to feed every op the previous
    op's output and ignore op.input, so a second branch from `source` was graded on top of
    the first branch (root cause of the false-color candidates in the 1.5/10 audit)."""
    import shutil
    from pathlib import Path

    from photo_grading.model import parse_request
    from photo_grading.security import PathPolicy

    src = tmp_path / "src.png"
    src.write_bytes(b"src")
    doc = {"schema": "photo-grading/request@1",
           "project": {"project_id": "branches", "source": {"source_id": "s", "path": str(src)},
                       "operations": [
                           {"op_id": "a", "type": "PHOTO_CORRECTION", "input": "source",
                            "parameters": {"exposure": 0.1}},
                           {"op_id": "b", "type": "PHOTO_CORRECTION", "input": "source",
                            "parameters": {"exposure": 0.2}},
                           {"op_id": "c", "type": "PHOTO_CORRECTION", "input": "op:a",
                            "parameters": {"contrast": 10}}],
                       "outputs": [{"output_id": "oa", "operation": "op:a", "path": "oa.png", "format": "png"},
                                   {"output_id": "ob", "operation": "op:b", "path": "ob.png", "format": "png"}]}}
    project = parse_request(doc)

    ex = object.__new__(Executor)
    ex.policy = PathPolicy(str(tmp_path))
    ex.ffmpeg = Path(shutil.which("ffmpeg"))
    ex.ffprobe = Path(shutil.which("ffprobe"))
    ex._cancel = None
    calls = []

    def fake_probe(path):
        p = Path(path)
        return {"path": str(p), "width": 2, "height": 2, "pix_fmt": "rgb24", "codec_name": "png",
                "size": p.stat().st_size, "sha256": "hash-" + p.stem, "n_streams": 1}

    def fake_apply(src_path, dst, op, timeout, reference=None):
        calls.append((op.op_id, Path(src_path).name))
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        Path(dst).write_bytes(b"x")
        return {"output_hash": "hash-" + Path(dst).stem, "operation_id": op.op_id, "type": op.type}

    ex.probe = fake_probe
    ex._apply = fake_apply
    ex._check_reuse = lambda *a, **k: None
    ex._write_stamp = lambda *a, **k: None
    ex.signalstats = lambda p: {}
    ex.run_project(project, reuse=False)

    # a and b both read the source; c reads op:a -- not the previous op's output.
    assert calls == [("a", "src.png"), ("b", "src.png"), ("c", "a.png")], calls
