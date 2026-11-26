"""Absolute look descriptors in OKLab, with no fitting and no reference image.

`PHOTO_ANALYZE` uses these to give a non-vision caller numbers it can read: tone
percentiles, zone tints, saturation, a small palette, and skin-band statistics. Everything
is measured on the sampled pixels of one image; nothing here decides whether a look is good.

Determinism: the palette uses a seeded `numpy.random.default_rng(seed)`, the hue sectors are
fixed 30-degree bins, and the output is rounded to six decimals. The same pixels and seed
always produce the same dict.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from .colorspace import _np, hue_deg, rgb_to_oklab

DEFAULT_PALETTE_K = 5
PALETTE_MAX_PIXELS = 20_000
PALETTE_MAX_ITER = 50
HUE_SECTORS = 12
CHROMA_FLOOR = 0.01          # below this OKLab chroma the hue angle is mostly noise
SKIN_MIN_PIXELS = 50
SKIN_MIN_SHARE = 0.005       # 0.5% of the sampled pixels
SKIN_HUE_RANGE = (35.0, 70.0)
SKIN_CHROMA_RANGE = (0.04, 0.14)
SKIN_L_RANGE = (0.40, 0.92)


def _r(x: Any, digits: int = 6) -> float:
    return round(float(x), digits)


def colorfulness_m3(rgb) -> float:
    """Hasler & Suesstrunk (2003) M3 colourfulness on sRGB 0..255. Same code every time."""
    np = _np()
    rgb = np.asarray(rgb, dtype=np.float64) * 255.0
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    rg = r - g
    yb = 0.5 * (r + g) - b
    return float(np.hypot(rg.std(), yb.std()) + 0.3 * np.hypot(rg.mean(), yb.mean()))


def _kmeans(points, k: int, seed: int):
    """Seeded k-means++ in OKLab. Returns (centers, counts); zero-count clusters are kept
    here and dropped by the caller so a uniform image reports one colour, not five copies."""
    np = _np()
    n = int(points.shape[0])
    k = max(1, min(int(k), n))
    rng = np.random.default_rng(int(seed))

    centers = [points[int(rng.integers(n))]]
    for _ in range(1, k):
        d2 = np.min(((points[:, None, :] - np.asarray(centers)[None, :, :]) ** 2).sum(-1), axis=1)
        total = float(d2.sum())
        idx = int(rng.integers(n)) if total <= 0.0 else int(rng.choice(n, p=d2 / total))
        centers.append(points[idx])
    centers = np.asarray(centers, dtype=np.float64)

    labels = np.full(n, -1, dtype=np.int64)
    for _ in range(PALETTE_MAX_ITER):
        d2 = ((points[:, None, :] - centers[None, :, :]) ** 2).sum(-1)
        new_labels = d2.argmin(axis=1)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for j in range(k):
            members = points[labels == j]
            if len(members):
                centers[j] = members.mean(axis=0)
            else:
                # Re-seed an empty cluster at the point farthest from its current centre.
                far = int(np.argmax(d2[np.arange(n), labels]))
                centers[j] = points[far]

    counts = np.bincount(labels, minlength=k).astype(np.int64)
    return centers, counts


def _palette(lab, seed: int, k: int = DEFAULT_PALETTE_K) -> Dict[str, Any]:
    np = _np()
    n = int(lab.shape[0])
    if n > PALETTE_MAX_PIXELS:
        # Deterministic subsample: evenly spaced indices, no second RNG stream.
        idx = np.linspace(0, n - 1, PALETTE_MAX_PIXELS).astype(np.int64)
        points = lab[idx]
    else:
        points = lab
    centers, counts = _kmeans(points, k, seed)
    total = int(counts.sum())
    colors: List[Dict[str, float]] = []
    for c, count in zip(centers, counts):
        if int(count) == 0:
            continue
        L, a, b = float(c[0]), float(c[1]), float(c[2])
        C = math.hypot(a, b)
        colors.append({"L": _r(L), "C": _r(C),
                       "hue": _r(hue_deg(a, b), 3) if C > 1e-9 else 0.0,
                       "weight": _r(int(count) / max(1, total))})
    # Stable presentation: biggest first, then a fixed tie-break. Cluster label order from
    # k-means is arbitrary, but the output order must not be.
    colors.sort(key=lambda e: (-e["weight"], e["L"], e["hue"], e["C"]))
    return {"k": int(k), "colors": colors}


def _zone_tint(lab, L, lo: float, hi: float) -> Dict[str, Any]:
    np = _np()
    if hi <= lo:
        return {"hue": 0.0, "mag": 0.0, "pixels": 0}
    mask = (L >= lo) & (L < hi)
    n = int(mask.sum())
    if n < 20:
        return {"hue": 0.0, "mag": 0.0, "pixels": n}
    da = float(lab[mask, 1].mean() - lab[:, 1].mean())
    db = float(lab[mask, 2].mean() - lab[:, 2].mean())
    mag = math.hypot(da, db)
    return {"hue": _r(hue_deg(da, db), 3) if mag > 1e-9 else 0.0,
            "mag": _r(mag), "pixels": n}


def describe(rgb, seed: int = 0) -> Dict[str, Any]:
    """Measure the absolute look descriptors of sRGB pixels (N,3 or H,W,3, 0..1).

    Tone percentiles are OKLab L. Zone tints are the mean (a,b) of a zone minus the
    whole-image mean (a,b), which removes the global cast but not the scene's own colour.
    Hue sectors are 30-degree OKLab bins; `share` is the fraction of chromatic pixels in a
    bin, so the shares sum to 1 when the image has any chroma. The palette is k-means in
    OKLab (OKLCH with the circular hue handled through a/b) and is sorted by weight.
    """
    np = _np()
    rgb = np.asarray(rgb, dtype=np.float64).reshape(-1, 3)
    if rgb.shape[0] == 0:
        raise ValueError("describe() needs at least one pixel")
    lab = rgb_to_oklab(rgb)
    L = lab[:, 0]
    a = lab[:, 1]
    b = lab[:, 2]
    chroma = np.hypot(a, b)
    hue = hue_deg(a, b)

    p01, p05, p25, p50, p75, p95, p99 = (float(v) for v in np.percentile(L, [1, 5, 25, 50, 75, 95, 99]))
    tone = {
        "p01": _r(p01), "p05": _r(p05), "p25": _r(p25), "p50": _r(p50),
        "p75": _r(p75), "p95": _r(p95), "p99": _r(p99),
        "black_point": _r(p01), "white_rolloff": _r(p99),
        "median": _r(p50), "spread_p95_p5": _r(p95 - p05),
    }

    zones = {
        "shadows": _zone_tint(lab, L, -1.0, p25),
        "midtones": _zone_tint(lab, L, p25, p75),
        "highlights": _zone_tint(lab, L, p75, 2.0),
    }

    chromatic = chroma > CHROMA_FLOOR
    n_chromatic = int(chromatic.sum())
    sector_idx = (np.floor(hue[chromatic] / (360.0 / HUE_SECTORS)).astype(np.int64)) % HUE_SECTORS
    counts = np.bincount(sector_idx, minlength=HUE_SECTORS)
    sums = np.bincount(sector_idx, weights=chroma[chromatic], minlength=HUE_SECTORS)
    sectors = []
    for i in range(HUE_SECTORS):
        count = int(counts[i])
        sectors.append({"hue_center": _r(i * (360.0 / HUE_SECTORS) + 180.0 / HUE_SECTORS, 3),
                        "mean_chroma": _r(sums[i] / count) if count else 0.0,
                        "share": _r(count / n_chromatic) if n_chromatic else 0.0})

    skin_mask = ((hue > SKIN_HUE_RANGE[0]) & (hue < SKIN_HUE_RANGE[1])
                 & (chroma > SKIN_CHROMA_RANGE[0]) & (chroma < SKIN_CHROMA_RANGE[1])
                 & (L > SKIN_L_RANGE[0]) & (L < SKIN_L_RANGE[1]))
    n_skin = int(skin_mask.sum())
    min_skin = max(SKIN_MIN_PIXELS, int(round(rgb.shape[0] * SKIN_MIN_SHARE)))
    if n_skin >= min_skin:
        skin = {"detected": True, "pixels": n_skin, "share": _r(n_skin / rgb.shape[0]),
                "mean_hue": _r(hue_deg(a[skin_mask].mean(), b[skin_mask].mean()), 3),
                "mean_chroma": _r(chroma[skin_mask].mean()),
                "mean_L": _r(L[skin_mask].mean())}
    else:
        skin = {"detected": False, "pixels": n_skin, "share": _r(n_skin / rgb.shape[0]),
                "mean_hue": None, "mean_chroma": None, "mean_L": None}

    return {
        "tone": tone,
        "zone_tint": zones,
        "saturation": {"mean_chroma": _r(chroma.mean()), "p90_chroma": _r(np.percentile(chroma, 90)),
                       "colorfulness_m3": _r(colorfulness_m3(rgb), 4), "hue_sectors": sectors},
        "palette": _palette(lab, seed),
        "skin": skin,
        "settings": {"seed": int(seed), "palette_k": DEFAULT_PALETTE_K, "hue_sectors": HUE_SECTORS,
                     "chroma_floor": CHROMA_FLOOR, "skin_min_share": SKIN_MIN_SHARE},
    }
