"""Objective photo inspection (photo-grading inspect).

Decodes the first frame to raw 8-bit RGB with ffmpeg and computes exact pixel statistics in
pure Python. This is the skill's self-check: after a grade, `inspect` reports clipping,
saturation, cast and hue-family numbers plus warnings, so a result can be verified against
measurable limits instead of being eyeballed.

Thresholds are deliberately conservative (a photo is flagged only when a metric is clearly
outside a natural range); they are heuristics, not a quality score.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .buildlut import HSV_FAMILIES, hue_family_weights
from .errors import PhotoError

SAMPLE_PIXELS = 200_000
HIGH_CLIP_LEVEL = 250          # channel value considered near-clipped white
LOW_CLIP_LEVEL = 5             # channel value considered near-clipped black
NEON_SATURATION = 90           # HSV saturation (0..100) considered neon
NEON_VALUE = 35                # HSV value floor: dark pixels are not neon
NEUTRAL_SATURATION = 0.12      # below this HSV saturation a pixel is near-neutral (white-balance sample)
CAST_LIMIT = 12.0              # mean |channel difference| (0..255) before it is a cast


def _tool(name: str) -> str:
    p = shutil.which(name)
    if not p:
        raise PhotoError("TOOL_ERROR", f"{name} not found on PATH", {"binary": name})
    return p


def _probe(path: Path) -> Dict[str, Any]:
    p = subprocess.run([_tool("ffprobe"), "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=codec_type,width,height,pix_fmt,codec_name",
                        "-print_format", "json", str(path)], capture_output=True, timeout=60)
    if p.returncode != 0:
        raise PhotoError("INVALID_INPUT", f"ffprobe failed on {path.name}: "
                         f"{p.stderr.decode('utf-8', 'replace').strip()[:300]}", {"path": str(path)})
    import json
    doc = json.loads(p.stdout.decode("utf-8", "replace") or "{}")
    streams = [s for s in doc.get("streams", []) if s.get("codec_type") == "video"]
    if not streams:
        raise PhotoError("INVALID_INPUT", f"no photo stream found: {path.name}", {"path": str(path)})
    s = streams[0]
    return {"width": int(s.get("width") or 0), "height": int(s.get("height") or 0),
            "pix_fmt": s.get("pix_fmt"), "codec_name": s.get("codec_name")}


def _raw_rgb(path: Path, width: int, height: int) -> bytes:
    p = subprocess.run([_tool("ffmpeg"), "-nostdin", "-v", "error", "-i", str(path),
                        "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True, timeout=300)
    if p.returncode != 0:
        raise PhotoError("INVALID_INPUT", f"ffmpeg could not decode {path.name}: "
                         f"{p.stderr.decode('utf-8', 'replace').strip()[:300]}", {"path": str(path)})
    if len(p.stdout) < width * height * 3:
        raise PhotoError("INVALID_INPUT", f"short decode for {path.name}", {"path": str(path)})
    return p.stdout


def _percentile(sorted_values: List[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    i = int(round(q / 100.0 * (len(sorted_values) - 1)))
    return sorted_values[max(0, min(len(sorted_values) - 1, i))]


def _hsv(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """HSV of an 8-bit pixel: h in degrees, s and v in 0..1 (same convention as buildlut)."""
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(rf, gf, bf), min(rf, gf, bf)
    v = mx
    s = 0.0 if mx == 0 else (mx - mn) / mx
    if mx == mn:
        h = 0.0
    elif mx == rf:
        h = (60.0 * ((gf - bf) / (mx - mn)) + 360.0) % 360.0
    elif mx == gf:
        h = (60.0 * ((bf - rf) / (mx - mn)) + 120.0) % 360.0
    else:
        h = (60.0 * ((rf - gf) / (mx - mn)) + 240.0) % 360.0
    return h, s, v


def inspect_image(image: str) -> Dict[str, Any]:
    """Return exact pixel statistics and conservative warnings for one photo."""
    path = Path(image)
    if not path.is_file():
        raise PhotoError("INVALID_INPUT", f"image not found: {image}", {"path": str(image)})
    meta = _probe(path)
    width, height = meta["width"], meta["height"]
    if width <= 0 or height <= 0:
        raise PhotoError("INVALID_INPUT", f"image has no usable size: {image}", {"path": str(image)})
    data = _raw_rgb(path, width, height)
    total = width * height
    stride = max(1, total // SAMPLE_PIXELS)

    lumas: List[float] = []
    sats: List[float] = []
    family_hits: Dict[str, float] = {f: 0.0 for f in HSV_FAMILIES}
    family_total = 0.0
    sum_r = sum_g = sum_b = 0
    neutral_r = neutral_g = neutral_b = 0
    neutral_n = 0
    hi_clip = lo_clip = neon = 0
    n = 0
    for idx in range(0, total, stride):
        off = idx * 3
        r, g, b = data[off], data[off + 1], data[off + 2]
        n += 1
        sum_r += r
        sum_g += g
        sum_b += b
        lumas.append(0.2126 * r + 0.7152 * g + 0.0722 * b)
        if max(r, g, b) >= HIGH_CLIP_LEVEL:
            hi_clip += 1
        if max(r, g, b) <= LOW_CLIP_LEVEL:
            lo_clip += 1
        h, s, v = _hsv(r, g, b)
        sats.append(s * 100.0)
        if s * 100.0 >= NEON_SATURATION and v * 100.0 >= NEON_VALUE:
            neon += 1
        if s <= NEUTRAL_SATURATION:
            # White balance is judged on near-neutral pixels (cloud, rock, concrete): the mean
            # of a green landscape is not a cast, it is the scene's content.
            neutral_r += r
            neutral_g += g
            neutral_b += b
            neutral_n += 1
        if s >= 0.15:
            weights = hue_family_weights(h)
            for fam, w in weights.items():
                family_hits[fam] += w
            family_total += 1.0

    lumas.sort()
    sats.sort()
    mean_r, mean_g, mean_b = sum_r / n, sum_g / n, sum_b / n
    cast_rg = mean_r - mean_g
    cast_bg = mean_b - mean_g
    neutral_pct = neutral_n / n * 100.0
    if neutral_n >= max(64, n * 0.01):
        neutral_cast_rg = neutral_r / neutral_n - neutral_g / neutral_n
        neutral_cast_bg = neutral_b / neutral_n - neutral_g / neutral_n
    else:
        neutral_cast_rg, neutral_cast_bg = cast_rg, cast_bg
    top_families = sorted(((f, (c / family_total * 100.0) if family_total else 0.0)
                           for f, c in family_hits.items()), key=lambda kv: -kv[1])[:3]
    metrics: Dict[str, Any] = {
        "width": width, "height": height, "pix_fmt": meta["pix_fmt"], "codec_name": meta["codec_name"],
        "pixels_sampled": n,
        "mean_rgb": [round(mean_r, 2), round(mean_g, 2), round(mean_b, 2)],
        "mean_luma": round(sum(lumas) / n, 2),
        "luma_p01": round(_percentile(lumas, 1), 2), "luma_p05": round(_percentile(lumas, 5), 2),
        "luma_p50": round(_percentile(lumas, 50), 2), "luma_p95": round(_percentile(lumas, 95), 2),
        "luma_p99": round(_percentile(lumas, 99), 2),
        "highlight_clip_pct": round(hi_clip / n * 100.0, 3),
        "shadow_clip_pct": round(lo_clip / n * 100.0, 3),
        "mean_saturation": round(sum(sats) / n, 2),
        "p95_saturation": round(_percentile(sats, 95), 2),
        "neon_pct": round(neon / n * 100.0, 3),
        "cast_r_minus_g": round(cast_rg, 2),
        "cast_b_minus_g": round(cast_bg, 2),
        "neutral_pixels_pct": round(neutral_pct, 2),
        "neutral_cast_r_minus_g": round(neutral_cast_rg, 2),
        "neutral_cast_b_minus_g": round(neutral_cast_bg, 2),
        "hue_families": {f: round(p, 2) for f, p in top_families},
    }

    warnings: List[str] = []
    if metrics["highlight_clip_pct"] > 2.0:
        warnings.append(f"highlight clipping: {metrics['highlight_clip_pct']:.1f}% of pixels have a channel >= {HIGH_CLIP_LEVEL}")
    if metrics["shadow_clip_pct"] > 5.0:
        warnings.append(f"shadow clipping: {metrics['shadow_clip_pct']:.1f}% of pixels are at black")
    if metrics["mean_saturation"] > 55.0:
        warnings.append(f"over-saturated: mean saturation {metrics['mean_saturation']:.1f} (natural photos are usually 20-45)")
    if metrics["neon_pct"] > 2.0:
        warnings.append(f"neon/flat color: {metrics['neon_pct']:.1f}% of pixels are >= {NEON_SATURATION}% saturation")
    if abs(neutral_cast_rg) > CAST_LIMIT or abs(neutral_cast_bg) > CAST_LIMIT:
        basis = (f"near-neutral pixels, {neutral_pct:.1f}% of sample" if neutral_pct >= 1.0
                 else "whole image (too few neutral pixels)")
        warnings.append(f"color cast: R-G {neutral_cast_rg:+.1f}, B-G {neutral_cast_bg:+.1f} "
                        f"(limit {CAST_LIMIT:+.0f}; {basis})")
    return {"schema": "photo-grading/inspection@1", "ok": True, "image": str(path),
            "metrics": metrics, "warnings": warnings}
