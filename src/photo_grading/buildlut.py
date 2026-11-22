"""Generate 3D .cube LUTs for PHOTO_GRADING from the 3-way color grading wheels
(Shadows / Midtones / Highlights + Global).

Zone model (models the semantics of the LRS Color Grading panel):
- Three tonal zones by BT.709 luma: shadows (luma < lo), midtones (between lo and
  hi), highlights (luma > hi). The Balance slider (-100..100) moves the boundaries:
  positive balance widens the midtones (hi rises), negative moves the lo down.
- Each wheel carries (hue 0..360, saturation 0..100, luminance -100..100). A wheel
  tint rotates a pixel's hue by its hue and scales saturation by saturation/100,
  applied within its zone; luminance lifts/lowers the pixel's channels by
  luminance/100 * 0.6. Wheels with no saturation are identity (LRS behavior).
- Global (hue/sat/lum) applies to every pixel after the three-way tint.
- blending (0..100, default 50) mixes the tinted LUT back toward the identity LUT:
  out = tinted*(blending/100) + identity*(1-blending/100), so 0 = no wheels.

All math is stdlib float math (colorsys-like HSV helpers), fully deterministic:
the same wheel values always produce the same LUT bytes.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .errors import PhotoError

WHEEL_PARAMS = ("hue", "saturation", "luminance")
WHEELS = ("shadows", "midtones", "highlights", "global")
DEFAULT_WHEEL: Dict[str, Any] = {"hue": 0, "saturation": 0, "luminance": 0}
DEFAULT_BLENDING = 50
DEFAULT_BALANCE = 0
LUT_SIZE = 64            # points per axis of the generated cube
HUE_DEG = 360

Zone = Tuple[float, float]  # (lo, hi) luma boundaries for shadows / highlights


def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def _clamp255(v: float) -> int:
    return 0 if v < 0 else (255 if v > 255 else round(v))


def _zone_bounds(balance: int) -> Tuple[float, float]:
    """BT.709 luma boundaries (lo, hi) between shadows/midtones/highlights. balance
    in -100..100 moves them apart (-100: teal takes over the midtones) or together."""
    b = _clamp01((balance or 0) / 100.0)
    lo = 0.20 + b * 0.20   # balance>0: lower lo -> shadows shrink, mid grows
    hi = 0.80 - b * 0.20   # balance<0: raise hi -> highlights shrink, mid grows
    return lo, hi


def rgb_to_hsv(r: float, g: float, b: float) -> Tuple[float, float, float]:
    r, g, b = _clamp01(r), _clamp01(g), _clamp01(b)
    mx, mn = max(r, g, b), min(r, g, b)
    v = mx
    s = 0.0 if mx == 0 else (mx - mn) / mx
    if mx == mn:
        h = 0.0
    elif mx == r:
        h = (60.0 * ((g - b) / (mx - mn)) + 360.0) % 360.0
    elif mx == g:
        h = (60.0 * ((b - r) / (mx - mn)) + 120.0) % 360.0
    else:
        h = (60.0 * ((r - g) / (mx - mn)) + 240.0) % 360.0
    return h, s, v


def hsv_to_rgb(h: float, s: float, v: float) -> Tuple[float, float, float]:
    i = int(h / 60.0) % 6
    f = (h / 60.0) - int(h / 60.0)
    p = v * (1 - s)
    q = v * (1 - s * f)
    t = v * (1 - s * (1 - f))
    return (p, t, v) if i == 0 else (v, q, p) if i == 1 else (q, p, v) if i == 2 \
        else (t, v, p) if i == 3 else (p, v, q) if i == 4 else (v, t, q)


def _tint(r: float, g: float, b: float, hue: float, saturation: float, luminance: float) -> Tuple[float, float, float]:
    """Rotate a pixel's hue by `hue` and scale saturation by saturation/100 (a no-op when
    saturation == 0), then lift/lower channels by luminance/100 * 0.6. All floats 0..1.
    With a nonzero saturation the tint is made visible even on near-black corners: pixels
    at v < 0.02 get v = 0.02, so a shadow wheel leaves a visible color trace (LRS-like)."""
    h, s, v = rgb_to_hsv(r, g, b)
    if saturation:
        h = (h + hue) % 360.0
        s = _clamp01(s * (1.0 + saturation / 100.0))
        if v < 0.02:
            v = 0.02
    out = hsv_to_rgb(h, s, v)
    lum = luminance or 0
    if lum:
        out = tuple(_clamp01(c + lum / 100.0 * 0.6) for c in out)
    return out


def _luma(r: float, g: float, b: float) -> float:
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _wheel_zone(luma: float, lo: float, hi: float, shadow_sat: float, highlights_sat: float) -> str:
    """Which zone a pixel is in. When shadow/highlight saturation is 0 the zone is neutral,
    so a pixel that only has midtone tints is untouched (matches LRS: a zero-saturation
    wheel is inactive and midtones carry the tint only where their own wheel has saturation)."""
    if luma < lo:
        return "shadows" if shadow_sat else "midtones"
    if luma > hi:
        return "highlights" if highlights_sat else "midtones"
    return "midtones"


def build_wheel_lut(wheels: Dict[str, Dict[str, Any]], blending: int = DEFAULT_BLENDING,
                    balance: int = DEFAULT_BALANCE, strength: float = 1.0, size: int = LUT_SIZE) -> str:
    """Generate an identity-based 3D LUT from the 3-way wheels; returns the .cube file path.

    `wheels` maps "shadows"/"midtones"/"highlights"/"global" to {hue, saturation, luminance}.
    `strength` (0..1, default 1.0) dials the overall grade down: the effective blend becomes
    `blending/100 * strength` — like a "look dial" ("dial it back"), per the transcript's tip
    that a grade should be scalable to the preferred strength.
    The caller places the file in the run's scratch dir; this builder only computes the bytes.
    Returns the LUT path."""
    import os
    params = {w: {**DEFAULT_WHEEL, **(wheels.get(w) or {})} for w in WHEELS}
    for w in WHEELS:
        for k in WHEEL_PARAMS:
            params[w][k] = float(params[w].get(k) or 0)
    lo, hi = _zone_bounds(balance)
    strength = max(0.0, min(1.0, float(strength)))
    blending = _clamp01((blending or 0) / 100.0 * strength)
    shadows_sat, highlights_sat = params["shadows"]["saturation"], params["highlights"]["saturation"]
    cube: List[str] = ["TITLE PHOTO_GRADING_WHEELS", f"LUT_3D_SIZE {size}", ""]
    n = size
    for ix in range(n):                      # r (slowest: ffmpeg reads the cube with R first)
        for iy in range(n):                  # g
            for iz in range(n):              # b (fastest)
                r, g, b = ix / (n - 1), iy / (n - 1), iz / (n - 1)
                luma = _luma(r, g, b)
                zone = _wheel_zone(luma, lo, hi, shadows_sat, highlights_sat)
                out_r, out_g, out_b = r, g, b
                # zone wheel: shadows / midtones / highlights
                wheel = params[zone]
                if wheel["saturation"]:
                    out_r, out_g, out_b = _tint(out_r, out_g, out_b, wheel["hue"], wheel["saturation"], wheel["luminance"])
                # global wheel
                if params["global"]["saturation"]:
                    out_r, out_g, out_b = _tint(out_r, out_g, out_b, params["global"]["hue"], params["global"]["saturation"],
                                                params["global"]["luminance"])
                if blending < 1.0:
                    out_r = r + (out_r - r) * blending
                    out_g = g + (out_g - g) * blending
                    out_b = b + (out_b - b) * blending
                # .cube data lines are 0-1 floats (ffmpeg reads them as 0..1; ints 0-255 clip)
                cube.append(f"{out_r:.6f} {out_g:.6f} {out_b:.6f}")
    # header/values order: .cube is LUT_3D_SIZE^3 triplets, index = blue + n*green + n*n*red (blue fastest)
    body = "\n".join(cube[3:]) + "\n"
    header = "\n".join(cube[:3]) + "\n"
    import hashlib
    digest = hashlib.sha256((header + body).encode("ascii")).hexdigest()[:16]
    p = Path(os.environ.get("PHOTO_GRADING_SCRATCH", os.getcwd())) / f"grading_wheels_{digest}.cube"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(header + body, encoding="ascii")
    return str(p)


def scale_lut_strength(lut_path: str, strength: float, work_dir: Optional[str] = None) -> str:
    """Scale a user .cube LUT toward identity: out' = in + strength*(entry - in), where
    `in` is the LUT's input point. Entry i of a LUT of size N maps input point
    (r = i // (N*N), g = (i // N) % N, b = i % N) (the R-slowest/B-fastest order ffmpeg reads).
    Writes the scaled LUT into the run's scratch dir and returns its path (a new file: the
    user's LUT is never modified). strength 0 -> identity; strength 1 -> the LUT unchanged."""
    import hashlib
    lines = Path(lut_path).read_text(encoding="ascii").splitlines()
    m = re.search(r"LUT_3D_SIZE (\d+)", lines[1] if len(lines) > 1 else "")
    if not m:
        raise PhotoError("UNSUPPORTED_FORMAT", f"LUT file is missing a LUT_3D_SIZE header: {lut_path}")
    n = int(m.group(1))
    entries = [tuple(map(float, ln.split())) for ln in lines[3:] if ln.strip()]
    if len(entries) != n * n * n:
        raise PhotoError("UNSUPPORTED_FORMAT", f"LUT file has {len(entries)} entries, expected {n * n * n} (LUT_3D_SIZE {n}): {lut_path}")
    strength = max(0.0, min(1.0, float(strength)))
    denom = max(1, n - 1)
    out: List[Tuple[float, float, float]] = []
    for i, (e_r, e_g, e_b) in enumerate(entries):
        in_r = i // (n * n) / denom
        in_g = ((i // n) % n) / denom
        in_b = (i % n) / denom
        out.append((_clamp01(in_r + strength * (e_r - in_r)),
                    _clamp01(in_g + strength * (e_g - in_g)),
                    _clamp01(in_b + strength * (e_b - in_b))))
    header = "\n".join([lines[0], lines[1]] + (lines[2:3] or [])) + "\n"
    body = "\n".join(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}" for v in out) + "\n"
    digest = hashlib.sha256((header + body).encode("ascii")).hexdigest()[:16]
    p = Path(work_dir or os.getcwd()) / f"lut_scaled_{digest}.cube"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(header + body, encoding="ascii")
    return str(p)


def build_levels_lut(shadows: float = 0.0, highlights: float = 0.0, blacks: float = 0.0,
                     whites: float = 0.0, size: int = LUT_SIZE) -> str:
    """Generate a LUT from the tonal adjustments of PHOTO_CORRECTION: directional lifts on
    the shadow/highlight bands (shadows, highlights, blacks, whites), each 0..100.

    Semantics (per band, per axis): the band is luma-delimited, as in LRS, but here
    applied to all channels equally so the LUT stays pure-luma-tinted:
    - shadows (lift/darken, band luma < 0.35): v += shadows/100 * 0.30
    - highlights (lift/darken, band luma > 0.60): v += highlights/100 * 0.35
    - blacks (v < 0.25): v += blacks/100 * 0.35
    - whites (v > 0.75): v += whites/100 * 0.35
    Only bands with a nonzero parameter change anything."""
    import os
    lines = ["TITLE PHOTO_CORRECTION_LEVELS", f"LUT_3D_SIZE {size}", ""]
    n = size
    for iz in range(n):
        for iy in range(n):
            for ix in range(n):
                r, g, b = ix / (n - 1), iy / (n - 1), iz / (n - 1)
                vals = [r, g, b]
                luma = _luma(r, g, b)
                for i, v in enumerate(vals):
                    adj = 0.0
                    if shadows and luma < 0.35:
                        adj += shadows / 100.0 * 0.30
                    if highlights and luma > 0.60:
                        adj += highlights / 100.0 * 0.35
                    if blacks and v < 0.25:
                        adj += blacks / 100.0 * 0.35
                    if whites and v > 0.75:
                        adj += whites / 100.0 * 0.35
                    vals[i] = _clamp01(v + adj)
                lines.append(f"{vals[0]:.6f} {vals[1]:.6f} {vals[2]:.6f}")
    import hashlib
    body = "\n".join(lines[3:]) + "\n"
    digest = hashlib.sha256(("levels" + repr([shadows, highlights, blacks, whites]) + body).encode("ascii")).hexdigest()[:16]
    p = Path(os.environ.get("PHOTO_GRADING_SCRATCH", os.getcwd())) / f"correction_levels_{digest}.cube"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines[:3]) + "\n" + body, encoding="ascii")
    return str(p)
