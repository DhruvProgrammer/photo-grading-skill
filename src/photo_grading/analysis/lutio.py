"""LUT application and lattice helpers for the analysis package.

`apply_lut_numpy` mirrors FFmpeg's `lut3d`: a .cube table is stored in Adobe Cube order
(red fastest, blue slowest), so the dense array is indexed `[blue, green, red]`, and a
sample is trilinear-interpolated between the eight surrounding nodes.
"""
from __future__ import annotations

from .colorspace import _np


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
