"""Executor: runs typed photo operations through FFmpeg's photo filters and validates every
output by re-probing it.

Filter chains (every value reaching a subprocess argv is a fixed flag or a path this skill
resolved itself):
- PHOTO_GRADING      lut3d of the wheel-built LUT (buildlut.build_wheel_lut)
- PHOTO_CORRECTION   eq (exposure -> brightness, contrast, saturation), hue (white balance
                     temperature -> rotation, tint -> saturation multiplier), unsharp
                     (sharpness), plus lut3d of the levels LUT (buildlut.build_levels_lut)
                     when shadows/highlights/blacks/whites are set
- PHOTO_LUT_APPLY    lut3d of the caller's LUT

Validation: after every run, re-probe the output with ffprobe and check: the photo stream
exists, size > 0, width/height unchanged from the source (tolerance 1px), readable, and record
measured signalstats (YAVG/UAVG/VAVG) of source and output in the result. The value is
OBSERVED, never inferred or judged.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import SKILL_ID, VERSION
from .buildlut import build_levels_lut, build_wheel_lut, scale_lut_strength
from .errors import PhotoError
from .model import ColorOperation
from .security import PathPolicy

WORK_DIR_NAME = ".photo-grading"
GEOMETRY_TOLERANCE = 1          # px; photos do not change geometry: a 1px slack
MAX_TOOL_TIMEOUT = 1200.0
PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp")
# (measurement keys we record are "yavg", "uavg", "vavg" — parsed from showinfo's `mean:[Y U V]`)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _lut_arg(path: str) -> str:
    # The path sits in a filter string, where ':' separates options and '\' escapes.
    # Prefer a cwd-relative path (the LUT is written into the cwd): no colon, clean.
    p = str(path)
    try:
        rel = os.path.relpath(p, os.getcwd())
        if not rel.startswith("..") and ":" not in rel:
            return rel.replace("\\", "/")
    except ValueError:
        pass
    return p.replace("\\", "/").replace(":", "\\:")


def _run(argv: List[str], timeout: float, label: str = "") -> subprocess.CompletedProcess:
    try:
        p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=min(timeout, MAX_TOOL_TIMEOUT), capture_output=False)
        return p
    except subprocess.TimeoutExpired:
        raise PhotoError("TOOL_ERROR", f"{label} timed out after {timeout:.0f}s",
                         {"command": argv[0], "timeout": timeout}, retryable=True)
    except OSError as e:
        raise PhotoError("TOOL_ERROR", f"{label} failed to start: {e}", {"command": argv[0]})


class Executor:
    def __init__(self, policy: PathPolicy, timeout: float = 600.0, cancel_event: Optional[Any] = None):
        self.policy = policy
        self.timeout = timeout
        self.ffmpeg = self._locate("ffmpeg", "TOOL_ERROR", "ffmpeg")
        self.ffprobe = self._locate("ffprobe", "TOOL_ERROR", "ffprobe")
        self._cancel = cancel_event

    def _locate(self, name: str, code: str, what: str) -> Path:
        p = shutil.which(name)
        if not p:
            raise PhotoError(code, f"{what} not found on PATH", {"binary": name})
        return Path(p)

    # ---- measurement / probing ----
    def probe(self, path: Path) -> Dict[str, Any]:
        p = _run([str(self.ffprobe), "-v", "error", "-print_format", "json",
                  "-show_format", "-show_streams", str(path)], 30.0, "ffprobe")
        if p.returncode != 0:
            raise PhotoError("INVALID_INPUT", f"ffprobe failed on {path.name}: {p.stderr.decode('utf-8', 'replace').strip()[:300]}",
                             {"path": str(path)})
        doc = json.loads(p.stdout.decode("utf-8", "replace") or "{}")
        streams = [s for s in doc.get("streams", []) if s.get("codec_type") == "video"]
        if not streams:
            raise PhotoError("INVALID_INPUT", f"no photo stream found: {path.name}", {"path": str(path)})
        s = streams[0]
        size = os.path.getsize(path)
        return {"path": str(path), "width": int(s.get("width") or 0), "height": int(s.get("height") or 0),
                "pix_fmt": s.get("pix_fmt"), "codec_name": s.get("codec_name"), "duration": doc.get("format", {}).get("duration"),
                "size": size, "sha256": _sha256_file(path), "n_streams": len(doc.get("streams", []))}

    def signalstats(self, path: Path) -> Dict[str, float]:
        """Measured mean luma/chroma of the first frame, via `ffmpeg -vf signalstats,showinfo`.
        showinfo prints `mean:[<y> <u> <v>]` for the frame at info level; the values are
        OBSERVED measurements, used as before/after records in provenance."""
        import re
        p = subprocess.run([str(self.ffmpeg), "-nostdin", "-v", "info", "-i", str(path),
                            "-vf", "signalstats,showinfo", "-f", "null", "-"], capture_output=True, timeout=60)
        out = (p.stderr or b"").decode("utf-8", "replace")
        m = re.search(r"mean:\[([0-9.\-]+) ([0-9.\-]+) ([0-9.\-]+)\]", out)
        if not m:
            return {}
        return {"yavg": float(m.group(1)), "uavg": float(m.group(2)), "vavg": float(m.group(3))}

    # ---- validation ----
    def _check_geometry_unchanged(self, src_probe: Dict[str, Any], dst: Path, timeout: float) -> Dict[str, Any]:
        try:
            dst_probe = self.probe(dst)
        except PhotoError as e:
            raise PhotoError("VALIDATION_ERROR", f"output {Path(dst).name} did not probe: {e.message}",
                             {"path": str(dst), "probe_error": e.message})
        for k in ("width", "height"):
            s, d = src_probe[k], dst_probe[k]
            if s and d and abs(s - d) > GEOMETRY_TOLERANCE:
                raise PhotoError("VALIDATION_ERROR", f"output {k} changed from {s} to {d}",
                                 {"path": str(dst), "key": k, "before": s, "after": d})
        return dst_probe

    def _check_readable(self, dst: Path) -> None:
        try:
            with open(dst, "rb") as f:
                f.read(1)
        except OSError as e:
            raise PhotoError("VALIDATION_ERROR", f"output {Path(dst).name} is not readable", {"error": str(e)})

    # ---- filter chain construction ----
    def _photo_correction_filter(self, op: ColorOperation) -> List[str]:
        p = op.parameters
        filters: List[str] = []
        # white balance: temperature -> hue rotation, tint -> saturation multiplier (hue filter)
        temp = p.get("white_balance_temperature")
        tint = p.get("white_balance_tint")
        if temp is not None or tint is not None:
            t = float(temp) if temp is not None else 6500.0
            tt = float(tint) if tint is not None else 0.0
            h = round((6500.0 - t) * 0.45)          # neutral 6500 -> 0; hot -> +; cool -> -
            s = 1.0 - tt / 100.0                    # tint +100 -> 0 (desaturate green/magenta)
            h = max(-180, min(180, h))
            filters.append(f"hue=h={h:.4g}:s={s:.4g}")
        # base eq
        eq_parts: List[str] = []
        exposure = p.get("exposure")
        contrast = p.get("contrast")
        saturation = p.get("saturation")
        if exposure is not None:
            eq_parts.append(f"brightness={float(exposure) / 10.0:.4g}")
        if contrast is not None:
            eq_parts.append(f"contrast={max(0.0, min(2.0, 1.0 + float(contrast) / 100.0)):.4g}")
        if saturation is not None:
            eq_parts.append(f"saturation={max(0.0, min(2.0, 1.0 + float(saturation) / 100.0)):.4g}")
        if eq_parts:
            filters.append("eq=" + ":".join(eq_parts))
        # levels LUT (shadows/highlights/blacks/whites)
        levels = {k: p.get(k, 0.0) for k in ("shadows", "highlights", "blacks", "whites")}
        if any(v for v in levels.values()):
            lut = build_levels_lut(**levels)
            filters.append(f"lut3d=file={_lut_arg(lut)}")
        # sharpness
        sharpness = p.get("sharpness")
        if sharpness:
            filters.append(f"unsharp=la.size=3:amount={min(1.0, float(sharpness) / 100.0):.4g}")
        # film grain (transcript: "film grain this is really important... use it sparingly")
        grain = p.get("grain")
        if grain:
            filters.append(f"noise=alls={int(grain)}")
        return filters

    def build_chain(self, op: ColorOperation, work_dir: Path) -> List[str]:
        work_dir.mkdir(parents=True, exist_ok=True)
        if op.type == "PHOTO_GRADING":
            wheels = {w: {k: op.parameters.get(f"{w}_{k}", 0) for k in ("hue", "saturation", "luminance")}
                      for w in ("shadows", "midtones", "highlights", "global")}
            lut = build_wheel_lut(wheels, op.parameters.get("blending", 50), op.parameters.get("balance", 0),
                                  strength=op.parameters.get("strength", 1.0))
            return [f"lut3d=file={_lut_arg(lut)}"]
        if op.type == "PHOTO_CORRECTION":
            return self._photo_correction_filter(op)
        if op.type == "PHOTO_LUT_APPLY":
            lut = op.parameters["lut_path"]
            strength = float(op.parameters.get("strength", 1.0))
            if strength < 1.0:
                lut = scale_lut_strength(lut, strength, str(self.policy.work_dir()))
            return [f"lut3d=file={_lut_arg(lut)}"]
        raise PhotoError("UNSUPPORTED_OPERATION", f"no chain for type {op.type!r}", {"type": op.type})

    def _apply(self, src: Path, dst: Path, op: ColorOperation, timeout: float) -> Dict[str, Any]:
        chain = self.build_chain(op, self.policy.work_dir())
        argv = [str(self.ffmpeg), "-nostdin", "-y", "-i", str(src)]
        if chain:
            argv += ["-vf", ",".join(chain)]
        argv += [str(dst)]
        src_probe = self.probe(src)
        src_stats = self.signalstats(src)
        p = _run(argv, timeout, f"ffmpeg {op.type}")
        if p.returncode != 0:
            raise PhotoError("TOOL_ERROR", f"ffmpeg failed for {op.type}: {p.stderr.decode('utf-8', 'replace').strip()[:300]}",
                             {"op_id": op.op_id, "type": op.type}, retryable=True)
        if not dst.is_file() or dst.stat().st_size == 0:
            raise PhotoError("OUTPUT_ERROR", f"ffmpeg wrote no output for {op.op_id}", {"path": str(dst)})
        dst_probe = self._check_geometry_unchanged(src_probe, dst, timeout)
        self._check_readable(dst)
        out_stats = self.signalstats(dst)
        lut_info: Dict[str, Any] = {}
        if op.type in ("PHOTO_GRADING", "PHOTO_LUT_APPLY"):
            lut = op.parameters["lut_path"] if op.type == "PHOTO_LUT_APPLY" else chain[0].split("file=", 1)[1]
            lut_path = Path(lut)
            lut_info = {"path": str(lut_path), "sha256": _sha256_file(lut_path), "applied": "lut3d"}
        return {"operation_id": op.op_id, "type": op.type, "tool": "ffmpeg",
                "input_hash": src_probe["sha256"], "output_hash": dst_probe["sha256"],
                "measurements": {"before": {k: v for k, v in src_stats.items()}, "after": {k: v for k, v in out_stats.items()},
                                 "source": {"width": src_probe["width"], "height": src_probe["height"]},
                                 "output": {"width": dst_probe["width"], "height": dst_probe["height"],
                                            "pix_fmt": dst_probe["pix_fmt"], "codec_name": dst_probe["codec_name"]}},
                **lut_info}

    # ---- reuse ----
    def _identity(self, op: ColorOperation, src_probe: Dict[str, Any], tool_versions: Dict[str, str]) -> str:
        canon = {"type": op.type, "parameters": op.parameters, "input_identity": src_probe["sha256"],
                 "tool_versions": tool_versions}
        return hashlib.sha256(json.dumps(canon, sort_keys=True, default=str).encode()).hexdigest()

    def _check_reuse(self, dst: Path, identity: str, src: Path, op: ColorOperation) -> Optional[Dict[str, Any]]:
        stamp = self.policy.work_dir() / f"{dst.stem}.stamp.json"
        if not stamp.is_file():
            return None
        doc = json.loads(stamp.read_text("utf-8"))
        if doc.get("identity") != identity or not dst.is_file() or dst.stat().st_size == 0:
            return None
        try:
            self.probe(dst)
        except PhotoError:
            return None
        return doc["result"]

    def _write_stamp(self, dst: Path, identity: str, result: Dict[str, Any]) -> None:
        self.policy.work_dir().mkdir(parents=True, exist_ok=True)
        (self.policy.work_dir() / f"{dst.stem}.stamp.json").write_text(
            json.dumps({"identity": identity, "result": result, "tool": "ffmpeg", "version": subprocess.run(
                            [str(self.ffmpeg), "-version"], capture_output=True).stdout.decode("utf-8", "replace").split("\n")[0]}),
            "utf-8")

    # ---- main entry: run every op in order; bind outputs to op artifacts ----
    def run_project(self, project, reuse: bool = True) -> Dict[str, Any]:
        src = self.policy.check_input(project.source.path, "input")
        if src.suffix.lower() not in PHOTO_EXTENSIONS:
            raise PhotoError("INVALID_INPUT", f"input is not a photo file: {src.suffix}", {"path": str(src)})
        src_probe = self.probe(src)
        tool_versions = {"ffmpeg": subprocess.run([str(self.ffmpeg), "-version"], capture_output=True).stdout.decode("utf-8", "replace").split("\n")[0][:60]}
        results_by_op: Dict[str, Dict[str, Any]] = {}
        artifacts: Dict[str, Path] = {"source": src}
        current: Path = src
        for op in project.operations:
            # intermediates keep the source photo's extension: ffmpeg infers the output format
            # from the name, and a photo never changes container in this skill
            dst = self.policy.work_dir() / f"{op.op_id}{src.suffix}"
            identity = self._identity(op, src_probe, tool_versions)
            hit = None
            if reuse:
                hit = self._check_reuse(dst, identity, src, op)
                result = hit if hit is not None else self._apply(current, dst, op, project.options["timeout"])
                if hit is None:
                    self._write_stamp(dst, identity, result)
            else:
                result = self._apply(current, dst, op, project.options["timeout"])
                self._write_stamp(dst, identity, result)
            results_by_op[op.op_id] = {"operation_id": op.op_id, "type": op.type, **result, "reused": hit is not None}
            artifacts[f"op:{op.op_id}"] = dst   # keyed by REF so an op literally named "source" can't clobber it
            current = dst
        outputs: List[Dict[str, Any]] = []
        for o in project.outputs:
            ref = o.operation                   # "source" | "op:<id>"
            artifact = artifacts[ref]
            dst = self.policy.check_output(o.path, [])
            if artifact != dst and artifact.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy2(artifact, dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
            out_record: Dict[str, Any] = {"output_id": o.output_id, "path": str(dst), "status": "completed",
                                          "sha256": self.probe(dst)["sha256"]}
            result = results_by_op.get(ref.split(":", 1)[1]) if ref != "source" else None
            if result is not None:
                out_record["provenance"] = result
            outputs.append(out_record)
        return {"tool": "ffmpeg", "tool_versions": tool_versions, "source": {"path": str(src), "sha256": src_probe["sha256"]},
                "results": list(results_by_op.values()), "outputs": outputs}

    def response(self, project, dry_run: bool) -> Dict[str, Any]:
        src = self.policy.check_input(project.source.path, "input")
        src_probe = self.probe(src)
        plan = {
            "operations": [{"op_id": o.op_id, "type": o.type, "input": o.input, "parameters": dict(o.parameters)}
                           for o in project.operations],
            "source": {"path": str(src), "sha256": src_probe["sha256"], "width": src_probe["width"], "height": src_probe["height"]},
            "outputs": [{"output_id": o.output_id, "operation": o.operation, "path": o.path, "format": o.format}
                        for o in project.outputs],
            "geometry_tolerance_px": GEOMETRY_TOLERANCE,
        }
        if dry_run:
            return {"schema": f"{SKILL_ID}/response@1", "skill": {"id": SKILL_ID, "version": VERSION},
                    "ok": True, "status": "planned", "dry_run": True, "plan": plan, "warnings": []}
        exec_info = self.run_project(project, reuse=project.options["reuse_intermediates"])
        return {"schema": f"{SKILL_ID}/response@1", "skill": {"id": SKILL_ID, "version": VERSION},
                "ok": True, "status": "ok", "dry_run": False, "plan": plan,
                "results": exec_info["results"], "outputs": exec_info["outputs"], "warnings": []}

    # cancelled via signal: best-effort partial-output removal is left to callers
    def cancel(self) -> None:
        if self._cancel is not None:
            self._cancel()
