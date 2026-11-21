"""Regenerate contract/contract.json from the code (run `python contract/generate.py`).
The committed contract must be byte-for-byte the output of `photo-grading contract --json`."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from photo_grading.contract import skill_contract  # noqa: E402


def main() -> int:
    doc = skill_contract()
    text = json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    target = Path(__file__).resolve().parents[1] / "contract" / "contract.json"
    target.write_text(text, encoding="utf-8")
    print(f"wrote {target} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
