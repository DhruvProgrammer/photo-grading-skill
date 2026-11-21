"""photo-grading-skill: deterministic photo color grading / photo color correction execution Skill.

It executes typed, validated photo operations — the 3-way color grading (Teal & Orange, etc.),
photo corrections (white balance, exposure, contrast, levels, vibrance, sharpness) and 3D LUT
application — through FFmpeg's photo filters and reports provenance. It does not decide which
color treatment to apply, does not judge a photo "cinematic", does not pick a look or a
correction value, and never runs a shell or an arbitrary filter string.
"""
from __future__ import annotations

SKILL_ID = "photo-grading"
PACKAGE_NAME = "photo-grading-skill"
VERSION = "0.1.0"

CONTRACT_SCHEMA_VERSION = 1
REQUEST_SCHEMA_VERSION = 1
RESPONSE_SCHEMA_VERSION = 1
DOCTOR_SCHEMA_VERSION = 1

__all__ = ["SKILL_ID", "PACKAGE_NAME", "VERSION"]
