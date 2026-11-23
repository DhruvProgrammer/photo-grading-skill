"""Typed photo operation model and request validation (schema: photo-grading/request@1).

Operations:
- PHOTO_GRADING  the core creative op: the 3-way color grading wheels (shadows / midtones /
  highlights / global), each (hue 0..360, saturation 0..100, luminance -100..100), plus
  `blending` (0..100) and `balance` (-100..100). Executed by generating a 3D .cube LUT from
  the wheels and applying it with ffmpeg's lut3d.
- PHOTO_CORRECTION  base corrections: white_balance_temperature (2500..10000),
  white_balance_tint (-100..100), exposure (-10..10), contrast (-100..100), highlights,
  shadows, blacks, whites (-100..100 each), saturation (-100..100); executed via generated
  LUT + ffmpeg eq/hue/unsharp.
- PHOTO_WHITE_BALANCE  alias of PHOTO_CORRECTION restricted to temperature/tint (resolved to
  PHOTO_CORRECTION at validation, like the video skill's WHITE_BALANCE).
- PHOTO_HSV  per-hue-family HSL tweaks (red/orange/yellow/green/cyan/blue/magenta), each
  hue/saturation/luminance -100..100; executed via a generated LUT (soft family weights, so
  neighbouring colors blend instead of posterizing).
- PHOTO_LUT_APPLY  apply a 3D .cube LUT with ffmpeg lut3d; requires lut_path.

The model is a pure structural/semantic validator: it never touches the file system (that is
the executor's and PathPolicy's job). Unknown fields are rejected everywhere; fields that
could carry a filter string or executable are rejected by name everywhere in the document.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from . import REQUEST_SCHEMA_VERSION, SKILL_ID
from .errors import PhotoError

REQUEST_SCHEMA_ID = f"{SKILL_ID}/request@{REQUEST_SCHEMA_VERSION}"

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
REF_RE = re.compile(r"^(source|op:[A-Za-z0-9][A-Za-z0-9._-]{0,63})$")

FORBIDDEN_KEYS = frozenset({"command", "commands", "argv", "args", "cmd", "shell", "exec", "executable", "script",
                            "filter", "filters", "filter_complex", "vf", "af", "ffmpeg", "env", "cwd", "api_key",
                            "workspace", "process", "eval", "apply", "denoiser"})
MAX_OPERATIONS = 50
MAX_DOC_BYTES = 16 * 1024 * 1024

# Output container: format name -> extension (photos keep their original format; no container
# conversion is offered by this skill).
OUTPUT_FORMATS: Dict[str, Dict[str, Any]] = {
    "jpg": {"extension": ".jpg"},
    "jpeg": {"extension": ".jpeg"},
    "png": {"extension": ".png"},
    "tiff": {"extension": ".tiff"},
    "tif": {"extension": ".tif"},
    "webp": {"extension": ".webp"},
    "bmp": {"extension": ".bmp"},
}
PHOTO_EXTENSIONS = tuple(fmt["extension"] for fmt in OUTPUT_FORMATS.values())

# operation_aliases: request-level aliases, resolved to their target type at validation.
OPERATION_TYPES = ("PHOTO_GRADING", "PHOTO_CORRECTION", "PHOTO_LUT_APPLY", "PHOTO_HSV")
OPERATION_ALIASES = {"WHITE_BALANCE": "PHOTO_CORRECTION", "PHOTO_WHITE_BALANCE": "PHOTO_CORRECTION"}


def _is_int(v: Any) -> bool:
    return isinstance(v, bool) is False and isinstance(v, int)


def _is_num(v: Any) -> bool:
    return isinstance(v, bool) is False and isinstance(v, (int, float))


def _check_id(doc: Dict[str, Any], value: Any, pattern: Any, what: str, path: str) -> str:
    if not isinstance(value, str) or not pattern.match(value):
        raise PhotoError("INVALID_REQUEST", f"{what} must match {pattern.pattern}", {"path": path, "got": value})
    return value


def _validate_params(params: Any, allowed: Dict[str, Dict[str, Any]], alias: bool = False) -> None:
    """Typed parameters: type, range, and "each independently optional and defaulting to
    unchanged". Unknown fields in the parameters object are rejected."""
    if not isinstance(params, dict):
        raise PhotoError("INVALID_REQUEST", "operation parameters must be an object", {})
    path = "operations[].parameters"
    for k, v in params.items():
        if k not in allowed:
            raise PhotoError("INVALID_REQUEST", f"unknown parameter {k!r}", {"path": path, "parameter": k})
        spec = allowed[k]
        if spec.get("required") and (v is None or (isinstance(v, str) and not v)):
            raise PhotoError("INVALID_REQUEST", f"parameter {k} is required", {"path": path, "parameter": k})
        if spec.get("type") == "string" and v is not None and not isinstance(v, str):
            raise PhotoError("INVALID_REQUEST", f"parameter {k} must be a string", {"path": path, "parameter": k})
        if spec.get("type") in ("int", "number") and v is not None:
            lo, hi = spec["min"], spec["max"]
            if spec["type"] == "int":
                if not _is_int(v) or v < lo or v > hi:
                    raise PhotoError("INVALID_REQUEST", f"parameter {k} must be an integer in [{lo}, {hi}]", {"path": path, "parameter": k, "got": v})
            else:
                if not _is_num(v) or v < lo or v > hi:
                    raise PhotoError("INVALID_REQUEST", f"parameter {k} must be a number in [{lo}, {hi}]", {"path": path, "parameter": k, "got": v})


# ---- typed parameter tables ----

_WHEEL_PARAMS: Dict[str, Dict[str, Any]] = {
    "hue": {"type": "int", "min": 0, "max": 360, "default": 0},
    "saturation": {"type": "int", "min": 0, "max": 100, "default": 0},
    "luminance": {"type": "int", "min": -100, "max": 100, "default": 0},
}
def _wheel(prefix: str, default_hue: int = 0, default_sat: int = 0) -> Dict[str, Dict[str, Any]]:
    return {f"{prefix}_{k}": dict(v, default=default_hue if k == "hue" else default_sat if k == "saturation" else 0)
            for k, v in _WHEEL_PARAMS.items()}


PHOTO_GRADING_PARAMS: Dict[str, Dict[str, Any]] = {
    **_wheel("shadows"), **_wheel("midtones"), **_wheel("highlights"), **_wheel("global"),
    "blending": {"type": "int", "min": 0, "max": 100, "default": 50},
    "balance": {"type": "int", "min": -100, "max": 100, "default": 0},
    "strength": {"type": "number", "min": 0.0, "max": 1.0, "default": 1.0},
}

PHOTO_CORRECTION_PARAMS: Dict[str, Dict[str, Any]] = {
    "white_balance_temperature": {"type": "int", "min": 2500, "max": 10000, "default": 6500},
    "white_balance_tint": {"type": "int", "min": -100, "max": 100, "default": 0},
    "exposure": {"type": "number", "min": -10.0, "max": 10.0, "default": 0.0},
    "contrast": {"type": "number", "min": -100.0, "max": 100.0, "default": 0.0},
    "highlights": {"type": "number", "min": -100.0, "max": 100.0, "default": 0.0},
    "shadows": {"type": "number", "min": -100.0, "max": 100.0, "default": 0.0},
    "blacks": {"type": "number", "min": -100.0, "max": 100.0, "default": 0.0},
    "whites": {"type": "number", "min": -100.0, "max": 100.0, "default": 0.0},
    "saturation": {"type": "number", "min": -100.0, "max": 100.0, "default": 0.0},
    # Vibrance (user feedback: "keep saturation controlled across all channels"): a saturation
    # boost weighted toward under-saturated pixels, so already-vivid foliage/sky barely move and
    # neutral pixels stay neutral. Prefer it over `saturation` for "make it vibrant".
    "vibrance": {"type": "number", "min": -100.0, "max": 100.0, "default": 0.0},
    "sharpness": {"type": "int", "min": 0, "max": 100, "default": 25},
    # Clarity: local midtone contrast (ffmpeg `cas`, Contrast Adaptive Sharpen). Unlike
    # `sharpness` (a fixed unsharp kernel), cas boosts local contrast without halos around
    # edges, which is what "clarity" means in a photo editor. 0 = off.
    "clarity": {"type": "int", "min": 0, "max": 100, "default": 0},
    "grain": {"type": "int", "min": 0, "max": 50, "default": 0},
    # Tone curve anchors (user feedback #3: "Rebuild contrast with a tone curve: anchor deep
    # blacks..., smooth the highlight shoulder"): piecewise-linear on BT.709 luma, anchors at
    # L=0->blacks, L=0.15->shadows, L=0.5->midtones, L=0.85->highlights, L=1->whites;
    # identity at the defaults.
    "tone_blacks": {"type": "number", "min": 0.0, "max": 2.0, "default": 0.0},
    "tone_shadows": {"type": "number", "min": 0.0, "max": 2.0, "default": 0.15},
    "tone_midtones": {"type": "number", "min": 0.0, "max": 2.0, "default": 0.5},
    "tone_highlights": {"type": "number", "min": 0.0, "max": 2.0, "default": 0.85},
    "tone_whites": {"type": "number", "min": 0.0, "max": 2.0, "default": 1.0},
}


def _hsv_fam_params() -> Dict[str, Dict[str, Any]]:
    """PHOTO_HSV: per-color-family HSL tweaks (user feedback #4: HSL greens/blues/reds...)."""
    out: Dict[str, Dict[str, Any]] = {}
    for fam in ("red", "orange", "yellow", "green", "cyan", "blue", "magenta"):
        out[f"{fam}_hue"] = {"type": "int", "min": -100, "max": 100, "default": 0,
                              "description": f"hue shift of the {fam} family (slider: -100..100 maps to -40..40 degrees)"}
        out[f"{fam}_saturation"] = {"type": "int", "min": -100, "max": 100, "default": 0,
                                    "description": f"saturation shift of the {fam} family (-100..100)"}
        out[f"{fam}_luminance"] = {"type": "int", "min": -100, "max": 100, "default": 0,
                                   "description": f"luminance shift of the {fam} family"}
    return out


PHOTO_HSV_PARAMS: Dict[str, Dict[str, Any]] = _hsv_fam_params()

# For the WHITE_BALANCE alias, the allowed parameter set at request level is restricted to
# white-balance fields: temperature + tint only (the alias is resolved to PHOTO_CORRECTION at
# validation, like the video skill's WHITE_BALANCE alias).
_WHITE_BALANCE_ALIAS_PARAMS: Dict[str, Dict[str, Any]] = {
    "white_balance_temperature": PHOTO_CORRECTION_PARAMS["white_balance_temperature"],
    "white_balance_tint": PHOTO_CORRECTION_PARAMS["white_balance_tint"],
}
ALIAS_PARAM_RESTRICTIONS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "WHITE_BALANCE": _WHITE_BALANCE_ALIAS_PARAMS,
    "PHOTO_WHITE_BALANCE": _WHITE_BALANCE_ALIAS_PARAMS,
}

# alias -> target operation type; when a request uses the alias, parameters are restricted
ALIAS_WHITE_BALANCE = ("PHITE_WHITE_BALANCE", "PHOTO_WHITE_BALANCE")
_PHOTO_WHITE_BALANCE_ALLOWED = {"white_balance_temperature", "white_balance_tint"}


@dataclass
class ColorSource:
    source_id: str
    path: str


@dataclass
class ColorOperation:
    op_id: str
    type: str                       # resolved type (aliases resolved to targets)
    input: str                      # "source" | "op:<id>"
    parameters: Dict[str, Any]


@dataclass
class ColorOutput:
    output_id: str
    operation: str                  # "source" | "op:<id>"
    path: str
    format: str


@dataclass
class ColorProject:
    project_id: str
    source: ColorSource
    operations: List[ColorOperation]
    outputs: List[ColorOutput]
    options: Dict[str, Any] = field(default_factory=dict)


def _validate_forbidden(doc: Any) -> None:
    """Every field name that could carry a command, filter string or executable is rejected
    anywhere in the document (same name set as the video skill)."""
    def walk(v: Any, path: str) -> None:
        if isinstance(v, dict):
            for k, sub in v.items():
                if k in FORBIDDEN_KEYS:
                    raise PhotoError("INVALID_REQUEST", f"field {k!r} is not allowed", {"path": path, "field": k})
                walk(sub, f"{path}.{k}")
        elif isinstance(v, list):
            for i, sub in enumerate(v):
                walk(sub, f"{path}[{i}]")
    if isinstance(doc, dict):
        walk(doc, "")


def _validate_unknown_fields(obj: Dict[str, Any], allowed: set, what: str, path: str) -> None:
    for k in obj:
        if k not in allowed:
            raise PhotoError("INVALID_REQUEST", f"unknown {what} field {k!r}", {"path": path, "field": k})


def _validate_outputs(outputs: Any, known: Dict[str, ColorOperation], op_index: Dict[str, ColorOperation]) -> List[ColorOutput]:
    if not isinstance(outputs, list) or not outputs:
        raise PhotoError("INVALID_REQUEST", "project.outputs must be a non-empty array", {})
    seen: Dict[str, None] = {}
    out: List[ColorOutput] = []
    for i, o in enumerate(outputs):
        if not isinstance(o, dict):
            raise PhotoError("INVALID_REQUEST", "each output must be an object", {"index": i})
        _validate_unknown_fields(o, {"output_id", "operation", "path", "format", "expect"}, "output", f"project.outputs[{i}]")
        oid = _check_id({}, o.get("output_id"), ID_RE, "output_id", f"project.outputs[{i}].output_id")
        if oid in seen:
            raise PhotoError("INVALID_REQUEST", f"duplicate output id {oid!r}", {"output_id": oid})
        seen[oid] = None
        ref = o.get("operation")
        if not isinstance(ref, str) or not REF_RE.match(ref):
            raise PhotoError("INVALID_REQUEST", "output.operation must match", {"path": f"project.outputs[{i}].operation", "got": ref})
        if ref != "source" and ref.split(":", 1)[1] not in op_index:
            raise PhotoError("MISSING_INPUT", f"output references undeclared operation {ref!r}", {"output_id": oid, "operation": ref})
        path_ = o.get("path")
        if not isinstance(path_, str) or not path_:
            raise PhotoError("INVALID_REQUEST", "output.path must be a non-empty string", {"index": i})
        fmt = o.get("format")
        if not isinstance(fmt, str) or fmt not in OUTPUT_FORMATS:
            raise PhotoError("UNSUPPORTED_FORMAT", f"output format must be one of {sorted(OUTPUT_FORMATS)}", {"format": fmt})
        import os
        ext = os.path.splitext(path_)[1].lower()
        if ext and OUTPUT_FORMATS[fmt]["extension"] not in (ext, ext.lower()):
            # allow "jpg" vs "JPEG"? no - extension must match the format exactly, except case-insensitively
            if ext != OUTPUT_FORMATS[fmt]["extension"]:
                raise PhotoError("UNSUPPORTED_FORMAT", f"output path extension {ext!r} does not match format {fmt!r}",
                                 {"path": path_, "format": fmt})
        out.append(ColorOutput(oid, ref, path_, fmt))
    return out


def parse_request(doc: Any) -> ColorProject:
    """Structural + semantic validation of a photo-grading request document."""
    if not isinstance(doc, dict):
        raise PhotoError("INVALID_REQUEST", "request document must be a JSON object", {})
    if doc.get("schema") != REQUEST_SCHEMA_ID:
        raise PhotoError("INVALID_REQUEST", f"schema must be {REQUEST_SCHEMA_ID!r}", {"got": doc.get("schema")})
    if set(doc) - {"schema", "project", "options"}:
        raise PhotoError("INVALID_REQUEST", "unknown top-level field", {"fields": sorted(set(doc) - {"schema", "project", "options"})})
    _validate_forbidden(doc)
    project = doc.get("project")
    if not isinstance(project, dict):
        raise PhotoError("INVALID_REQUEST", "project must be an object", {})
    _validate_unknown_fields(project, {"project_id", "source", "operations", "outputs", "options"}, "project", "project")
    pid = _check_id({}, project.get("project_id"), ID_RE, "project_id", "project.project_id")
    source = project.get("source")
    if not isinstance(source, dict):
        raise PhotoError("INVALID_REQUEST", "project.source must be an object", {})
    _validate_unknown_fields(source, {"source_id", "path"}, "source", "project.source")
    sid = _check_id({}, source.get("source_id"), ID_RE, "source_id", "project.source.source_id")
    path_ = source.get("path")
    if not isinstance(path_, str) or not path_:
        raise PhotoError("INVALID_INPUT", "source.path must be a non-empty string", {})

    ops_doc = project.get("operations")
    if not isinstance(ops_doc, list) or not ops_doc:
        raise PhotoError("INVALID_REQUEST", "project.operations must be a non-empty array", {})
    if len(ops_doc) > MAX_OPERATIONS:
        raise PhotoError("DEPENDENCY_ERROR", f"too many operations (max {MAX_OPERATIONS})", {})
    ops: List[ColorOperation] = []
    op_index: Dict[str, ColorOperation] = {}
    for i, o in enumerate(ops_doc):
        if not isinstance(o, dict):
            raise PhotoError("INVALID_REQUEST", "each operation must be an object", {"index": i})
        _validate_unknown_fields(o, {"op_id", "type", "input", "parameters"}, "operation", f"project.operations[{i}]")
        oid = _check_id({}, o.get("op_id"), ID_RE, "op_id", f"project.operations[{i}].op_id")
        if oid in op_index:
            raise PhotoError("DEPENDENCY_ERROR", f"duplicate op_id {oid!r}", {"op_id": oid})
        req_type = o.get("type")
        alias_restriction = ALIAS_PARAM_RESTRICTIONS.get(req_type)
        otype = OPERATION_ALIASES.get(req_type, req_type)
        if otype not in OPERATION_TYPES:
            raise PhotoError("UNSUPPORTED_OPERATION", f"operation type must be one of {sorted(OPERATION_TYPES)}",
                             {"type": req_type})
        ref = o.get("input")
        if not isinstance(ref, str) or not REF_RE.match(ref):
            raise PhotoError("MISSING_INPUT", "operation.input must match (source|op:<id>)", {"op_id": oid, "input": ref})
        if ref != "source" and ref.split(":", 1)[1] not in op_index:
            raise PhotoError("MISSING_INPUT", f"operation references undeclared operation {ref!r}", {"op_id": oid, "input": ref})
        params = o.get("parameters", {})
        if alias_restriction is not None:
            allowed = alias_restriction
        elif otype == "PHOTO_GRADING":
            allowed = PHOTO_GRADING_PARAMS
        elif otype == "PHOTO_CORRECTION":
            allowed = PHOTO_CORRECTION_PARAMS
        elif otype == "PHOTO_HSV":
            allowed = PHOTO_HSV_PARAMS
        else:  # PHOTO_LUT_APPLY
            allowed = {"lut_path": {"type": "string", "required": True, "default": None},
                       "strength": {"type": "number", "min": 0.0, "max": 1.0, "default": 1.0}}
        if otype != "PHOTO_LUT_APPLY":
            _validate_params(params, allowed)
        else:
            # LUT path: required string, .cube extension only
            _validate_params(params, allowed)
            if not isinstance(params.get("lut_path"), str) or not params["lut_path"]:
                raise PhotoError("INVALID_REQUEST", "parameter lut_path is required", {"path": "operations[].parameters.lut_path"})
            if not params["lut_path"].lower().endswith(".cube"):
                raise PhotoError("UNSUPPORTED_FORMAT", "LUT must be a .cube file", {"lut_path": params["lut_path"]})
        if otype == "PHOTO_LUT_APPLY" and set(params) - {"lut_path", "strength"}:
            raise PhotoError("INVALID_REQUEST", f"PHOTO_LUT_APPLY takes no other parameters (got {sorted(set(params) - {'lut_path', 'strength'})})", {})
        ops.append(ColorOperation(oid, otype, ref, dict(params)))
        op_index[oid] = ops[-1]

    outputs = _validate_outputs(project.get("outputs"), None, op_index)
    # every output must reference a photo input reachable via operations on one source
    for out in outputs:
        if out.operation != "source" and out.operation.split(":", 1)[1] not in op_index:
            raise PhotoError("MISSING_INPUT", f"output references undeclared operation {out.operation!r}", {"output_id": out.output_id})
    project_options = project.get("options", {})
    if not isinstance(project_options, dict):
        raise PhotoError("INVALID_REQUEST", "project.options must be an object", {})
    _validate_unknown_fields(project_options, {"reuse_intermediates", "timeout", "overwrite"}, "options", "project.options")
    if "reuse_intermediates" in project_options and not isinstance(project_options["reuse_intermediates"], bool):
        raise PhotoError("INVALID_REQUEST", "options.reuse_intermediates must be a boolean", {})
    if "overwrite" in project_options and not isinstance(project_options["overwrite"], bool):
        raise PhotoError("INVALID_REQUEST", "options.overwrite must be a boolean", {})
    if "timeout" in project_options:
        v = project_options["timeout"]
        if not _is_num(v) or v < 1 or v > 7200:
            raise PhotoError("INVALID_REQUEST", "options.timeout must be a number in [1, 7200]", {"got": v})
    options = {"reuse_intermediates": bool(project_options.get("reuse_intermediates", True)),
               "timeout": float(project_options.get("timeout", 600)), "overwrite": bool(project_options.get("overwrite", False))}
    return ColorProject(pid, ColorSource(sid, path_), ops, outputs, options)
