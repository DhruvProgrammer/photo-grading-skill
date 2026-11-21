"""Path policy for photo inputs, LUTs and outputs.

- Input: a regular photo file (symlink resolved); if allowed_input_roots is set, it must sit
  under one of them.
- LUT: a regular .cube file (symlink resolved); if allowed_lut_roots is set (default: same as
  allowed_input_roots), it must sit under one.
- Output: inside the workspace, never an existing input file unless overwrite, never outside
  the workspace, no traversal or symlink escapes.
No shell, no user-supplied filter strings: every value that reaches a subprocess argv is a
fixed flag or this skill's own resolved absolute path (same policy as the video skill).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from .errors import PhotoError

WORK_DIR_NAME = ".photo-grading"


def _resolve(path: Path) -> Path:
    try:
        return path.resolve(strict=True)
    except OSError:
        return path.resolve()


def _under(path: Path, roots: List[Path]) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


class PathPolicy:
    def __init__(self, workspace: Optional[str] = None, allowed_input_roots: Optional[List[str]] = None,
                 allowed_lut_roots: Optional[List[str]] = None, overwrite: bool = False):
        self.workspace = Path(workspace or os.getcwd()).resolve()
        # Default policy: inputs and LUTs must live inside the workspace (the caller may widen
        # this with --allowed-input / --allowed-lut).
        if allowed_input_roots is None:
            allowed_input_roots = [str(self.workspace)]
        if allowed_lut_roots is None:
            allowed_lut_roots = allowed_input_roots
        self.allowed_input_roots = [Path(r).resolve() for r in allowed_input_roots]
        self.allowed_lut_roots = [Path(r).resolve() for r in allowed_lut_roots]
        self.overwrite = overwrite

    def _check_allowed(self, path: Path, allowed: Optional[List[Path]], what: str) -> None:
        if allowed and not _under(path, allowed):
            raise PhotoError("PATH_NOT_ALLOWED", f"{what} must be inside {[str(r) for r in allowed]}",
                             {"path": str(path), "roots": [str(r) for r in allowed]})

    def check_input(self, path_str: str, what: str = "input") -> Path:
        path = _resolve(Path(path_str))
        if not path.is_file():
            raise PhotoError("INVALID_INPUT", f"{what} is missing or not a regular file: {path_str}", {"path": path_str})
        self._check_allowed(path, self.allowed_input_roots, what)
        return path

    def check_lut(self, path_str: str) -> Path:
        path = _resolve(Path(path_str))
        if not path.is_file():
            raise PhotoError("INVALID_INPUT", f"LUT is missing or not a regular file: {path_str}", {"path": path_str})
        if path.suffix.lower() != ".cube":
            raise PhotoError("UNSUPPORTED_FORMAT", f"LUT must be a .cube file: {path_str}", {"path": path_str})
        if path.stat().st_size > 10 * 1024 * 1024:
            raise PhotoError("UNSUPPORTED_FORMAT", "LUT is larger than 10 MiB", {"path": path_str})
        self._check_allowed(path, self.allowed_lut_roots, "LUT")
        return path

    def check_output(self, path_str: str, inputs: List[Path]) -> Path:
        if os.path.isabs(path_str) and not _under(Path(path_str), [self.workspace]):
            raise PhotoError("PATH_NOT_ALLOWED", "output must be inside the workspace", {"path": path_str, "workspace": str(self.workspace)})
        path = (self.workspace / path_str) if not os.path.isabs(path_str) else Path(path_str)
        path = _resolve(path)
        if not _under(path, [self.workspace]):
            raise PhotoError("PATH_NOT_ALLOWED", "output must resolve inside the workspace", {"path": path_str})
        if path.exists():
            if path in inputs and not self.overwrite:
                raise PhotoError("OUTPUT_ERROR", f"output collides with an input: {path}", {"path": str(path)})
            if not path.is_file() or path.stat().st_size == 0:
                raise PhotoError("OUTPUT_ERROR", "output path exists and is not a writable file", {"path": str(path)})
            if not self.overwrite:
                raise PhotoError("OUTPUT_ERROR", f"output exists and overwrite was not requested: {path}", {"path": str(path)})
        return path

    def work_dir(self) -> Path:
        return self.workspace / WORK_DIR_NAME
