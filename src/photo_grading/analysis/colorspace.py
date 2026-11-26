"""Colour-space math for the analysis package.

Pure functions over NumPy arrays. NumPy is imported lazily so the core image operations keep
working without the optional `[analysis]` extra.

OKLab uses Bjorn Ottosson's reference matrices: linear sRGB -> LMS -> cube root -> OKLab.
Hue is an angle in the OKLab a/b plane: 0 = red/magenta (+a), 90 = yellow (+b),
180 = green (-a), 270 = blue (-b). It is an absolute angle, not an HSV hue and not the
rotation that a grading wheel applies.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from ..errors import PhotoError

# Linear sRGB -> LMS -> OKLab.
_M1 = ((0.4122214708, 0.5363325363, 0.0514459929),
       (0.2119034982, 0.6806995451, 0.1073969566),
       (0.0883024619, 0.2817188376, 0.6299787005))
_M2 = ((0.2104542553, 0.7936177850, -0.0040720468),
       (1.9779984951, -2.4285922050, 0.4505937099),
       (0.0259040371, 0.7827717662, -0.8086757660))
_MAT_CACHE: Dict[str, Any] = {}


def _np():
    """Import numpy lazily; a missing extra is a DEPENDENCY_ERROR, never a traceback."""
    try:
        import numpy as np
    except ImportError as e:  # pragma: no cover - exercised only without the extra
        raise PhotoError(
            "DEPENDENCY_ERROR",
            "the analysis operations need numpy; install the optional extra: "
            "pip install -e \".[analysis]\" (or \".[critic]\")",
            {"missing": "numpy", "extra": "analysis", "error": str(e)},
        )
    return np


def _mats():
    np = _np()
    if "m1" not in _MAT_CACHE:
        _MAT_CACHE["m1"] = np.asarray(_M1, dtype=np.float64)
        _MAT_CACHE["m2"] = np.asarray(_M2, dtype=np.float64)
        _MAT_CACHE["m1i"] = np.linalg.inv(_MAT_CACHE["m1"])
        _MAT_CACHE["m2i"] = np.linalg.inv(_MAT_CACHE["m2"])
    return _MAT_CACHE


def srgb_to_linear(c):
    np = _np()
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    np = _np()
    c = np.clip(np.asarray(c, dtype=np.float64), 0.0, 1.0)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1.0 / 2.4) - 0.055)


def rgb_to_oklab(rgb):
    """sRGB 0..1 (..., 3) -> OKLab (..., 3)."""
    np = _np()
    m = _mats()
    lms = np.cbrt(srgb_to_linear(rgb) @ m["m1"].T)
    return lms @ m["m2"].T


def oklab_to_rgb(lab):
    """OKLab (..., 3) -> sRGB 0..1 (..., 3), clipped to the display gamut."""
    np = _np()
    m = _mats()
    lms = (np.asarray(lab, dtype=np.float64) @ m["m2i"].T) ** 3
    return np.clip(linear_to_srgb(lms @ m["m1i"].T), 0.0, 1.0)


def oklab_to_oklch(lab):
    """OKLab (..., 3) -> OKLCH (..., 3) = (L, chroma, hue degrees)."""
    np = _np()
    lab = np.asarray(lab, dtype=np.float64)
    C = np.hypot(lab[..., 1], lab[..., 2])
    return np.stack([lab[..., 0], C, hue_deg(lab[..., 1], lab[..., 2])], axis=-1)


def oklch_to_oklab(lch):
    """OKLCH (..., 3) = (L, chroma, hue degrees) -> OKLab (..., 3)."""
    np = _np()
    lch = np.asarray(lch, dtype=np.float64)
    rad = np.radians(lch[..., 2])
    return np.stack([lch[..., 0], lch[..., 1] * np.cos(rad), lch[..., 1] * np.sin(rad)], axis=-1)


def hue_deg(a, b):
    np = _np()
    return np.degrees(np.arctan2(b, a)) % 360.0


def hue_diff(h1: float, h2: float) -> float:
    """Smallest circular difference between two hue angles, degrees."""
    return abs((float(h1) - float(h2) + 180.0) % 360.0 - 180.0)
