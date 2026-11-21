"""Structured error model. Every failure that crosses the Skill boundary is a PhotoError with a
code from ERROR_TABLE; the CLI turns it into {"ok": false, "error": {"code", "message",
"retryable", "details"}}."""
from __future__ import annotations

from typing import Any, Dict, Optional

# code -> (exit code, retryable)
ERROR_TABLE: Dict[str, Any] = {
    "INVALID_REQUEST": (2, False),       # document shape / unknown fields / bad types
    "INVALID_INPUT": (3, False),         # input missing, unreadable, not a photo, or not a regular file
    "PATH_NOT_ALLOWED": (4, False),      # input/LUT outside allowed roots, output outside workspace, traversal, symlink escape
    "UNSUPPORTED_OPERATION": (5, False), # operation type not implemented by this skill
    "UNSUPPORTED_FORMAT": (6, False),    # output format not in the contract, extension mismatch, LUT format unsupported
    "DEPENDENCY_ERROR": (8, False),      # duplicate op id, missing input reference, unreachable output
    "MISSING_INPUT": (9, False),         # operation references an input that does not exist
    "OUTPUT_ERROR": (10, False),         # output could not be written, is empty, collides with input, exists
    "VALIDATION_ERROR": (11, False),     # output written but failed post-validation (no photo stream, geometry changed)
    "TOOL_ERROR": (12, True),            # ffmpeg / ffprobe failed, timed out, or unavailable
    "CANCELLED": (13, True),             # interrupted by signal
    "INTERNAL_ERROR": (14, False),       # a bug in this skill
}
ERROR_CODES = tuple(ERROR_TABLE)
EXIT_CODES = {code: ERROR_TABLE[code][0] for code in ERROR_CODES}


class PhotoError(Exception):
    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None, retryable: Optional[bool] = None):
        if code not in ERROR_TABLE:
            raise ValueError(f"unknown error code {code!r}")
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = dict(details or {})
        self.retryable = ERROR_TABLE[code][1] if retryable is None else bool(retryable)

    def to_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "message": self.message, "retryable": self.retryable, "details": self.details}

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.code]


# Alias so existing callers/tests of the video skill read naturally
ColorError = PhotoError
