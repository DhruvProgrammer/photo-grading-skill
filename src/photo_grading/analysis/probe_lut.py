"""Mode C: probe a .cube LUT, describe it, and try to explain it as wheel params.

A LUT is a black box. The probe set is deterministic except for one seeded uniform sample:
a 64-step neutral ramp, 12 hues x 3 chroma x 3 luma color patches, and 4,096 seeded sRGB
colors. The LUT is applied with the same trilinear interpolation FFmpeg uses, and the
resulting facts are OBSERVED measurements, not judgments.

The fit reuses `fit_params` (the same wheel model and optimizer a pair fit uses). If the
mean residual is above 0.02 the LUT is not expressible as wheels; the report says so and
points at `PHOTO_LUT_APPLY`, while still returning the best-fit params.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .colorspace import _np, hue_deg, rgb_to_oklab
from .fit_params import (RESIDUAL_THRESHOLD, fit_wheel_grade, hsv_to_rgb,
                         request_params)
from .lutio import apply_lut_numpy, read_cube

NEUTRAL_POINTS = 64
HUE_SECTORS = 12
CHROMA_LEVELS = (0.35, 0.60, 0.85)
LUMA_LEVELS = (0.30, 0.55, 0.80)
UNIFORM_POINTS = 4096
NEUTRAL_NO_OP = 0.005      # max delta_E_OK on the neutral ramp that still counts as a no-op
TINT_BINS = 8


def _r(value: Any, digits: int = 6) -> float:
    return round(float(value), digits)


def _signed_hue_diff(a: float, b: float) -> float:
    return (float(a) - float(b) + 180.0) % 360.0 - 180.0


def probe_points(seed: int = 0) -> Dict[str, Any]:
    """The deterministic probe set. `uniform` is the only seeded part."""
    np = _np()
    ramp = np.repeat(np.linspace(0.0, 1.0, NEUTRAL_POINTS)[:, None], 3, axis=1)
    centers: List[float] = []
    patches: List[Any] = []
    for sector in range(HUE_SECTORS):
        hue = sector * 30.0 + 15.0
        for chroma in CHROMA_LEVELS:
            for luma in LUMA_LEVELS:
                centers.append(hue)
                patches.append((hue, chroma, luma))
    patch_hsv = np.asarray(patches, dtype=np.float64)
    hue_patches = hsv_to_rgb(patch_hsv[:, 0], patch_hsv[:, 1], patch_hsv[:, 2])
    rng = np.random.default_rng(int(seed))
    uniform = rng.random((UNIFORM_POINTS, 3))
    points = np.vstack([ramp, hue_patches, uniform])
    return {"points": points, "neutral": ramp, "hue_patches": hue_patches,
            "hue_centers": np.asarray(centers, dtype=np.float64),
            "uniform": uniform, "sizes": {"neutral": int(len(ramp)),
                                          "hue_patches": int(len(hue_patches)),
                                          "uniform": int(len(uniform))}}


def _neutral_facts(points: Dict[str, Any], out) -> Dict[str, Any]:
    np = _np()
    ramp = points["neutral"]
    lab_in = rgb_to_oklab(ramp)
    lab_out = rgb_to_oklab(out[:len(ramp)])
    delta = np.linalg.norm(lab_out - lab_in, axis=1)
    luma_in = 0.2126 * ramp[:, 0] + 0.7152 * ramp[:, 1] + 0.0722 * ramp[:, 2]
    bins = []
    for i in range(TINT_BINS):
        lo = i / TINT_BINS
        hi = (i + 1) / TINT_BINS
        mask = (luma_in >= lo) & (luma_in <= hi if i == TINT_BINS - 1 else luma_in < hi)
        if not np.any(mask):
            continue
        da = float((lab_out[mask, 1] - lab_in[mask, 1]).mean())
        db = float((lab_out[mask, 2] - lab_in[mask, 2]).mean())
        bins.append({"luma": _r((lo + hi) / 2.0),
                     "da": _r(da), "db": _r(db),
                     "hue": _r(hue_deg(da, db), 3) if abs(da) + abs(db) > 1e-9 else 0.0,
                     "mag": _r((da * da + db * db) ** 0.5)})
    ramp_out = out[:len(ramp)]
    return {
        "neutral_ramp": {
            "input": [_r(v) for v in ramp[:, 0]],
            "r": [_r(v) for v in ramp_out[:, 0]],
            "g": [_r(v) for v in ramp_out[:, 1]],
            "b": [_r(v) for v in ramp_out[:, 2]],
        },
        "black_lift": [_r(v) for v in ramp_out[0]],
        "white_rolloff": [_r(v) for v in ramp_out[-1]],
        "tint_vs_luma": bins,
        "neutral_no_op": bool(float(delta.max()) <= NEUTRAL_NO_OP),
        "neutral_max_delta_E_OK": _r(float(delta.max())),
    }


def _hue_facts(points: Dict[str, Any], out) -> List[Dict[str, Any]]:
    np = _np()
    start = len(points["neutral"])
    patches = points["hue_patches"]
    lab_in = rgb_to_oklab(patches)
    lab_out = rgb_to_oklab(out[start:start + len(patches)])
    c_in = np.hypot(lab_in[:, 1], lab_in[:, 2])
    c_out = np.hypot(lab_out[:, 1], lab_out[:, 2])
    hue_in = hue_deg(lab_in[:, 1], lab_in[:, 2])
    hue_out = hue_deg(lab_out[:, 1], lab_out[:, 2])
    centers = points["hue_centers"]
    sectors: List[Dict[str, Any]] = []
    for sector in range(HUE_SECTORS):
        center = sector * 30.0 + 15.0
        mask = centers == center
        if not np.any(mask):
            continue
        ratio = c_out[mask] / np.maximum(c_in[mask], 1e-9)
        shifts = [_signed_hue_diff(a, b) for a, b in zip(hue_out[mask], hue_in[mask])]
        sectors.append({"hue_center": _r(center, 3),
                        "chroma_ratio": _r(float(ratio.mean())),
                        "hue_shift_deg": _r(float(np.mean(shifts)), 3),
                        "patches": int(mask.sum())})
    return sectors


def _fit_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    fit = report["fit"]
    held = fit["heldout"]
    train = fit["train"]
    if held.get("mean_delta_E_OK") is not None:
        mean = float(held["mean_delta_E_OK"])
        p95 = float(held["p95_delta_E_OK"])
        source = "heldout"
    else:
        mean = float(train["mean_delta_E_OK"])
        p95 = float(train["p95_delta_E_OK"])
        source = "train"
    return {"mean_delta_E_OK": mean, "p95_delta_E_OK": p95, "source": source}


def probe_table(table, size: int, seed: int = 0) -> Dict[str, Any]:
    """Measure a dense cube table (already in [blue, green, red] order)."""
    np = _np()
    points = probe_points(seed)
    inputs = points["points"]
    outputs = apply_lut_numpy(inputs, table, size)
    fit = fit_wheel_grade(inputs, outputs, seed=seed, max_samples=len(inputs),
                          drop_clipped=False)
    summary = _fit_summary(fit)
    expressible = summary["mean_delta_E_OK"] <= RESIDUAL_THRESHOLD
    if expressible:
        message = (f"fits the wheel model: mean delta_E_OK {summary['mean_delta_E_OK']:.4f} "
                   f"on the {summary['source']} probe")
    else:
        message = (f"this LUT is not expressible as wheels: mean delta_E_OK "
                   f"{summary['mean_delta_E_OK']:.4f} is above {RESIDUAL_THRESHOLD:g}; "
                   "apply it with PHOTO_LUT_APPLY instead")
    return {
        "schema": "photo-grading/lut_probe@1",
        "ok": True,
        "kind": "lut_probe",
        "params": request_params(fit["params"]),
        "fit": {"mean_delta_E_OK": summary["mean_delta_E_OK"],
                "p95_delta_E_OK": summary["p95_delta_E_OK"],
                "source": summary["source"],
                "train": fit["fit"]["train"],
                "heldout": fit["fit"]["heldout"],
                "probe_points": int(len(inputs))},
        "facts": {
            **_neutral_facts(points, outputs),
            "hue_sectors": _hue_facts(points, outputs),
        },
        "expressible_as_wheels": bool(expressible),
        "residual_threshold": RESIDUAL_THRESHOLD,
        "message": message,
        "identifiability_warnings": fit["identifiability_warnings"],
        "settings": {"seed": int(seed), "neutral_points": points["sizes"]["neutral"],
                     "hue_patches": points["sizes"]["hue_patches"],
                     "uniform_points": points["sizes"]["uniform"],
                     "chroma_levels": list(CHROMA_LEVELS), "luma_levels": list(LUMA_LEVELS),
                     "neutral_no_op_threshold": NEUTRAL_NO_OP},
        "measurements": "OBSERVED",
    }


def probe_lut(path: str, seed: int = 0) -> Dict[str, Any]:
    """Parse `path` and probe it. Raises PhotoError for a missing or malformed file."""
    cube = read_cube(path)
    report = probe_table(cube["table"], cube["size"], seed=seed)
    report["lut"] = {"path": cube["path"], "size": cube["size"], "title": cube["title"]}
    return report
