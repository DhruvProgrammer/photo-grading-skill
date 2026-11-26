"""LUT application and lattice helpers for the analysis package.

`apply_lut_numpy` mirrors FFmpeg's `lut3d`: a .cube table is stored in Adobe Cube order
(red fastest, blue slowest), so the dense array is indexed `[blue, green, red]`, and a
sample is trilinear-interpolated between the eight surrounding nodes.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

from ..errors import PhotoError
from .colorspace import _np

MAX_LUT_BYTES = 10 * 1024 * 1024


def read_cube(path: str, max_bytes: int = MAX_LUT_BYTES) -> Dict[str, Any]:
    """Parse an Adobe Cube LUT into a dense (size, size, size, 3) table in [blue, green, red]
    order, the order `apply_lut_numpy` and FFmpeg's `lut3d` use.

    The parser accepts the full Cube 1.0 header, comments and blank lines. Only the 3D form
    is supported; a 1D LUT, a missing size or a short table is UNSUPPORTED_FORMAT. The file
    is size-checked here as well as by the path policy, so the library is safe on its own.
    """
    np = _np()
    p = Path(path)
    try:
        size_bytes = p.stat().st_size
    except OSError as e:
        raise PhotoError("INVALID_INPUT", f"cannot read LUT: {e}", {"lut_path": str(path)})
    if size_bytes > int(max_bytes):
        raise PhotoError("UNSUPPORTED_FORMAT",
                         f"LUT is larger than {int(max_bytes)} bytes",
                         {"lut_path": str(path), "bytes": int(size_bytes)})
    try:
        text = p.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as e:
        raise PhotoError("INVALID_INPUT", f"cannot read LUT: {e}", {"lut_path": str(path)})

    size: Optional[int] = None
    title: Optional[str] = None
    entries = []
    for raw in text.splitlines():
        s = raw.split("#", 1)[0].strip()
        if not s:
            continue
        if s.startswith("TITLE"):
            title = s[5:].strip() or None
            continue
        m = re.match(r"^LUT_3D_SIZE\s+(\d+)\s*$", s)
        if m:
            size = int(m.group(1))
            continue
        if s.startswith("LUT_") or s.startswith("DOMAIN_"):
            continue
        parts = s.split()
        if len(parts) != 3:
            raise PhotoError("UNSUPPORTED_FORMAT",
                             f"LUT data line has {len(parts)} values, expected 3: {s[:80]!r}",
                             {"lut_path": str(path)})
        try:
            values = tuple(float(v) for v in parts)
        except ValueError:
            raise PhotoError("UNSUPPORTED_FORMAT",
                             f"LUT data line is not numeric: {s[:80]!r}",
                             {"lut_path": str(path)})
        if not all(np.isfinite(v) for v in values):
            raise PhotoError("UNSUPPORTED_FORMAT",
                             f"LUT data line is not finite: {s[:80]!r}",
                             {"lut_path": str(path)})
        entries.append(values)
    if not size:
        raise PhotoError("UNSUPPORTED_FORMAT",
                         f"LUT file is missing a LUT_3D_SIZE header: {path}",
                         {"lut_path": str(path)})
    if not 2 <= size <= 256:
        raise PhotoError("UNSUPPORTED_FORMAT",
                         f"LUT_3D_SIZE must be between 2 and 256, got {size}",
                         {"lut_path": str(path), "size": size})
    expected = size * size * size
    if len(entries) < expected:
        raise PhotoError("UNSUPPORTED_FORMAT",
                         f"LUT file has {len(entries)} entries, expected {expected} "
                         f"(LUT_3D_SIZE {size}): {path}",
                         {"lut_path": str(path), "size": size, "entries": len(entries)})
    table = np.asarray(entries[:expected], dtype=np.float64).reshape(size, size, size, 3)
    return {"path": str(path), "size": size, "title": title, "table": table}


def apply_lut_numpy(rgb, table, size: int):
    """Trilinear interpolation of a .cube table in (blue, green, red) axis order.

    `rgb` is (N, 3) in 0..1, `table` is (size, size, size, 3) indexed [b, g, r], and `size`
    is the grid resolution. The result is the same mapping FFmpeg's `lut3d` applies, up to
    8-bit output rounding and FFmpeg's own interpolation implementation.
    """
    np = _np()
    x = np.clip(np.asarray(rgb, dtype=np.float64), 0.0, 1.0) * (size - 1)
    i0 = np.floor(x).astype(np.int32)
    i1 = np.minimum(i0 + 1, size - 1)
    f = x - i0
    r0, g0, b0 = i0[:, 0], i0[:, 1], i0[:, 2]
    r1, g1, b1 = i1[:, 0], i1[:, 1], i1[:, 2]
    fr, fg, fb = f[:, 0], f[:, 1], f[:, 2]
    c000 = table[b0, g0, r0]
    c001 = table[b0, g0, r1]
    c010 = table[b0, g1, r0]
    c011 = table[b0, g1, r1]
    c100 = table[b1, g0, r0]
    c101 = table[b1, g0, r1]
    c110 = table[b1, g1, r0]
    c111 = table[b1, g1, r1]
    w000 = (1 - fr) * (1 - fg) * (1 - fb)
    w001 = fr * (1 - fg) * (1 - fb)
    w010 = (1 - fr) * fg * (1 - fb)
    w011 = fr * fg * (1 - fb)
    w100 = (1 - fr) * (1 - fg) * fb
    w101 = fr * (1 - fg) * fb
    w110 = (1 - fr) * fg * fb
    w111 = fr * fg * fb
    return (c000 * w000[:, None] + c001 * w001[:, None] + c010 * w010[:, None]
            + c011 * w011[:, None] + c100 * w100[:, None] + c101 * w101[:, None]
            + c110 * w110[:, None] + c111 * w111[:, None])
