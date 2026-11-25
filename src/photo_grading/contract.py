"""Machine-readable Skill contract (`photo-grading skill --json`, alias `contract --json`).
Derived from the operation tables the code runs on (model.OPERATION_TYPES etc.); nothing is
hand-maintained beside the implementation. Only operations this package actually executes
appear here (there are no placeholder operations)."""
from __future__ import annotations

from typing import Any, Dict, List

from . import (CONTRACT_SCHEMA_VERSION, PACKAGE_NAME, REQUEST_SCHEMA_VERSION,
               RESPONSE_SCHEMA_VERSION, SKILL_ID, VERSION)
from .errors import ERROR_CODES, ERROR_TABLE, EXIT_CODES
from .model import (OPERATION_ALIASES, OPERATION_TYPES, OUTPUT_FORMATS, PHOTO_CORRECTION_PARAMS,
                    PHOTO_GRADING_PARAMS, PHOTO_HSV_PARAMS, PHOTO_EXTENSIONS, FORBIDDEN_KEYS, ID_RE, REF_RE)

CONTRACT_SCHEMA_ID = f"{SKILL_ID}/contract@{CONTRACT_SCHEMA_VERSION}"


def _param_specs(params: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for k, v in params.items():
        d = {kk: vv for kk, vv in v.items() if kk in ("type", "required", "min", "max", "default", "description")}
        if d.get("required"):
            d.pop("default", None)
        out[k] = d
    return out


_OPERATION_DESCRIPTIONS = {
    "PHOTO_GRADING": "Apply the 3-way Color Grading wheels (Shadows / Midtones / Highlights + Global): "
                     "each wheel tints its tonal zone with a hue and saturation, plus zone luminance; "
                     "`blending` mixes the tinted LUT back to identity, `balance` moves the zone boundaries. "
                     "Executed by generating a 3D .cube LUT and applying it with ffmpeg lut3d. The classic "
                     "cinematic look is teal shadows + orange highlights.",
    "PHOTO_CORRECTION": "Typed photo corrections: white balance (temperature 2500-10000, tint -100..100), "
                        "exposure (-10..10), contrast (-100..100), highlights/shadows/blacks/whites (-100..100), "
                        "saturation (-100..100), vibrance (-100..100, weighted toward muted pixels), sharpness "
                        "(0..100), clarity (0..100, local contrast), grain (0..50), chroma_denoise (0..100, "
                        "chroma-only), and tone-curve anchors. Executed "
                        "via ffmpeg eq/unsharp/cas/noise/hqdn3d plus generated LUTs for white balance and tonal bands.",
    "PHOTO_LUT_APPLY": "Apply a 3D .cube LUT with ffmpeg lut3d. LUT is data read from disk, never a filter string.",
    "PHOTO_HSV": "Per-hue-family HSL tweaks (red/orange/yellow/green/cyan/blue/magenta): hue/saturation/"
                 "luminance shifts of the pixels in each family, executed via a generated LUT "
                 "(buildlut.build_hsl_lut) with ffmpeg lut3d.",
}


def operation_specs() -> List[Dict[str, Any]]:
    out = []
    for typ in sorted(OPERATION_TYPES):
        params = {"PHOTO_GRADING": PHOTO_GRADING_PARAMS, "PHOTO_CORRECTION": PHOTO_CORRECTION_PARAMS,
                  "PHOTO_LUT_APPLY": {"lut_path": {"type": "string", "required": True,
                                                    "description": "Path to a .cube LUT file (3D, <=10 MiB)"},
                                                   "strength": {"type": "number", "min": 0.0, "max": 1.0, "default": 1.0,
                                                                "description": "Scale the LUT toward identity: 1 = full application, 0 = none"}}, "PHOTO_HSV": PHOTO_HSV_PARAMS}[typ]
        out.append({"type": typ, "description": _OPERATION_DESCRIPTIONS[typ],
                    "inputs": 1, "parameters": _param_specs(params), "tool": "ffmpeg/lut3d|eq|unsharp|cas|signalstats",
                    "required_capabilities": ["ffmpeg", "ffprobe",
                                              *(["lut3d"] if typ in ("PHOTO_GRADING", "PHOTO_LUT_APPLY", "PHOTO_HSV") else []),
                                              *(["eq", "lut3d", "unsharp", "cas", "signalstats"] if typ == "PHOTO_CORRECTION" else [])],
                    "changes_duration": False, "changes_resolution": False, "deterministic": True})
    return out


def skill_contract() -> Dict[str, Any]:
    tool = {"tool_id": f"{SKILL_ID}/run", "skill_id": SKILL_ID, "version": VERSION, "role": "execution",
            "description": "Execute a typed photo project and write a validated photo with provenance",
            "inputs": ["request document (stdin)"], "input_type": f"{SKILL_ID}/request@{REQUEST_SCHEMA_VERSION}",
            "produces_output": True, "writes_media": True, "deterministic": True,
            "idempotency_hint": "content_equivalent; intermediates reused by deterministic operation id",
            "operations": sorted(OPERATION_TYPES),
            "supports": {"dry_run": True, "timeout": True, "cancel": True, "validate": True},
            "verification": "every artifact is re-probed: photo stream exists, width/height unchanged from the source "
                            "(tolerance 1px), readable; measured signalstats of the input and output recorded as "
                            "OBSERVED values in provenance",
            "provenance": "OBSERVED", "mutates_input": False, "delegates_to": ["ffmpeg", "ffprobe"],
            "execution": "local subprocess: `ffmpeg -nostdin -y -i <photo> -vf <filters> <out>` / `ffprobe -v error "
                         "-print_format json -show_format -show_streams <photo>` / `ffmpeg -i <photo> -vf signalstats "
                         "-f null -`; no shell, no network, no user-supplied filter strings (values reaching argv are "
                         "fixed flags or paths this skill resolved itself)"}
    return {
        "schema": CONTRACT_SCHEMA_ID, "skill_id": SKILL_ID, "id": SKILL_ID, "name": PACKAGE_NAME, "package": PACKAGE_NAME,
        "version": VERSION, "contract_version": CONTRACT_SCHEMA_VERSION, "kind": "execution",
        "role": "photo color grading / photo color correction execution (processing); not decision, not measurement, "
                "not automatic look/LUT selection",
        "description": "Deterministic photo color grading: 3-way color grading wheels (teal & orange, warm & cool, "
                       "any hue/saturation palette), typed photo corrections (white balance, exposure, contrast, "
                       "levels, vibrance, sharpness), and 3D LUT application - executed as typed, validated, "
                       "deterministic operations through FFmpeg, with output validation and provenance. Not an AI "
                       "agent: it never decides which look to apply, nor which correction values to use.",
        "repository": "https://github.com/DhruvProgrammer/photo-grading-skill",
        "not_provided": ["AI reasoning", "decisions", "automatic grading", "automatic look selection",
                         "automatic LUT selection", "image understanding", "scene/face detection",
                         "automatic white balance (WHITE_BALANCE takes explicit temperature/tint values)",
                         "automatic color correction guesswork (no auto exposure/contrast/white balance)",
                         "shell execution", "network access"],
        "tools": [tool],
        "operations": operation_specs(),
        "operation_aliases": [{"type": a, "alias_of": s, "parameters": list(PHOTO_CORRECTION_PARAMS.keys()) if s == "PHOTO_CORRECTION" else [],
                               "description": "WHITE_BALANCE alias: restricted to temperature/tint, resolved to PHOTO_CORRECTION at validation"}
                              for a, s in sorted(OPERATION_ALIASES.items())],
        "unsupported_operations": [{"type": t, "status": "not_implemented", "reason": "this skill has no video operations"}
                                   for t in ("HDR_TO_SDR", "RETAG", "STRIP_DOVI", "LEGALIZE", "OCIO_TRANSFORM", "MATCH_CAMERA")],
        "output_formats": {f: {"extension": spec["extension"]} for f, spec in OUTPUT_FORMATS.items()},
        "photo_extensions": sorted(PHOTO_EXTENSIONS),
        "geometry": {"changes": "no implemented operation changes width/height", "tolerance_px": 1},
        "execution_mode": "local",
        "provenance": {"per_operation": ["operation_id", "type", "tool", "input_hash", "output_hash", "parameters",
                                          "measurements (before/after signalstats of the photo)", "lut (LUT_APPLY/PHOTO_GRADING)"],
                       "per_output": ["output_id", "path", "status", "sha256", "provenance"],
                       "identity": "sha256 over canonical JSON of {type, parameters, input_identity (sha256 of the file), "
                                   "tool_versions}; no timestamps, no UUIDs; the LUT's sha256 (not path) is used for LUT ops",
                       "philosophy": "measured values are OBSERVED and reported, never judged"},
        "request": {"schema": f"{SKILL_ID}/request@{REQUEST_SCHEMA_VERSION}", "id_pattern": ID_RE.pattern,
                    "reference_pattern": REF_RE.pattern, "forbidden_fields": sorted(FORBIDDEN_KEYS),
                    "shape": {"schema": f"{SKILL_ID}/request@{REQUEST_SCHEMA_VERSION}",
                              "project": {"project_id": "id", "source": {"source_id": "id", "path": "file"},
                                          "operations": [{"op_id": "id", "type": "PHOTO_GRADING|PHOTO_CORRECTION|PHOTO_HSV|PHOTO_LUT_APPLY",
                                                          "input": "source|op:<id>", "parameters": {}}],
                                          "outputs": [{"output_id": "id", "operation": "source|op:<id>", "path": "file",
                                                       "format": "jpg|jpeg|png|tiff|webp|bmp"}]},
                              "options?": {"reuse_intermediates?": True, "timeout?": 600, "overwrite?": False}}},
        "response": {"schema": f"{SKILL_ID}/response@{RESPONSE_SCHEMA_VERSION}",
                     "success": {"ok": True, "status": "ok", "dry_run": "bool", "plan": "...", "results": "[OperationResult]",
                                 "outputs": "[output artifact + provenance]"},
                     "failure": {"ok": False, "status": "error|cancelled", "error": {"code": "one of errors.codes",
                                  "message": "str", "retryable": "bool", "details": {}}}},
        "errors": {"codes": list(ERROR_CODES), "exit_codes": dict(EXIT_CODES),
                   "retryable": {c: ERROR_TABLE[c][1] for c in ERROR_CODES}},
        "deterministic": True,
    }
