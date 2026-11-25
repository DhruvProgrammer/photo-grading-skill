"""Deterministic critic and optimizer for photo grades.

The caller supplies the target look as *numbers* (see TARGET_FIELDS); this module measures a
photo in OKLab, scores it against that target, and, for `PHOTO_OPTIMIZE`, coordinate-descends
grade parameters that maximize the score. It never decides a look, and it never uses a vision
model: the same image and target always produce the same report.

The loop
--------
    proxy -> apply_grade (OKLab) -> analyze -> score -> coordinate descent

- Everything is measured in OKLab (perceptually uniform: equal steps look like equal colour
  differences, which RGB and HSV do not give).
- Optimization runs on a ~384 px proxy. The winning grade is baked into a 3D .cube LUT and the
  proxy is re-scored through that LUT with numpy trilinear interpolation, so the score reflects
  what ffmpeg's `lut3d` will render; the executor then renders that LUT once at full size.
- Coordinate descent is deterministic: a fixed parameter order, fixed step schedule, no RNG.
  A candidate is accepted only when it raises the score, so the result is never worse than the
  untouched image under the same critic. The executor re-checks the full-size render and falls
  back to an identity LUT if the full render would score below the source.

Metrics (all OBSERVED, never inferred)
--------------------------------------
exposure        median OKLab L, plus per-channel clipping percentages
contrast        p95 - p05 spread of OKLab L
colour cast     mean a/b of near-neutral pixels (gray-world idea); reported, not penalized
colourfulness   Hasler-Suesstrunk M3 on sRGB 0..255 (mean + 0.3 * mean of opponent channels)
look match      tint added in the shadow/highlight quartiles: OKLab hue + magnitude
skin            mean OKLab hue shift of a rough skin-hue mask, tolerated up to ~6 deg
overcooked      mean OKLab distance from the original, penalized past 0.10

Hue in the target is an *OKLab* hue angle, not HSV: 0 deg = red/magenta (+a), 90 deg =
yellow (+b), 180 deg = green (-a), 270 deg = blue (-b). Teal is about 200, orange about 55.

Requires the optional `critic` extra::

    pip install -e ".[critic]"
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .errors import PhotoError

REPORT_SCHEMA = "photo-grading/report@1"

DEFAULT_MAX_PIXELS = 250_000
DEFAULT_PROXY_SIZE = 384
DEFAULT_LUT_SIZE = 33
DEFAULT_ITERATIONS = 40
LUT_SIZES = (17, 33, 65)
MAX_ITERATIONS = 200

TARGET_FIELDS = ("shadow_hue", "highlight_hue", "tint_mag", "colorfulness", "median_L", "spread")
TARGET_RANGES: Dict[str, Tuple[float, float]] = {
    "shadow_hue": (0.0, 360.0),
    "highlight_hue": (0.0, 360.0),
    "tint_mag": (0.0, 0.20),
    "colorfulness": (0.0, 150.0),
    "median_L": (0.0, 1.0),
    "spread": (0.0, 1.0),
}

# Grade parameters. Bounds are deliberately conservative: a photo grade that needs more than
# +-0.25 L of exposure or +-0.6 of chroma scaling is not a grade, it is a rescue.
PARAM_BOUNDS: Dict[str, Tuple[float, float]] = {
    "exposure": (-0.25, 0.25),     # OKLab L offset
    "contrast": (-0.40, 0.60),     # scale around L = 0.5
    "saturation": (-0.50, 0.60),   # scale a/b chroma
    "sh_hue": (0.0, 360.0),        # shadow tint direction (OKLab hue)
    "sh_amt": (0.0, 0.08),         # shadow tint chroma
    "hi_hue": (0.0, 360.0),        # highlight tint direction
    "hi_amt": (0.0, 0.08),         # highlight tint chroma
    "balance": (-0.15, 0.15),      # moves the shadow/highlight zone boundaries
}
PARAM_ORDER = tuple(PARAM_BOUNDS)
IDENTITY: Dict[str, Any] = {"exposure": 0.0, "contrast": 0.0, "saturation": 0.0,
                            "sh_hue": 200.0, "sh_amt": 0.0, "hi_hue": 50.0, "hi_amt": 0.0,
                            "balance": 0.0}

# Starting weights. They are a template, not a law: tune them against real photos you consider
# well graded. Every term is reported with its measured value and the target it missed.
WEIGHTS: Dict[str, float] = {
    "exposure": 40.0, "contrast": 20.0, "clipping": 4.0, "colorfulness": 15.0,
    "shadow_hue": 25.0, "highlight_hue": 25.0, "tint_strength": 20.0,
    "skin": 30.0, "overcooked": 30.0,
}
TOLERANCES: Dict[str, float] = {
    "median_L": 0.25,          # L error that costs the full exposure weight
    "spread": 0.35,            # spread error that costs the full contrast weight
    "clip_pct": 10.0,          # clipped percent that costs the full clipping weight
    "colorfulness": 40.0,      # M3 error that costs the full colourfulness weight
    "tint_eps": 1e-4,          # below this a tint is not measurable
    "tint_floor": 0.02,        # denominator when the target tint is 0 (2 * 0.01 per zone)
    "tint_meaningful": 0.005,  # target tints below this are below the visible floor: treat as no tint
    "skin_deg": 6.0,           # free skin-hue shift
    "skin_scale": 20.0,        # degrees beyond tolerance that costs the full skin weight
    "overcooked": 0.10,        # free mean OKLab distance
    "overcooked_scale": 0.10,  # distance beyond the free limit that costs the full weight
}

# OKLab matrices (Bjorn Ottosson). Linear sRGB -> LMS -> OKLab.
_M1 = ((0.4122214708, 0.5363325363, 0.0514459929),
       (0.2119034982, 0.6806995451, 0.1073969566),
       (0.0883024619, 0.2817188376, 0.6299787005))
_M2 = ((0.2104542553, 0.7936177850, -0.0040720468),
       (1.9779984951, -2.4285922050, 0.4505937099),
       (0.0259040371, 0.7827717662, -0.8086757660))
_MAT_CACHE: Dict[str, Any] = {}


# ---------------------------------------------------------------- dependencies
def _np():
    """Import numpy lazily so the core image operations keep working without the extra."""
    try:
        import numpy as np
    except ImportError as e:  # pragma: no cover - exercised only without the extra
        raise PhotoError("DEPENDENCY_ERROR",
                         "the critic needs numpy; install the optional extra: "
                         "pip install -e \".[critic]\"",
                         {"missing": "numpy", "extra": "critic", "error": str(e)})
    return np


def _pil():
    try:
        from PIL import Image
    except ImportError as e:  # pragma: no cover - exercised only without the extra
        raise PhotoError("DEPENDENCY_ERROR",
                         "the critic needs Pillow; install the optional extra: "
                         "pip install -e \".[critic]\"",
                         {"missing": "Pillow", "extra": "critic", "error": str(e)})
    return Image


def _mats():
    np = _np()
    if "m1" not in _MAT_CACHE:
        _MAT_CACHE["m1"] = np.asarray(_M1, dtype=np.float64)
        _MAT_CACHE["m2"] = np.asarray(_M2, dtype=np.float64)
        _MAT_CACHE["m1i"] = np.linalg.inv(_MAT_CACHE["m1"])
        _MAT_CACHE["m2i"] = np.linalg.inv(_MAT_CACHE["m2"])
    return _MAT_CACHE


# ---------------------------------------------------------------- colour math
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


def hue_deg(a, b):
    np = _np()
    return np.degrees(np.arctan2(b, a)) % 360.0


def hue_diff(h1: float, h2: float) -> float:
    """Smallest circular difference between two hue angles, degrees."""
    return abs((float(h1) - float(h2) + 180.0) % 360.0 - 180.0)


def _smoothstep(edge0, edge1, x):
    np = _np()
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def apply_grade(lab, params: Dict[str, Any]):
    """The 8-parameter grade, applied in OKLab. This is the function the optimizer searches.

    exposure  adds L; contrast scales L around 0.5; saturation scales a/b; the shadow and
    highlight zones (defined by L, moved by `balance`) each add a tint vector
    (amount * cos/sin of an OKLab hue). Identity params leave the image unchanged.
    """
    np = _np()
    lab = np.asarray(lab, dtype=np.float64)
    L = lab[..., 0].copy()
    a = lab[..., 1].copy()
    b = lab[..., 2].copy()
    p = {k: float(params.get(k, IDENTITY[k])) for k in PARAM_ORDER}
    L = L + p["exposure"]
    L = 0.5 + (L - 0.5) * (1.0 + p["contrast"])
    a = a * (1.0 + p["saturation"])
    b = b * (1.0 + p["saturation"])
    bal = p["balance"]
    w_sh = 1.0 - _smoothstep(0.15 + bal, 0.55 + bal, L)
    w_hi = _smoothstep(0.45 + bal, 0.85 + bal, L)
    for w, h, amt in ((w_sh, p["sh_hue"], p["sh_amt"]), (w_hi, p["hi_hue"], p["hi_amt"])):
        if amt:
            rad = math.radians(h)
            a = a + w * amt * math.cos(rad)
            b = b + w * amt * math.sin(rad)
    return np.stack([L, a, b], axis=-1)


# ---------------------------------------------------------------- target look
def normalize_target(target: Any, path: str = "target") -> Dict[str, float]:
    """Validate a caller-supplied target look and return it as floats. Unknown fields are
    rejected: a target is a closed set of numbers, not a place to smuggle in a look name."""
    if not isinstance(target, dict):
        raise PhotoError("INVALID_REQUEST", f"{path} must be an object of numbers", {"path": path})
    unknown = sorted(set(target) - set(TARGET_FIELDS))
    if unknown:
        raise PhotoError("INVALID_REQUEST", f"unknown target field(s) {unknown}", {"path": path, "unknown": unknown})
    missing = [k for k in TARGET_FIELDS if k not in target]
    if missing:
        raise PhotoError("INVALID_REQUEST", f"target is missing {missing}", {"path": path, "missing": missing})
    out: Dict[str, float] = {}
    for k in TARGET_FIELDS:
        v = target[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise PhotoError("INVALID_REQUEST", f"target.{k} must be a number", {"path": f"{path}.{k}", "got": v})
        lo, hi = TARGET_RANGES[k]
        if not math.isfinite(float(v)) or float(v) < lo or float(v) > hi:
            raise PhotoError("INVALID_REQUEST", f"target.{k} must be in [{lo}, {hi}]",
                             {"path": f"{path}.{k}", "got": v})
        out[k] = float(v)
    return out


# ---------------------------------------------------------------- analysis
def colorfulness_m3(rgb) -> float:
    """Hasler & Suesstrunk (2003) M3 colourfulness on sRGB 0..255. Same code every time."""
    np = _np()
    rgb = np.asarray(rgb, dtype=np.float64) * 255.0
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    rg = r - g
    yb = 0.5 * (r + g) - b
    return float(np.hypot(rg.std(), yb.std()) + 0.3 * np.hypot(rg.mean(), yb.mean()))


def _zone_tint(lab, ref_lab, mask) -> Dict[str, Any]:
    np = _np()
    n = int(mask.sum())
    if n < 20:
        return {"hue": 0.0, "mag": 0.0, "pixels": n}
    d = (lab[mask][:, 1:] - ref_lab[mask][:, 1:]).mean(axis=0)
    mag = float(np.hypot(d[0], d[1]))
    return {"hue": round(float(hue_deg(d[0], d[1])), 3) if mag > 1e-9 else 0.0,
            "mag": round(mag, 6), "pixels": n}


def analyze_rgb(rgb, reference=None) -> Dict[str, Any]:
    """Measure a graded sRGB image (N,3 or H,W,3, 0..1) against its original.

    `reference` must contain the same pixels (same shape); it defaults to `rgb`, which is the
    untouched-image baseline (all deltas and tints are then zero)."""
    np = _np()
    rgb = np.asarray(rgb, dtype=np.float64).reshape(-1, 3)
    ref = rgb if reference is None else np.asarray(reference, dtype=np.float64).reshape(-1, 3)
    if ref.shape != rgb.shape:
        raise PhotoError("INVALID_INPUT", "analysis reference has a different pixel count",
                         {"graded_pixels": int(rgb.shape[0]), "reference_pixels": int(ref.shape[0])})
    lab = rgb_to_oklab(rgb)
    ref_lab = rgb_to_oklab(ref)
    L = lab[:, 0]
    ref_L = ref_lab[:, 0]
    p01, p05, p50, p95, p99 = np.percentile(L, [1, 5, 50, 95, 99])
    ref_p25, ref_p75 = np.percentile(ref_L, [25, 75])

    # Colour cast: a gray-world sample of pixels that are near-neutral in the graded image.
    # Reported as a measurement, never penalized: a deliberate tint is a look, not an error.
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    neutral = (chroma < 0.03) & (L > 0.02) & (L < 0.98)
    if int(neutral.sum()) >= max(64, int(rgb.shape[0] * 0.01)):
        cast = lab[neutral][:, 1:].mean(axis=0)
        cast_basis = "neutral"
    else:
        cast = lab[:, 1:].mean(axis=0)
        cast_basis = "all"

    shadow = _zone_tint(lab, ref_lab, ref_L < ref_p25)
    highlight = _zone_tint(lab, ref_lab, ref_L > ref_p75)

    # Rough skin mask in OKLCH: orange-ish hue, moderate chroma, mid-to-light L. It is a
    # heuristic, not a face/skin segmentation model; it is only used to catch a hue shift.
    ref_chroma = np.hypot(ref_lab[:, 1], ref_lab[:, 2])
    ref_hue = hue_deg(ref_lab[:, 1], ref_lab[:, 2])
    skin = ((ref_hue > 35.0) & (ref_hue < 70.0) & (ref_chroma > 0.04) & (ref_chroma < 0.14)
            & (ref_L > 0.40) & (ref_L < 0.92))
    n_skin = int(skin.sum())
    if n_skin >= 50:
        graded_hue = hue_deg(lab[skin, 1], lab[skin, 2])
        deltas = np.abs((graded_hue - ref_hue[skin] + 180.0) % 360.0 - 180.0)
        skin_shift = float(deltas.mean())
    else:
        skin_shift = 0.0

    mean_delta = float(np.linalg.norm(lab - ref_lab, axis=-1).mean())

    return {
        "pixels": int(rgb.shape[0]),
        "median_L": round(float(p50), 6),
        "luma_p01": round(float(p01), 6),
        "luma_p05": round(float(p05), 6),
        "luma_p95": round(float(p95), 6),
        "luma_p99": round(float(p99), 6),
        "spread_p95_p5": round(float(p95 - p05), 6),
        "black_clip_pct": round(float((rgb.min(axis=-1) <= 0.004).mean() * 100.0), 4),
        "white_clip_pct": round(float((rgb.max(axis=-1) >= 0.996).mean() * 100.0), 4),
        "colorfulness_m3": round(colorfulness_m3(rgb), 4),
        "cast_a": round(float(cast[0]), 6),
        "cast_b": round(float(cast[1]), 6),
        "cast_mag": round(float(np.hypot(cast[0], cast[1])), 6),
        "neutral_pct": round(float(neutral.mean() * 100.0), 3),
        "cast_basis": cast_basis,
        "shadow_tint_hue": shadow["hue"],
        "shadow_tint_mag": shadow["mag"],
        "shadow_tint_pixels": shadow["pixels"],
        "highlight_tint_hue": highlight["hue"],
        "highlight_tint_mag": highlight["mag"],
        "highlight_tint_pixels": highlight["pixels"],
        "skin_hue_shift_deg": round(skin_shift, 4),
        "skin_pixels": n_skin,
        "skin_pixels_pct": round(n_skin / rgb.shape[0] * 100.0, 3),
        "mean_delta_oklab": round(mean_delta, 6),
    }


def score_metrics(metrics: Dict[str, Any], target: Dict[str, float]) -> Dict[str, Any]:
    """Score measured metrics against a target look (100 = perfect). Every penalty term is
    returned with the measured value, the target, and the tolerance that sets its scale."""
    t = target
    parts: Dict[str, Dict[str, Any]] = {}

    def add(name: str, penalty: float, measured: Any, wanted: Any, tolerance: float) -> None:
        parts[name] = {"penalty": round(-float(penalty), 4), "measured": measured,
                       "target": wanted, "tolerance": tolerance}

    d = abs(metrics["median_L"] - t["median_L"])
    add("exposure", WEIGHTS["exposure"] * min(d / TOLERANCES["median_L"], 1.0),
        metrics["median_L"], t["median_L"], TOLERANCES["median_L"])

    d = abs(metrics["spread_p95_p5"] - t["spread"])
    add("contrast", WEIGHTS["contrast"] * min(d / TOLERANCES["spread"], 1.0),
        metrics["spread_p95_p5"], t["spread"], TOLERANCES["spread"])

    clip = metrics["black_clip_pct"] + metrics["white_clip_pct"]
    add("clipping", WEIGHTS["clipping"] * min(clip, TOLERANCES["clip_pct"]),
        {"black_pct": metrics["black_clip_pct"], "white_pct": metrics["white_clip_pct"]},
        "no clipping", TOLERANCES["clip_pct"])

    d = abs(metrics["colorfulness_m3"] - t["colorfulness"])
    add("colorfulness", WEIGHTS["colorfulness"] * min(d / TOLERANCES["colorfulness"], 1.0),
        metrics["colorfulness_m3"], t["colorfulness"], TOLERANCES["colorfulness"])

    target_tint = t["tint_mag"] if t["tint_mag"] >= TOLERANCES["tint_meaningful"] else 0.0
    for zone, hue_key, mag_key, weight_key in (
            ("shadow_hue", "shadow_tint_hue", "shadow_tint_mag", "shadow_hue"),
            ("highlight_hue", "highlight_tint_hue", "highlight_tint_mag", "highlight_hue")):
        hue = metrics[hue_key]
        mag = metrics[mag_key]
        if target_tint <= 1e-6:
            # No tint requested: hue is meaningless and tint_strength carries the requirement.
            add(zone, 0.0, {"hue": hue, "mag": mag}, "no tint", 0.0)
        elif mag <= TOLERANCES["tint_eps"]:
            add(zone, WEIGHTS[weight_key], {"hue": None, "mag": mag}, t[zone], 180.0)
        else:
            d = hue_diff(hue, t[zone])
            add(zone, WEIGHTS[weight_key] * d / 180.0, {"hue": hue, "mag": mag}, t[zone], 180.0)

    denom = 2.0 * target_tint if target_tint > 1e-6 else TOLERANCES["tint_floor"]
    tint_err = (abs(metrics["shadow_tint_mag"] - target_tint)
                + abs(metrics["highlight_tint_mag"] - target_tint))
    add("tint_strength", WEIGHTS["tint_strength"] * min(tint_err / denom, 1.0),
        {"shadow": metrics["shadow_tint_mag"], "highlight": metrics["highlight_tint_mag"]},
        target_tint, denom / 2.0)

    over = max(metrics["skin_hue_shift_deg"] - TOLERANCES["skin_deg"], 0.0)
    add("skin", WEIGHTS["skin"] * min(over / TOLERANCES["skin_scale"], 1.0),
        metrics["skin_hue_shift_deg"], TOLERANCES["skin_deg"], TOLERANCES["skin_scale"])

    over = max(metrics["mean_delta_oklab"] - TOLERANCES["overcooked"], 0.0)
    add("overcooked", WEIGHTS["overcooked"] * min(over / TOLERANCES["overcooked_scale"], 1.0),
        metrics["mean_delta_oklab"], TOLERANCES["overcooked"], TOLERANCES["overcooked_scale"])

    total = sum(p["penalty"] for p in parts.values())
    return {"score": round(100.0 + total, 4), "total_penalty": round(total, 4), "parts": parts}


# ---------------------------------------------------------------- image IO
def _open_rgb(path: str):
    Image = _pil()
    np = _np()
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            arr = np.asarray(im, dtype=np.uint8)
    except (OSError, ValueError) as e:
        raise PhotoError("INVALID_INPUT", f"cannot decode image: {path}", {"path": str(path), "error": str(e)})
    if arr.ndim != 3 or arr.shape[2] != 3 or arr.size == 0:
        raise PhotoError("INVALID_INPUT", f"image has no RGB pixels: {path}", {"path": str(path)})
    return arr


def _sample(arr, max_pixels: int, stride: Optional[int] = None):
    np = _np()
    h, w = arr.shape[:2]
    total = h * w
    if stride is None:
        stride = max(1, int(math.ceil(total / max(1, int(max_pixels)))))
    flat = arr.reshape(-1, 3)
    rgb = flat[::stride].astype(np.float64) / 255.0
    meta = {"path": None, "width": int(w), "height": int(h), "stride": int(stride),
            "pixels": int(rgb.shape[0])}
    return rgb, meta


def load_pair(image: str, reference: Optional[str] = None,
              max_pixels: int = DEFAULT_MAX_PIXELS) -> Tuple[Any, Any, Dict[str, Any], Dict[str, Any]]:
    """Load two same-size images with the *same* sampling indices, so every per-pixel delta is
    aligned. Returns (graded_rgb, reference_rgb, image_meta, reference_meta)."""
    arr = _open_rgb(image)
    ref_arr = _open_rgb(reference) if reference else arr
    if arr.shape[:2] != ref_arr.shape[:2]:
        raise PhotoError("INVALID_INPUT", "image and reference must have the same dimensions",
                         {"image": str(image), "reference": str(reference),
                          "image_size": [int(arr.shape[1]), int(arr.shape[0])],
                          "reference_size": [int(ref_arr.shape[1]), int(ref_arr.shape[0])]})
    rgb, meta = _sample(arr, max_pixels)
    ref_rgb, ref_meta = _sample(ref_arr, max_pixels, stride=meta["stride"])
    meta["path"] = str(image)
    ref_meta["path"] = str(reference or image)
    return rgb, ref_rgb, meta, ref_meta


def load_proxy(image: str, size: int = DEFAULT_PROXY_SIZE):
    """Downscale to a proxy whose longest side is `size` (LANCZOS), as sRGB 0..1 (N,3)."""
    Image = _pil()
    np = _np()
    try:
        with Image.open(image) as im:
            im = im.convert("RGB")
            im.thumbnail((int(size), int(size)), Image.LANCZOS)
            arr = np.asarray(im, dtype=np.uint8)
    except (OSError, ValueError) as e:
        raise PhotoError("INVALID_INPUT", f"cannot decode image: {image}", {"path": str(image), "error": str(e)})
    if arr.ndim != 3 or arr.size == 0:
        raise PhotoError("INVALID_INPUT", f"image has no RGB pixels: {image}", {"path": str(image)})
    h, w = arr.shape[:2]
    rgb = arr.reshape(-1, 3).astype(np.float64) / 255.0
    return rgb, {"path": str(image), "width": int(w), "height": int(h), "pixels": int(rgb.shape[0]),
                 "proxy_size": int(size)}


# ---------------------------------------------------------------- LUT path
def build_grade_lut(params: Dict[str, Any], size: int = DEFAULT_LUT_SIZE,
                    directory: Optional[str] = None) -> Dict[str, Any]:
    """Bake the 8-parameter grade into a .cube LUT. Returns the path, size, sha256 and the
    dense table in (blue, green, red) axis order for numpy application."""
    np = _np()
    from .buildlut import write_cube
    n = int(size)
    if n not in LUT_SIZES:
        raise PhotoError("INVALID_REQUEST", f"lut_size must be one of {list(LUT_SIZES)}", {"lut_size": n})
    vals = np.linspace(0.0, 1.0, n, dtype=np.float64)
    ib, ig, ir = np.meshgrid(np.arange(n), np.arange(n), np.arange(n), indexing="ij")
    rgb = np.stack([ir.ravel(), ig.ravel(), ib.ravel()], axis=-1) / (n - 1)
    graded = oklab_to_rgb(apply_grade(rgb_to_oklab(rgb), params))
    lines = [f"{c[0]:.6f} {c[1]:.6f} {c[2]:.6f}" for c in graded]
    path = write_cube("critic_grade", n, "PHOTO_OPTIMIZE_GRADE", lines, directory=directory)
    import hashlib
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    table = graded.reshape(n, n, n, 3)
    return {"path": path, "size": n, "sha256": digest, "table": table,
            "bytes": Path(path).stat().st_size}


def apply_lut_numpy(rgb, table, size: int):
    """Trilinear interpolation of a .cube table in (blue, green, red) axis order. This mirrors
    ffmpeg's lut3d so the proxy score matches the eventual render."""
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


# ---------------------------------------------------------------- optimizer
def _score_params(lab, params: Dict[str, Any], reference_rgb, target: Dict[str, float]):
    graded_rgb = oklab_to_rgb(apply_grade(lab, params))
    metrics = analyze_rgb(graded_rgb, reference_rgb)
    return score_metrics(metrics, target)


def optimize_proxy(rgb, target: Dict[str, float], iterations: int = DEFAULT_ITERATIONS) -> Dict[str, Any]:
    """Deterministic coordinate descent with a shrinking step.

    A candidate is accepted only on a strict improvement over the current best, so the result
    can never be worse than the identity grade under this critic. No randomness is used; the
    parameter order and step schedule are fixed.
    """
    np = _np()
    rgb = np.asarray(rgb, dtype=np.float64).reshape(-1, 3)
    lab = rgb_to_oklab(rgb)
    baseline = _score_params(lab, IDENTITY, rgb, target)
    best = float(baseline["score"])
    params = dict(IDENTITY)
    step = {k: (hi - lo) * 0.2 for k, (lo, hi) in PARAM_BOUNDS.items()}
    history: List[float] = [round(best, 4)]
    evaluations = 1

    def f(q: Dict[str, Any]) -> float:
        return float(_score_params(lab, q, rgb, target)["score"])

    for _ in range(max(1, int(iterations))):
        improved = False
        for k in PARAM_ORDER:
            lo, hi = PARAM_BOUNDS[k]
            for s in (step[k], -step[k]):
                q = dict(params)
                q[k] = (q[k] + s) % 360.0 if k.endswith("hue") else float(min(hi, max(lo, q[k] + s)))
                v = f(q)
                evaluations += 1
                if v > best + 1e-6:
                    params, best, improved = q, v, True
        history.append(round(best, 4))
        if not improved:
            step = {k: v * 0.5 for k, v in step.items()}
            if max(step[k] / (PARAM_BOUNDS[k][1] - PARAM_BOUNDS[k][0]) for k in step) < 0.01:
                break

    improved = best > baseline["score"] + 1e-6
    if not improved:                     # never return a change that did not help
        params, best = dict(IDENTITY), float(baseline["score"])
    final = _score_params(lab, params, rgb, target)
    return {"params": {k: float(params[k]) for k in PARAM_ORDER},
            "improved": bool(improved),
            "baseline": baseline, "best": final,
            "history": history, "evaluations": evaluations,
            "iterations_run": len(history) - 1}


def _public_lut(lut: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in lut.items() if k != "table"}


def analyze_file(image: str, reference: Optional[str] = None,
                 max_pixels: int = DEFAULT_MAX_PIXELS) -> Dict[str, Any]:
    rgb, ref, meta, ref_meta = load_pair(image, reference, max_pixels)
    metrics = analyze_rgb(rgb, ref)
    return {"schema": REPORT_SCHEMA, "ok": True, "kind": "analyze",
            "image": str(image), "reference": str(reference or image),
            "sample": meta, "reference_sample": ref_meta, "metrics": metrics}


def score_file(image: str, target: Any, reference: Optional[str] = None,
               max_pixels: int = DEFAULT_MAX_PIXELS) -> Dict[str, Any]:
    t = normalize_target(target)
    rgb, ref, meta, ref_meta = load_pair(image, reference, max_pixels)
    metrics = analyze_rgb(rgb, ref)
    scored = score_metrics(metrics, t)
    return {"schema": REPORT_SCHEMA, "ok": True, "kind": "score",
            "image": str(image), "reference": str(reference or image),
            "sample": meta, "reference_sample": ref_meta, "target": t,
            "score": scored["score"], "total_penalty": scored["total_penalty"],
            "parts": scored["parts"], "metrics": metrics}


def optimize_file(image: str, target: Any, iterations: int = DEFAULT_ITERATIONS,
                  proxy_size: int = DEFAULT_PROXY_SIZE, lut_size: int = DEFAULT_LUT_SIZE,
                  directory: Optional[str] = None) -> Dict[str, Any]:
    """Run the loop on a proxy, bake the winner, and verify the LUT path.

    Escalation: if the 33^3 LUT scores materially below the direct grade, rebuild at 65^3 and
    keep the better one. Fallback: if even the best LUT scores below the identity LUT, return
    the identity grade (the untouched image) instead of a regression.
    """
    t = normalize_target(target)
    proxy, meta = load_proxy(image, proxy_size)
    result = optimize_proxy(proxy, t, iterations)
    params = result["params"]
    direct_score = float(result["best"]["score"])

    lut = build_grade_lut(params, lut_size, directory)
    lut_metrics = analyze_rgb(apply_lut_numpy(proxy, lut["table"], lut["size"]), proxy)
    lut_scored = score_metrics(lut_metrics, t)
    escalated = False
    if lut_size < max(LUT_SIZES) and lut_scored["score"] < direct_score - 0.5:
        bigger = build_grade_lut(params, max(LUT_SIZES), directory)
        bigger_metrics = analyze_rgb(apply_lut_numpy(proxy, bigger["table"], bigger["size"]), proxy)
        bigger_scored = score_metrics(bigger_metrics, t)
        if bigger_scored["score"] > lut_scored["score"]:
            lut, lut_metrics, lut_scored, escalated = bigger, bigger_metrics, bigger_scored, True

    # Guarantee through the same LUT path: never hand back a worse result than the untouched
    # image (an identity LUT is not bit-identical because of interpolation, so compare it).
    fallback = False
    identity_lut = build_grade_lut(IDENTITY, lut["size"], directory)
    identity_metrics = analyze_rgb(apply_lut_numpy(proxy, identity_lut["table"], identity_lut["size"]), proxy)
    identity_scored = score_metrics(identity_metrics, t)
    if lut_scored["score"] < identity_scored["score"]:
        fallback = True
        params = dict(IDENTITY)
        lut, lut_metrics, lut_scored = identity_lut, identity_metrics, identity_scored

    after = _score_params(rgb_to_oklab(proxy), params, proxy, t)
    direct_final = float(after["score"])
    return {"schema": REPORT_SCHEMA, "ok": True, "kind": "optimize",
            "image": str(image), "reference": str(image),
            "target": t, "proxy": meta,
            "iterations": int(iterations), "evaluations": result["evaluations"],
            "iterations_run": result["iterations_run"],
            "params": {k: float(params[k]) for k in PARAM_ORDER},
            "improved": bool(lut_scored["score"] > identity_scored["score"] + 1e-6),
            "fallback_identity": fallback,
            "score_before": float(identity_scored["score"]),
            "score_after": float(lut_scored["score"]),
            "score_direct": direct_final,
            "history": result["history"],
            "metrics_before": identity_metrics,
            "metrics_after": lut_metrics,
            "parts_before": identity_scored["parts"],
            "parts_after": lut_scored["parts"],
            "lut": {**_public_lut(lut), "escalated": escalated,
                    "delta_vs_direct": round(float(lut_scored["score"] - direct_final), 4)}}


def verify_full_render(source: str, rendered: str, target: Dict[str, float],
                       max_pixels: int = DEFAULT_MAX_PIXELS) -> Dict[str, Any]:
    """Score the full-size render against the source, for the executor's final guarantee."""
    rgb, ref, meta, _ = load_pair(rendered, source, max_pixels)
    before_metrics = analyze_rgb(ref, ref)
    after_metrics = analyze_rgb(rgb, ref)
    before = score_metrics(before_metrics, target)
    after = score_metrics(after_metrics, target)
    return {"sample": meta, "score_before": before["score"], "score_after": after["score"],
            "improved": after["score"] > before["score"] + 1e-6,
            "metrics_before": before_metrics, "metrics_after": after_metrics,
            "parts_after": after["parts"]}
