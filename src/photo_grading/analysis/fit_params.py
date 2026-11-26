"""Parametric fit of the PHOTO_GRADING wheel model (Phase 2).

The model is a vectorized, pure-NumPy port of `buildlut`'s wheel transform: the same
BT.709 zones, the same HSV tint, the same blend. A test pins it to `build_wheel_lut` on a
17^3 grid, so this is the skill's own look, not a lookalike.

Why wheels only: `PHOTO_GRADING` is the operation whose output is a LUT, so a LUT (Mode C)
can be compared with the model directly. `PHOTO_CORRECTION`'s `eq` stage runs in YUV inside
FFmpeg (a neutral gray ramp shifts by 0.1137 for `brightness=0.1`), so it is not modeled
here; correction-stage fitting and the residual LUT belong to the pair-mode phase.

The fit is deterministic: seeded subsampling and hold-out split, a fixed parameter order,
a shrinking step, and accepted improvements only. Nothing here decides whether a look is
good; it measures how close one wheel grade is to another.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .. import model
from ..errors import PhotoError
from .colorspace import _np, hue_deg, rgb_to_oklab

WHEELS = ("shadows", "midtones", "highlights", "global")
WHEEL_KEYS = ("hue", "saturation", "luminance")
PARAM_NAMES = tuple(f"{w}_{k}" for w in WHEELS for k in WHEEL_KEYS) + ("blending", "balance")

IDENTITY: Dict[str, float] = {f"{w}_{k}": 0.0 for w in WHEELS for k in WHEEL_KEYS}
IDENTITY.update({"blending": 50.0, "balance": 0.0})

HUBER_DELTA = 0.02          # delta_E_OK just above the JND; outliers (clipping, local edits) saturate
L2_PENALTY = 1e-5           # pull toward identity; tiny relative to a real fit term
HOLD_OUT = 0.2
MAX_SAMPLES = 8000
CLIP_LO, CLIP_HI = 0.004, 0.996
MAX_SWEEPS = 45
STEP_DECAY = 0.9            # shrink every sweep so the search cannot oscillate forever
CORR_WARNING = 0.95
WEAK_EFFECT = 0.0015        # RMS delta_E_OK for a 5%-of-range step below which a param is weakly identified
RESIDUAL_THRESHOLD = 0.02   # "not expressible as wheels" line


# ------------------------------------------------------------------ bounds
def param_bounds() -> Dict[str, Tuple[float, float]]:
    """Bounds from the request tables (the contract is generated from them)."""
    out: Dict[str, Tuple[float, float]] = {}
    for name in PARAM_NAMES:
        spec = model.PHOTO_GRADING_PARAMS[name]
        out[name] = (float(spec["min"]), float(spec["max"]))
    return out


def _wrap_hue(value: float) -> float:
    return float(value % 360.0)


def _int_param(name: str, value: float) -> int:
    """Clamp and round one parameter to the contract's integer type. Hue 360 is
    normalized to 0: they are the same rotation."""
    if name.endswith("_hue"):
        return int(round(_wrap_hue(value))) % 360
    lo, hi = param_bounds()[name]
    return int(round(min(hi, max(lo, float(value)))))


def identity_params() -> Dict[str, float]:
    return dict(IDENTITY)


def params_to_wheels(params: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """Flat request params -> the `wheels` dict `build_wheel_lut` expects."""
    return {w: {k: float(params.get(f"{w}_{k}", 0.0) or 0.0) for k in WHEEL_KEYS}
            for w in WHEELS}


def request_params(params: Dict[str, Any]) -> Dict[str, int]:
    """Round the fitted floats to the integer values the contract accepts."""
    return {name: _int_param(name, float(params.get(name, IDENTITY[name])))
            for name in PARAM_NAMES}


# ------------------------------------------------------------------ vector math
def rgb_to_hsv(rgb):
    """sRGB (N,3) 0..1 -> (hue degrees, saturation, value), the same branch order as
    buildlut.rgb_to_hsv (mx == r, then mx == g, then mx == b)."""
    np = _np()
    rgb = np.clip(np.asarray(rgb, dtype=np.float64), 0.0, 1.0)
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    d = mx - mn
    safe = np.where(mx > 0.0, mx, 1.0)
    s = np.where(mx > 0.0, d / safe, 0.0)
    h = np.zeros_like(mx)
    nz = d > 0.0
    rm = nz & (mx == r)
    gm = nz & ~rm & (mx == g)
    bm = nz & ~rm & ~gm
    h[rm] = (60.0 * ((g[rm] - b[rm]) / d[rm]) + 360.0) % 360.0
    h[gm] = 60.0 * ((b[gm] - r[gm]) / d[gm]) + 120.0
    h[bm] = 60.0 * ((r[bm] - g[bm]) / d[bm]) + 240.0
    return h, s, mx


def hsv_to_rgb(h, s, v):
    """(hue degrees, saturation, value) -> sRGB (N,3), the standard six-sector table."""
    np = _np()
    h = np.asarray(h, dtype=np.float64)
    s = np.clip(np.asarray(s, dtype=np.float64), 0.0, 1.0)
    v = np.clip(np.asarray(v, dtype=np.float64), 0.0, 1.0)
    sector = np.floor(h / 60.0).astype(np.int64) % 6
    f = h / 60.0 - np.floor(h / 60.0)
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    r = np.select([sector == 0, sector == 1, sector == 2, sector == 3, sector == 4, sector == 5],
                  [v, q, p, p, t, v])
    g = np.select([sector == 0, sector == 1, sector == 2, sector == 3, sector == 4, sector == 5],
                  [t, v, v, q, p, p])
    b = np.select([sector == 0, sector == 1, sector == 2, sector == 3, sector == 4, sector == 5],
                  [p, p, t, v, v, q])
    return np.stack([r, g, b], axis=-1)


def _zone_bounds(balance: float) -> Tuple[float, float]:
    """Same boundaries as buildlut._zone_bounds."""
    b = min(1.0, max(0.0, float(balance) / 100.0))
    return 0.20 + b * 0.20, 0.80 - b * 0.20


def _tint(rgb, hue, saturation, luminance):
    """Same per-pixel tint as buildlut._tint (saturation must be nonzero)."""
    np = _np()
    h, s, v = rgb_to_hsv(rgb)
    h = (h + np.asarray(hue, dtype=np.float64)) % 360.0
    s = np.clip(s * (1.0 + np.asarray(saturation, dtype=np.float64) / 100.0), 0.0, 1.0)
    v = np.where(v < 0.02, 0.02, v)
    out = hsv_to_rgb(h, s, v)
    lum = np.asarray(luminance, dtype=np.float64)
    if np.any(lum):
        if lum.ndim == 0:
            out = np.clip(out + float(lum) / 100.0 * 0.6, 0.0, 1.0)
        else:
            out = np.clip(out + lum[:, None] / 100.0 * 0.6, 0.0, 1.0)
    return out


def apply_wheel_grade(rgb, params: Dict[str, Any]):
    """Apply the PHOTO_GRADING wheel transform to sRGB (N,3 or H,W,3) pixels.

    This mirrors buildlut.build_wheel_lut exactly at full precision: zone by BT.709 luma,
    a zone wheel only when its saturation is nonzero, then the global wheel, then the
    blending mix. `luminance` is ignored on a zero-saturation wheel, as in the builder.
    """
    np = _np()
    shape = np.asarray(rgb).shape
    x = np.clip(np.asarray(rgb, dtype=np.float64).reshape(-1, 3), 0.0, 1.0)
    p = {name: float(params.get(name, IDENTITY[name])) for name in PARAM_NAMES}
    n = x.shape[0]
    luma = 0.2126 * x[:, 0] + 0.7152 * x[:, 1] + 0.0722 * x[:, 2]
    lo, hi = _zone_bounds(p["balance"])
    shadow_sat = p["shadows_saturation"]
    highlight_sat = p["highlights_saturation"]

    zone = np.ones(n, dtype=np.int8)                       # midtones
    shadow = luma < lo
    highlight = luma > hi
    zone[shadow & (shadow_sat != 0.0)] = 0
    zone[highlight & (highlight_sat != 0.0)] = 2

    d_hue = np.select([zone == 0, zone == 1, zone == 2],
                      [p["shadows_hue"], p["midtones_hue"], p["highlights_hue"]])
    d_sat = np.select([zone == 0, zone == 1, zone == 2],
                      [shadow_sat, p["midtones_saturation"], highlight_sat])
    d_lum = np.select([zone == 0, zone == 1, zone == 2],
                      [p["shadows_luminance"], p["midtones_luminance"], p["highlights_luminance"]])

    out = x.copy()
    mask = d_sat != 0.0
    if np.any(mask):
        out[mask] = _tint(x[mask], d_hue[mask], d_sat[mask], d_lum[mask])
    if p["global_saturation"] != 0.0:
        out = _tint(out, p["global_hue"], p["global_saturation"], p["global_luminance"])
    blend = min(1.0, max(0.0, p["blending"] / 100.0))
    if blend < 1.0:
        out = x + (out - x) * blend
    return out.reshape(shape)


# ------------------------------------------------------------------ loss
def _huber(delta):
    np = _np()
    d = np.asarray(delta, dtype=np.float64)
    return np.where(d <= HUBER_DELTA, 0.5 * d * d, HUBER_DELTA * (d - 0.5 * HUBER_DELTA))


def _penalty(params: Dict[str, float]) -> float:
    s = 0.0
    for w in WHEELS:
        s += (params[f"{w}_saturation"] / 100.0) ** 2
        s += (params[f"{w}_luminance"] / 100.0) ** 2
    s += 0.25 * ((params["blending"] - 50.0) / 50.0) ** 2
    s += (params["balance"] / 100.0) ** 2
    return L2_PENALTY * s


def _objective(params: Dict[str, float], before, after_lab) -> float:
    np = _np()
    out = rgb_to_oklab(apply_wheel_grade(before, params))
    return float(_huber(np.linalg.norm(out - after_lab, axis=1)).mean()) + _penalty(params)


# ------------------------------------------------------------------ initialization
def _circular_mean_deg(angles) -> float:
    np = _np()
    a = np.radians(np.asarray(angles, dtype=np.float64))
    return float(np.degrees(np.arctan2(np.sin(a).mean(), np.cos(a).mean())) % 360.0)


def _estimate_wheel(params: Dict[str, float], wheel: str, before_rgb, after_rgb,
                    blend: float) -> None:
    """Rough hue/saturation/luminance of one wheel from the OKLab change in its pixels.

    This is an initialization, not a fit: the wheel hue is an HSV rotation, while the
    measured shift is an OKLab angle, and the two are only related monotonically. It is
    close enough to escape the zero-saturation deadlock (a hue move is a no-op while the
    saturation is 0, so coordinate descent alone cannot start a wheel whose hue is far
    from 0).
    """
    np = _np()
    lab_b = rgb_to_oklab(before_rgb)
    lab_a = rgb_to_oklab(after_rgb)
    cb = np.hypot(lab_b[:, 1], lab_b[:, 2])
    ca = np.hypot(lab_a[:, 1], lab_a[:, 2])
    chromatic = cb > 0.02
    if int(chromatic.sum()) < 10:
        return
    hb = hue_deg(lab_b[chromatic, 1], lab_b[chromatic, 2])
    ha = hue_deg(lab_a[chromatic, 1], lab_a[chromatic, 2])
    shift = _circular_mean_deg(ha - hb)
    ratio = float(ca[chromatic].mean() / max(1e-9, cb[chromatic].mean()))
    sat = min(100.0, max(0.0, (ratio - 1.0) * 100.0))
    params[f"{wheel}_hue"] = shift
    params[f"{wheel}_saturation"] = sat
    d_l = float(np.median(lab_a[:, 0]) - np.median(lab_b[:, 0]))
    if sat > 1.0 and blend > 0.0:
        params[f"{wheel}_luminance"] = min(100.0, max(-100.0, d_l / (0.6 * blend) * 100.0))


def initial_guess(before, after) -> Dict[str, float]:
    """Statistics seed: global wheel first, then the residual in each luma zone.

    Global first matters: if a grade is a single global rotation, the zone wheels see an
    already-explained residual and stay at identity, so the simplest explanation wins
    instead of three identical zone wheels.
    """
    np = _np()
    params = identity_params()
    params["blending"] = 100.0
    x = np.clip(np.asarray(before, dtype=np.float64).reshape(-1, 3), 0.0, 1.0)
    y = np.clip(np.asarray(after, dtype=np.float64).reshape(-1, 3), 0.0, 1.0)
    _estimate_wheel(params, "global", x, y, blend=1.0)
    global_out = apply_wheel_grade(x, params)
    luma = 0.2126 * x[:, 0] + 0.7152 * x[:, 1] + 0.0722 * x[:, 2]
    lo, hi = _zone_bounds(0.0)
    masks = {"shadows": luma < lo,
             "midtones": (luma >= lo) & (luma <= hi),
             "highlights": luma > hi}
    for wheel, mask in masks.items():
        if int(mask.sum()) >= 10:
            _estimate_wheel(params, wheel, global_out[mask], y[mask], blend=1.0)
    return params


# ------------------------------------------------------------------ optimizer
def _prepare(before, after, mask=None, drop_clipped: bool = True):
    np = _np()
    x = np.clip(np.asarray(before, dtype=np.float64).reshape(-1, 3), 0.0, 1.0)
    y = np.clip(np.asarray(after, dtype=np.float64).reshape(-1, 3), 0.0, 1.0)
    if x.shape != y.shape:
        raise PhotoError("INVALID_REQUEST", "before and after must have the same shape",
                         {"before": list(x.shape), "after": list(y.shape)})
    valid = np.ones(x.shape[0], dtype=bool) if mask is None else np.asarray(mask, dtype=bool)
    if drop_clipped:
        clipped = ((x <= CLIP_LO) | (x >= CLIP_HI)).any(axis=1) | \
                  ((y <= CLIP_LO) | (y >= CLIP_HI)).any(axis=1)
        valid &= ~clipped
    dropped = 1.0 - float(valid.sum()) / max(1, x.shape[0])
    return x, y, valid, dropped


def _split(n: int, seed: int, holdout: float, max_samples: int):
    np = _np()
    rng = np.random.default_rng(int(seed))
    take = min(n, int(max_samples))
    picked = np.sort(rng.choice(n, size=take, replace=False))
    if holdout <= 0.0 or take < 50:
        return picked, picked[:0]
    n_hold = max(1, int(round(take * min(0.5, float(holdout)))))
    order = np.sort(rng.choice(take, size=n_hold, replace=False))
    held = picked[order]
    train = np.delete(picked, order)
    return train, held


SEED_HUES = tuple(range(0, 360, 30))
SEED_SATURATIONS = (5.0, 10.0, 20.0, 30.0, 45.0)


def _seed_wheels(params: Dict[str, float], before, after_lab, objective) -> Dict[str, float]:
    """Coarse joint (hue, saturation) seed for every wheel, global first.

    Coordinate descent alone cannot start a wheel: while its saturation is 0 the hue has
    no effect, and at a wrong hue the first saturation step can look like a regression.
    The statistics seed above is biased (an HSV rotation is not an OKLab hue angle), so a
    12-hue x 5-strength grid per wheel is both the escape from that deadlock and a
    correction of the bias. Global first: it applies to every pixel, so the zone wheels
    should explain only what the global wheel leaves behind. 60 evaluations per wheel is
    cheap and deterministic, and an identity target stays at identity because no
    non-identity candidate can beat the zero loss.
    """
    for wheel in ("global",) + WHEELS[:3]:
        best = dict(params)
        best_value = float(objective(best, before, after_lab))
        for hue in SEED_HUES:
            for sat in SEED_SATURATIONS:
                candidate = dict(params)
                candidate[f"{wheel}_hue"] = float(hue)
                candidate[f"{wheel}_saturation"] = sat
                value = float(objective(candidate, before, after_lab))
                if value < best_value - 1e-9:
                    best, best_value = candidate, value
        params = best
    return params


def _fit_values(x, y, idx, params: Dict[str, float], sweeps: int) -> Dict[str, float]:
    np = _np()
    before = x[idx]
    after_lab = rgb_to_oklab(y[idx])
    bounds = param_bounds()
    order = [name for name in PARAM_NAMES]
    # The contract accepts integers only, and a sub-integer saturation is not cosmetic:
    # 0.02 keeps a zone wheel active while 0 routes that zone through the midtones wheel.
    # Optimize in the same integer space the caller will send, so the reported fit is the
    # fit of the returned params rather than of an unroundable float point.
    params = request_params(params)
    steps = {name: max(1.0, 0.2 * (bounds[name][1] - bounds[name][0])) for name in order}
    params = _seed_wheels(params, before, after_lab, _objective)
    best = float(_objective(params, before, after_lab))
    for _ in range(int(sweeps)):
        improved = False
        for name in order:
            step = steps[name]
            if step < 1.0:
                continue
            # Hue and luminance on a zero-saturation wheel have no effect; skip them so
            # the search spends its evaluations on parameters that can move the fit.
            if name.endswith("_hue") or name.endswith("_luminance"):
                wheel = name.rsplit("_", 1)[0]
                if params[f"{wheel}_saturation"] < 1:
                    continue
            for sign in (1.0, -1.0):
                candidate = dict(params)
                candidate[name] = _int_param(name, params[name] + sign * step)
                if candidate[name] == params[name]:
                    continue
                value = float(_objective(candidate, before, after_lab))
                if value < best - 1e-12:
                    params = candidate
                    best = value
                    improved = True
        if not improved:
            for name in order:
                steps[name] *= 0.5
        else:
            for name in order:
                steps[name] *= STEP_DECAY
        if max(steps.values()) < 1.0:
            break
    return params


def _fit_errors(x, y, idx, params: Dict[str, float]) -> Dict[str, float]:
    np = _np()
    if len(idx) == 0:
        return {"mean_delta_E_OK": None, "p95_delta_E_OK": None, "samples": 0}
    out = rgb_to_oklab(apply_wheel_grade(x[idx], params))
    delta = np.linalg.norm(out - rgb_to_oklab(y[idx]), axis=1)
    return {"mean_delta_E_OK": round(float(delta.mean()), 6),
            "p95_delta_E_OK": round(float(np.percentile(delta, 95)), 6),
            "max_delta_E_OK": round(float(delta.max()), 6),
            "samples": int(len(idx))}


def _identifiability(x, idx, params: Dict[str, float]) -> List[str]:
    """Warnings from measurable facts: a parameter at a bound, a parameter that barely
    moves these pixels (so the pair fit cannot pin it down), or two parameters whose
    finite-difference residual directions are almost collinear (|corr| > 0.95)."""
    np = _np()
    warnings: List[str] = []
    bounds = param_bounds()
    for name in PARAM_NAMES:
        lo, hi = bounds[name]
        span = hi - lo
        if span <= 0:
            continue
        wheel = name.rsplit("_", 1)[0] if name not in ("blending", "balance") else None
        if wheel is not None and params[f"{wheel}_saturation"] < 1.0:
            continue  # the wheel is off; none of its parameters can affect the image
        v = params[name]
        if name.endswith("_hue"):
            continue  # circular: 0 and 360 are the same rotation, so no bound is meaningful
        if (v - lo) / span < 0.005:
            warnings.append(f"{name} is at its lower bound ({lo:g})")
        elif (hi - v) / span < 0.005:
            warnings.append(f"{name} is at its upper bound ({hi:g})")
    if len(idx) < 100:
        return warnings
    before = x[idx]
    base = rgb_to_oklab(apply_wheel_grade(before, params))
    cols: List[Any] = []
    names: List[str] = []
    for name in PARAM_NAMES:
        wheel = name.rsplit("_", 1)[0] if name not in ("blending", "balance") else None
        if wheel is not None and params[f"{wheel}_saturation"] < 1.0:
            continue
        lo, hi = bounds[name]
        step = 0.05 * (hi - lo)
        step = max(1.0, round(step))
        candidate = dict(params)
        candidate[name] = _int_param(name, params[name] + step)
        if candidate[name] == params[name]:
            continue
        moved = rgb_to_oklab(apply_wheel_grade(before, candidate)) - base
        effect = float(np.sqrt((moved ** 2).sum(axis=1).mean()))
        if effect < 1e-9:
            continue  # this parameter cannot move the image from the current point
        if effect < WEAK_EFFECT:
            warnings.append(f"{name} changes these pixels only weakly "
                            f"(RMS delta_E_OK {effect:.4f} for a {step:g} step); "
                            "its value is not well identified")
        cols.append(moved.reshape(-1))
        names.append(name)
    if len(cols) < 2:
        return warnings
    j = np.stack(cols, axis=1)
    jtj = j.T @ j
    diag = np.sqrt(np.maximum(np.diag(jtj), 1e-18))
    corr = jtj / np.outer(diag, diag)
    seen = set()
    for i in range(len(names)):
        for k in range(i + 1, len(names)):
            c = float(corr[i, k])
            if abs(c) >= CORR_WARNING and np.isfinite(c):
                pair = tuple(sorted((names[i], names[k])))
                if pair not in seen:
                    seen.add(pair)
                    warnings.append(f"{pair[0]} and {pair[1]} are correlated "
                                    f"(|corr| {abs(c):.2f})")
    return warnings


def fit_wheel_grade(before, after, *, seed: int = 0, max_samples: int = MAX_SAMPLES,
                    holdout: float = HOLD_OUT, sweeps: int = MAX_SWEEPS,
                    drop_clipped: bool = True,
                    initial: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fit PHOTO_GRADING wheel params to an aligned before/after pair.

    Returns integer request params, train/held-out delta_E_OK, the dropped clipped
    fraction, and identifiability warnings. The reported fit is computed with the
    rounded integer params, i.e. the values a caller would actually send.
    """
    np = _np()
    x, y, valid, dropped = _prepare(before, after, drop_clipped=drop_clipped)
    idx = np.flatnonzero(valid)
    if idx.size < 10:
        raise PhotoError("INVALID_INPUT", "too few usable pixels for a wheel fit",
                         {"usable": int(idx.size)})
    train_pos, held_pos = _split(idx.size, seed, holdout, max_samples)
    train = idx[train_pos]
    held = idx[held_pos]
    params = {name: float(IDENTITY[name]) for name in PARAM_NAMES}
    if initial:
        for name in PARAM_NAMES:
            if name in initial:
                params[name] = float(initial[name])
    else:
        params = initial_guess(x[train], y[train])
    fitted = _fit_values(x, y, train, params, sweeps)
    rounded = request_params(fitted)
    return {
        "params": rounded,
        "model": "PHOTO_GRADING wheels",
        "fit": {
            "train": _fit_errors(x, y, train, rounded),
            "heldout": _fit_errors(x, y, held, rounded),
            "dropped_clipped_fraction": round(dropped, 6),
            "train_pixels": int(len(train)),
            "heldout_pixels": int(len(held)),
        },
        "identifiability_warnings": _identifiability(x, train, fitted),
        "settings": {"seed": int(seed), "max_samples": int(max_samples),
                     "holdout": float(holdout), "sweeps": int(sweeps),
                     "huber_delta": HUBER_DELTA, "l2_penalty": L2_PENALTY,
                     "step_decay": STEP_DECAY, "seed_hues": list(SEED_HUES),
                     "seed_saturations": list(SEED_SATURATIONS),
                     "weak_effect": WEAK_EFFECT, "corr_warning": CORR_WARNING,
                     "residual_threshold": RESIDUAL_THRESHOLD},
    }
