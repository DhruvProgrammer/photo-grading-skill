"""Generate 3D .cube LUTs for the photo operations.

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

.cube file order is fixed by the Adobe Cube LUT Specification 1.0: **red changes fastest,
blue slowest**. Every builder in this module iterates `_cube_points`, which yields the grid
in exactly that order; writing the grid in the other order makes ffmpeg read the LUT with R
and B transposed (that bug produced false-color orange/blue blocks in the 1.5/10 audit).

All math is stdlib float math (colorsys-like HSV helpers), fully deterministic:
the same values always produce the same LUT bytes.
"""
from __future__ import annotations

import math
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

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


def _cube_points(size: int) -> Iterator[Tuple[float, float, float]]:
    """Yield (r, g, b) in .cube data-line order: red fastest, blue slowest (Adobe spec 1.0).
    This is the single source of truth for LUT ordering; never hand-roll the loops."""
    n = size
    for ib in range(n):
        b = ib / (n - 1)
        for ig in range(n):
            g = ig / (n - 1)
            for ir in range(n):
                yield ir / (n - 1), g, b


def write_cube(prefix: str, size: int, title: str, lines: List[str],
               directory: Optional[str] = None) -> str:
    """Write a full Adobe Cube 1.0 file and return its path.

    The filename carries sha256(content)[:16], so identical parameters produce identical
    filenames on every machine. `directory` places the file explicitly (the critic uses the
    run's work dir); otherwise PHOTO_GRADING_SCRATCH or the cwd is used.
    """
    # Full Adobe Cube 1.0 header: TITLE, LUT_3D_SIZE, DOMAIN_MIN, DOMAIN_MAX. The domain
    # lines are optional for ffmpeg but make the file self-describing and keep every parser
    # (ours included) aligned on where the data starts.
    header = "\n".join([f"TITLE {title}", f"LUT_3D_SIZE {size}",
                        "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0"]) + "\n"
    body = "\n".join(lines) + "\n"
    import hashlib
    digest = hashlib.sha256((header + body).encode("ascii")).hexdigest()[:16]
    base = Path(directory) if directory else Path(os.environ.get("PHOTO_GRADING_SCRATCH", os.getcwd()))
    p = base / f"{prefix}_{digest}.cube"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(header + body, encoding="ascii")
    return str(p)


def _write_cube(prefix: str, size: int, title: str, lines: List[str]) -> str:
    """Backward-compatible internal name; see write_cube."""
    return write_cube(prefix, size, title, lines)


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
    """HSV -> RGB (h degrees, s/v 0..1). Sector table per the standard formula; a wrong table
    scrambles every hue rotation (the original bug behind the psychedelic false-color grades)."""
    i = int(h / 60.0) % 6
    f = (h / 60.0) - int(h / 60.0)
    p = v * (1 - s)
    q = v * (1 - s * f)
    t = v * (1 - s * (1 - f))
    return (v, t, p) if i == 0 else (q, v, p) if i == 1 else (p, v, t) if i == 2 \
        else (p, q, v) if i == 3 else (t, p, v) if i == 4 else (v, p, q)


def _tint(r: float, g: float, b: float, hue: float, saturation: float, luminance: float) -> Tuple[float, float, float]:
    """Rotate a pixel's hue by `hue`, scale saturation by saturation/100 (when nonzero), and
    lift/lower channels by luminance/100 * 0.6. All floats 0..1. With a nonzero saturation the
    tint is made visible even on near-black corners: pixels at v < 0.02 get v = 0.02, so a
    shadow wheel leaves a visible color trace (LRS-like)."""
    h, s, v = rgb_to_hsv(r, g, b)
    if hue or saturation:
        h = (h + hue) % 360.0
        if saturation:
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
    params = {w: {**DEFAULT_WHEEL, **(wheels.get(w) or {})} for w in WHEELS}
    for w in WHEELS:
        for k in WHEEL_PARAMS:
            params[w][k] = float(params[w].get(k) or 0)
    lo, hi = _zone_bounds(balance)
    strength = max(0.0, min(1.0, float(strength)))
    blending = _clamp01((blending or 0) / 100.0 * strength)
    shadows_sat, highlights_sat = params["shadows"]["saturation"], params["highlights"]["saturation"]
    lines: List[str] = []
    for r, g, b in _cube_points(size):
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
        lines.append(f"{out_r:.6f} {out_g:.6f} {out_b:.6f}")
    return _write_cube("grading_wheels", size, "PHOTO_GRADING_WHEELS", lines)


def build_tone_curve_lut(blacks: float = 0.0, shadows: float = 0.15, midtones: float = 0.5,
                         highlights: float = 0.85, whites: float = 1.0, size: int = LUT_SIZE) -> str:
    """Piecewise-linear tone curve LUT on BT.709 luma with anchors
    (L=0 -> blacks, L=0.15 -> shadows, L=0.5 -> midtones, L=0.85 -> highlights, L=1 -> whites).
    Defaults are the identity anchors (blacks=0, shadows=0.15, midtones=0.5, highlights=0.85,
    whites=1). LUT entry (r,g,b) maps to `in + (curve(L) - L)`, preserving the pixel's hue/saturation
    ratios while changing the luminance curve (e.g. `tone_blacks > 0` anchors deep blacks without
    crushing them, `tone_whites < 1` softens the highlight shoulder so bright areas roll off cleanly).
    Writes the LUT; returns the path (the user's LUT is never modified)."""
    anchors = [(0.0, blacks), (0.15, shadows), (0.5, midtones), (0.85, highlights), (1.0, whites)]

    def curve(L: float) -> float:
        if L <= 0.0:
            return _clamp01(anchors[0][1])
        if L >= 1.0:
            return _clamp01(anchors[-1][1])
        for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
            if x0 <= L <= x1:
                t = (L - x0) / (x1 - x0) if x1 > x0 else 0.0
                return _clamp01(y0 + (y1 - y0) * t)
        return anchors[-1][1]

    lines: List[str] = []
    for r, g, b in _cube_points(size):
        L = _luma(r, g, b)
        delta = curve(L) - L
        lines.append(f"{_clamp01(r + delta):.6f} {_clamp01(g + delta):.6f} {_clamp01(b + delta):.6f}")
    return _write_cube("tone_curve", size, "PHOTO_TONE_CURVE", lines)


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        return 1.0 if x >= edge1 else 0.0
    t = (x - edge0) / (edge1 - edge0)
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return t * t * (3.0 - 2.0 * t)


def _soft_delta(v: float, k: float) -> float:
    """Apply a signed adjustment k (-1..1) to a 0..1 channel with soft headroom: lifts approach
    white asymptotically and reductions approach black asymptotically, so a strong adjustment
    can never hard-clip a channel into a flat neon patch."""
    if k >= 0.0:
        return v + (1.0 - v) * k
    return v * (1.0 + k)


# HSL per-color adjustments (user feedback #4: refine greens/blues per color). The families are
# SOFT: each family's influence is a normalized Gaussian over circular hue distance, so
# neighbouring families blend continuously and a hue shift can never create a hard mask edge.
# The first implementation assigned each pixel to its nearest family, which posterized the
# photo into flat orange/blue blocks (audit 1.5/10).
HSV_FAMILIES = ("red", "orange", "yellow", "green", "cyan", "blue", "magenta")
_HSV_CENTER: Dict[str, float] = {"red": 0.0, "orange": 30.0, "yellow": 60.0, "green": 120.0,
                                  "cyan": 180.0, "blue": 240.0, "magenta": 300.0}
_HUE_SIGMA = 42.0          # degrees; overlap between neighbouring families
HUE_SLIDER_DEG = 0.4       # hue slider -100..100 -> -40..40 degrees (Lightroom-like, not 360)
# Hue-selective math is unreliable on low-chroma pixels: their hue swings with every compression
# artifact, so a per-family LUT turns subtle texture (rock, concrete, haze) into mottled patches.
# Gate the whole family blend out below ~30% saturation; above 50% it applies fully.
_SAT_GATE = (0.30, 0.50)


def hue_family_weights(h: float) -> Dict[str, float]:
    """Normalized soft weights of the 7 hue families for hue `h` (degrees). Smooth and periodic;
    sum(weights) == 1, so identical tweaks on every family are the identity."""
    w: Dict[str, float] = {}
    for fam, c in _HSV_CENTER.items():
        d = abs(((h - c + 180.0) % 360.0) - 180.0)
        w[fam] = math.exp(-0.5 * (d / _HUE_SIGMA) ** 2)
    total = sum(w.values())
    return {k: v / total for k, v in w.items()} if total > 0 else {k: 1.0 / len(w) for k in w}


def build_hsl_lut(tweaks: Dict[str, Dict[str, float]], size: int = LUT_SIZE) -> str:
    """Per-hue-family HSL LUT. `tweaks[family]` = {hue, saturation, luminance}, each -100..100
    (hue is a slider: -100..100 maps to -40..40 degrees via HUE_SLIDER_DEG).

    Every pixel gets the weighted blend of its neighbouring families (soft Gaussian weights, no
    hard mask edges) and only pixels with real chroma are touched: the weight fades out below
    30% saturation and reaches full at 50%, so neutral rock, haze and compressed texture cannot
    be pushed into a color cast. Saturation and luminance use soft headroom (`_soft_delta`), so
    a boost can never clip a channel into a flat block. Identity when all tweaks are zero."""
    tweaks = {fam: {k: float(tweaks.get(fam, {}).get(k) or 0) for k in ("hue", "saturation", "luminance")}
              for fam in HSV_FAMILIES}
    active = any(any(t.values()) for t in tweaks.values())
    lines: List[str] = []
    for r, g, b in _cube_points(size):
        if not active:
            lines.append(f"{r:.6f} {g:.6f} {b:.6f}")
            continue
        h, s, v = rgb_to_hsv(r, g, b)
        gate = _smoothstep(_SAT_GATE[0], _SAT_GATE[1], s)
        if gate <= 0.0:
            lines.append(f"{r:.6f} {g:.6f} {b:.6f}")
            continue
        weights = hue_family_weights(h)
        dh = sum(weights[f] * tweaks[f]["hue"] for f in HSV_FAMILIES) * HUE_SLIDER_DEG * gate
        ds = sum(weights[f] * tweaks[f]["saturation"] for f in HSV_FAMILIES) * gate / 100.0
        dl = sum(weights[f] * tweaks[f]["luminance"] for f in HSV_FAMILIES) * gate / 100.0
        h = (h + dh) % 360.0
        s = _soft_delta(s, ds)
        v = _soft_delta(v, dl * 0.6)
        r, g, b = hsv_to_rgb(h, s, v)
        lines.append(f"{_clamp01(r):.6f} {_clamp01(g):.6f} {_clamp01(b):.6f}")
    return _write_cube("hsl", size, "PHOTO_HSL", lines)


def build_wb_lut(temperature: float, tint: float, size: int = LUT_SIZE) -> str:
    """White-balance LUT: per-channel gains, black-preserving.

    temperature 2500..10000 K (6500 neutral): warm lifts R and lowers B, cool the reverse.
    tint -100..100 (+ = magenta): pulls green down; negative pulls it up (green).
    Gains are relative to green, then normalized so the largest gain is exactly 1: no channel
    can clip and, unlike the previous soft-headroom implementation, black stays black. The
    old version added headroom to *every* channel, so (0,0,0) mapped to a lifted red and dark
    pixels turned into false-color red/orange speckles (found in the 1.5/10 audit). Identity
    at 6500 K / tint 0."""
    warmth = max(-1.0, min(1.0, (float(temperature) - 6500.0) / 3500.0))
    t = max(-1.0, min(1.0, float(tint) / 100.0))
    green = max(0.2, 1.0 - 0.15 * t)
    gains = [1.0 + 0.28 * warmth, 1.0, 1.0 - 0.28 * warmth]
    gains[0] /= green          # tint: raise R and B relative to G (magenta), lower them (green)
    gains[2] /= green
    peak = max(gains)
    gains = [g / peak for g in gains]   # largest gain = 1: no channel can clip
    lines: List[str] = []
    for r, g, b in _cube_points(size):
        out = (_clamp01(r * gains[0]), _clamp01(g * gains[1]), _clamp01(b * gains[2]))
        lines.append(f"{out[0]:.6f} {out[1]:.6f} {out[2]:.6f}")
    return _write_cube("wb", size, "PHOTO_WHITE_BALANCE", lines)


def build_vibrance_lut(vibrance: float, size: int = LUT_SIZE) -> str:
    """Vibrance LUT (user feedback: "keep saturation controlled across all channels").

    Unlike a global saturation slider (which scales every channel and clips already-saturated
    pixels into flat neon blocks), vibrance weights the boost by `(1 - s) * sqrt(s)`: zero at
    s=0 (neutral pixels stay neutral) and at s=1 (saturated pixels are protected), maximum
    around s=1/3. The same saturation gate as the HSL LUT also keeps low-chroma texture
    (rock, haze, compression noise) completely untouched: on a small photo, boosting a 20%-
    saturated boulder just amplifies block artifacts. `vibrance` is -100..100; the transform
    uses soft headroom (`_soft_delta`), so it can never clip a channel. Identity at 0."""
    k = max(-1.0, min(1.0, float(vibrance) / 100.0))
    lines: List[str] = []
    for r, g, b in _cube_points(size):
        if k:
            h, s, v = rgb_to_hsv(r, g, b)
            # Same low-chroma gate as the HSL LUT: a near-neutral surface must not pick up
            # amplified chroma noise (the 1.5/10 audit's mottled rock).
            gate = _smoothstep(_SAT_GATE[0], _SAT_GATE[1], s)
            weight = gate * (1.0 - s) * math.sqrt(s) if s > 0.0 else 0.0
            s = _soft_delta(s, k * weight)
            r, g, b = hsv_to_rgb(h, s, v)
        lines.append(f"{_clamp01(r):.6f} {_clamp01(g):.6f} {_clamp01(b):.6f}")
    return _write_cube("vibrance", size, "PHOTO_VIBRANCE", lines)


def scale_lut_strength(lut_path: str, strength: float, work_dir: Optional[str] = None) -> str:
    """Scale a user .cube LUT toward identity: out' = in + strength*(entry - in), where
    `in` is the LUT's input point. Entry i of a LUT of size N maps input point
    (r = i % N, g = (i // N) % N, b = i // (N*N)) — red fastest, blue slowest, the order of
    the Adobe Cube LUT Specification and the order ffmpeg reads.
    Writes the scaled LUT into the run's scratch dir and returns its path (a new file: the
    user's LUT is never modified). strength 0 -> identity; strength 1 -> the LUT unchanged."""
    import hashlib
    lines = Path(lut_path).read_text(encoding="ascii", errors="replace").splitlines()
    header_lines: List[str] = []
    entries: List[Tuple[float, float, float]] = []
    n = 0
    for ln in lines:
        s = ln.strip()
        if not entries:
            # still in the header: collect it verbatim, remember the declared size
            m = re.search(r"^LUT_3D_SIZE\s+(\d+)\s*$", s)
            if m:
                n = int(m.group(1))
            header_lines.append(ln)
            if s and not s.startswith("#") and not s.startswith("TITLE") and \
                    not s.startswith("LUT_") and not s.startswith("DOMAIN_"):
                # first numeric data line: header ends here
                try:
                    vals = tuple(float(v) for v in s.split())
                except ValueError:
                    continue
                if len(vals) == 3:
                    header_lines.pop()
                    entries.append(vals)
            continue
        if not s or s.startswith("#"):
            continue
        try:
            vals = tuple(float(v) for v in s.split())
        except ValueError:
            raise PhotoError("UNSUPPORTED_FORMAT", f"LUT data line is not numeric: {s[:80]!r}", {"lut_path": lut_path})
        if len(vals) != 3:
            raise PhotoError("UNSUPPORTED_FORMAT", f"LUT data line has {len(vals)} values, expected 3: {s[:80]!r}", {"lut_path": lut_path})
        entries.append(vals)
    if not n:
        raise PhotoError("UNSUPPORTED_FORMAT", f"LUT file is missing a LUT_3D_SIZE header: {lut_path}")
    if len(entries) < n * n * n:
        raise PhotoError("UNSUPPORTED_FORMAT", f"LUT file has {len(entries)} entries, expected {n * n * n} (LUT_3D_SIZE {n}): {lut_path}")
    entries = entries[:n * n * n]
    strength = max(0.0, min(1.0, float(strength)))
    denom = max(1, n - 1)
    out: List[Tuple[float, float, float]] = []
    for i, (e_r, e_g, e_b) in enumerate(entries):
        in_r = (i % n) / denom
        in_g = ((i // n) % n) / denom
        in_b = (i // (n * n)) / denom
        out.append((_clamp01(in_r + strength * (e_r - in_r)),
                    _clamp01(in_g + strength * (e_g - in_g)),
                    _clamp01(in_b + strength * (e_b - in_b))))
    header = "\n".join(header_lines) + "\n"
    body = "\n".join(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}" for v in out) + "\n"
    digest = hashlib.sha256((header + body).encode("ascii")).hexdigest()[:16]
    p = Path(work_dir or os.getcwd()) / f"lut_scaled_{digest}.cube"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(header + body, encoding="ascii")
    return str(p)


def build_levels_lut(shadows: float = 0.0, highlights: float = 0.0, blacks: float = 0.0,
                     whites: float = 0.0, size: int = LUT_SIZE) -> str:
    """Generate a LUT from the tonal adjustments of PHOTO_CORRECTION: directional lifts on
    the shadow/highlight bands (shadows, highlights, blacks, whites), each -100..100.

    Semantics (per band, per axis): the band is luma-delimited, as in LRS, but here
    applied to all channels equally so the LUT stays pure-luma-tinted:
    - shadows: weight fades out between luma 0.10 and 0.45; v += shadows/100 * 0.30 * weight
    - highlights: weight fades in between luma 0.55 and 0.90; v += highlights/100 * 0.35 * weight
    - blacks: per-channel fade out between 0.02 and 0.30; v += blacks/100 * 0.35 * weight
    - whites: per-channel fade in between 0.70 and 0.98; v += whites/100 * 0.35 * weight
    Only bands with a nonzero parameter change anything.

    The band edges are *soft* (smoothstep) rather than hard thresholds: a hard threshold puts a
    visible step where the band starts, which reads as posterization/banding after a strong
    adjustment. Lifts and reductions use `_soft_delta` so channels cannot hard-clip."""
    lines: List[str] = []
    for r, g, b in _cube_points(size):
        luma = _luma(r, g, b)
        w_shadows = 1.0 - _smoothstep(0.10, 0.45, luma)
        w_highlights = _smoothstep(0.55, 0.90, luma)
        vals = [r, g, b]
        for i, v in enumerate(vals):
            adj = 0.0
            if shadows:
                adj += shadows / 100.0 * 0.30 * w_shadows
            if highlights:
                adj += highlights / 100.0 * 0.35 * w_highlights
            if blacks:
                adj += blacks / 100.0 * 0.35 * (1.0 - _smoothstep(0.02, 0.30, v))
            if whites:
                adj += whites / 100.0 * 0.35 * _smoothstep(0.70, 0.98, v)
            vals[i] = _soft_delta(v, adj)
        lines.append(f"{vals[0]:.6f} {vals[1]:.6f} {vals[2]:.6f}")
    return _write_cube("correction_levels", size, "PHOTO_CORRECTION_LEVELS", lines)
