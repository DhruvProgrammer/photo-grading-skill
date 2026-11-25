"""Environment diagnosis against the contract. Reports only what was detected; every
capability carries one of supported | unsupported | unknown, never a guess. Detection goes
through `ffmpeg -h filter=<name>` / `ffprobe` -- pure process output, no assumptions."""
from __future__ import annotations

import importlib
import platform
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional


from . import DOCTOR_SCHEMA_VERSION, SKILL_ID, VERSION
from .errors import PhotoError
from .model import OPERATION_TYPES
from .security import PathPolicy

DOCTOR_SCHEMA_ID = f"{SKILL_ID}/doctor@{DOCTOR_SCHEMA_VERSION}"
PHOTO_FILTERS = ("lut3d", "eq", "hue", "unsharp", "cas", "signalstats", "showinfo", "lut", "vignette", "curves", "colorlevels")


def _version(binpath: Optional[str]) -> Optional[str]:
    if not binpath:
        return None
    try:
        out = subprocess.run([binpath, "-version"], capture_output=True, timeout=30).stdout.decode("utf-8", "replace")
        return out.split("\n")[0].strip() or None
    except Exception:
        return None


def _filter_supported(ffmpeg: str, name: str) -> bool:
    try:
        p = subprocess.run([ffmpeg, "-hide_banner", "-h", f"filter={name}"],
                           capture_output=True, timeout=30)
        out = (p.stdout or b"").decode("utf-8", "replace") + (p.stderr or b"").decode("utf-8", "replace")
    except Exception:
        return False
    return re.search(rf"\b{re.escape(name)}\b", out) is not None


def filter_status(ffmpeg: Optional[str]) -> Dict[str, str]:
    if not ffmpeg:
        return {name: "unsupported" for name in PHOTO_FILTERS}
    return {name: ("supported" if _filter_supported(ffmpeg, name) else "unsupported") for name in PHOTO_FILTERS}


def _problem_list() -> List[str]:
    return []


def doctor_report(workspace: Optional[str] = None) -> Dict[str, Any]:
    checks: Dict[str, Any] = {}
    problems: List[str] = []
    checks["python"] = {"status": "ok", "version": platform.python_version(), "implementation": platform.python_implementation(),
                        "platform": platform.system()}
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    checks["ffmpeg"] = {"status": "ok" if ffmpeg else "missing", "version": _version(ffmpeg)}
    checks["ffprobe"] = {"status": "ok" if ffprobe else "missing", "version": _version(ffprobe)}
    # Optional critic dependencies. They are not required for the core image operations; the
    # doctor reports them as capabilities so PHOTO_ANALYZE/SCORE/OPTIMIZE can be "unsupported"
    # without failing the whole environment.
    for module, name in (("numpy", "numpy"), ("PIL", "Pillow")):
        try:
            mod = importlib.import_module(module)
            checks[name] = {"status": "ok", "version": getattr(mod, "__version__", None)}
        except Exception as e:  # pragma: no cover - depends on the environment
            checks[name] = {"status": "missing", "version": None, "detail": str(e)}
    filters = filter_status(ffmpeg)
    checks["filters"] = {k: {"status": v} for k, v in filters.items()}
    if not ffmpeg or not ffprobe:
        problems.append("ffmpeg / ffprobe not found on PATH")
    try:
        policy = PathPolicy(workspace)
        checks["path_policy"] = {"status": "ok", "workspace": str(policy.workspace),
                                 "work_dir": str(policy.workspace / ".photo-grading")}
    except PhotoError as e:
        checks["path_policy"] = {"status": "fail", "detail": e.message}
        problems.append("path policy: " + e.message)
    def _status(name: str) -> str:
        if name in filters:
            return filters[name]  # "supported" | "unsupported" | "unknown"
        return checks.get(name, {}).get("status", "unsupported")

    ops = {}
    for typ in OPERATION_TYPES:
        need = ["ffmpeg", "ffprobe"]
        if typ == "PHOTO_GRADING":
            need += ["lut3d"]
        elif typ == "PHOTO_CORRECTION":
            # white balance, vibrance, levels and the tone curve are generated LUTs; sharpness
            # is unsharp, clarity is cas, grain is noise, exposure/contrast/saturation are eq.
            need += ["eq", "lut3d", "unsharp", "cas", "signalstats", "showinfo"]
        elif typ == "PHOTO_LUT_APPLY":
            need += ["lut3d"]
        elif typ == "PHOTO_HSV":
            need += ["lut3d"]
        elif typ in ("PHOTO_ANALYZE", "PHOTO_SCORE"):
            need += ["numpy", "Pillow"]
        elif typ == "PHOTO_OPTIMIZE":
            need += ["lut3d", "numpy", "Pillow"]
        ok = all(_status(c) in ("ok", "supported") for c in need)
        st = "supported" if ok else ("unknown" if any(_status(c) == "unknown" for c in need) else "unsupported")
        ops[typ] = {"status": st, "required": need,
                    "missing": [c for c in need if _status(c) not in ("ok", "supported", "unknown")]}
    checks["operations"] = ops
    unsupported = sorted(t for t, o in ops.items() if o["status"] == "unsupported")
    problems += [f"{t} unavailable: missing {o['missing']}" for t, o in ops.items() if o["status"] == "unsupported"]
    status = "fail" if problems else ("degraded" if unsupported else "ok")
    return {"schema": DOCTOR_SCHEMA_ID, "skill": {"id": SKILL_ID, "version": VERSION}, "status": status,
            "checks": checks, "unavailable_operations": unsupported, "problems": problems, "secrets_shown": False}
