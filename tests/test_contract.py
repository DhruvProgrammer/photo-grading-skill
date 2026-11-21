import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from photo_grading.contract import skill_contract  # noqa: E402


def test_contract_identity():
    c = skill_contract()
    assert c["schema"] == "photo-grading/contract@1"
    assert c["skill_id"] == "photo-grading"
    assert c["name"] == "photo-grading-skill"
    assert c["deterministic"] is True


def test_contract_operations():
    c = skill_contract()
    types = [o["type"] for o in c["operations"]]
    assert types == ["PHOTO_CORRECTION", "PHOTO_GRADING", "PHOTO_LUT_APPLY"]
    for o in c["operations"]:
        assert o["changes_duration"] is False
        assert o["changes_resolution"] is False


def test_contract_errors_and_aliases():
    c = skill_contract()
    assert c["errors"]["codes"]
    assert c["operation_aliases"][0]["type"] in ("WHITE_BALANCE", "PHOTO_WHITE_BALANCE")


def test_contract_matches_committed_file():
    import json
    import pathlib
    committed = pathlib.Path(__file__).resolve().parents[1] / "contract" / "contract.json"
    if not committed.is_file():
        return  # only meaningful when the file exists
    want = json.loads(committed.read_text(encoding="utf-8"))
    assert want == skill_contract()
