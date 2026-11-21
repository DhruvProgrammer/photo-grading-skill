import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

from photo_grading.errors import PhotoError  # noqa: E402
from photo_grading.security import PathPolicy  # noqa: E402


@pytest.fixture
def policy(tmp_path):
    (tmp_path / "photos").mkdir()
    (tmp_path / "photos" / "a.jpg").write_bytes(b"\xff\xd8")
    (tmp_path / "photos" / "luts").mkdir()
    (tmp_path / "photos" / "luts" / "l.cube").write_text("TITLE x")
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere" / "b.jpg").write_bytes(b"\xff\xd8")
    return PathPolicy(workspace=str(tmp_path))


def test_input_inside_workspace_ok(policy, tmp_path):
    p = policy.check_input(str(tmp_path / "photos" / "a.jpg"))
    assert p.name == "a.jpg"


def test_input_outside_workspace_denied(policy, tmp_path):
    outside_dir = tmp_path.parent / f"{tmp_path.name}_outside"
    outside_dir.mkdir(exist_ok=True)
    outside = outside_dir / "b.jpg"
    outside.write_bytes(b"\xff\xd8")
    with pytest.raises(PhotoError):
        policy.check_input(str(outside))
    # widening the allowed roots admits it
    p2 = PathPolicy(workspace=str(tmp_path), allowed_input_roots=[str(tmp_path), str(outside_dir)])
    assert p2.check_input(str(outside)) == outside.resolve()


def test_output_inside_ok(policy, tmp_path):
    p = policy.check_output("photos/out/graded.jpg", [])
    assert p == (tmp_path / "photos" / "out" / "graded.jpg").resolve()


def test_output_outside_workspace_denied(policy):
    with pytest.raises(PhotoError):
        policy.check_output("/etc/passwd", [])


def test_output_existing_needs_overwrite(policy, tmp_path):
    out = tmp_path / "photos" / "a.jpg"
    with pytest.raises(PhotoError):
        policy.check_output("photos/a.jpg", [])
    p = PathPolicy(workspace=str(tmp_path), overwrite=True)
    assert p.check_output("photos/a.jpg", []) == out


def test_output_collision_with_input(policy, tmp_path):
    with pytest.raises(PhotoError):
        policy.check_output("photos/a.jpg", [tmp_path / "photos" / "a.jpg"])


def test_lut_must_be_cube(policy, tmp_path):
    (tmp_path / "photos" / "photos2.txt").write_text("x")
    p = tmp_path / "photos"
    (p / "notcube.jpg").write_bytes(b"")
    with pytest.raises(PhotoError):
        policy.check_lut(str(p / "notcube.jpg"))
