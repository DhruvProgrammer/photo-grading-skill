"""photo-grading CLI.

stdout: with --json exactly one JSON document (contract / doctor / response), on success and failure alike.
stderr: diagnostics only. Exit code: 0 on success, otherwise errors.EXIT_CODES[error.code].

  photo-grading skill --json               contract (alias: contract --json)
  photo-grading doctor --json              environment diagnosis
  photo-grading validate - --json          validate a request document, run nothing
  photo-grading plan - --json              dry run: plan without writing media
  photo-grading run - --json [--dry-run]   execute a request document
  photo-grading inspect IMAGE --json       objective pixel statistics (clipping, saturation, cast)
  photo-grading analyze IMAGE --json       OKLab report: exposure, contrast, cast, M3, tint, skin
  photo-grading score IMAGE --target T --json   score against a caller-supplied look (numbers)
  photo-grading optimize IMAGE --target T --out FILE --json   critic loop, LUT render, report
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
from pathlib import Path
from typing import Any, List, Optional

from . import PACKAGE_NAME, SKILL_ID, VERSION
from . import critic
from .contract import skill_contract
from .doctor import doctor_report
from .errors import EXIT_CODES, PhotoError
from .executor import Executor
from .model import OUTPUT_FORMATS, parse_request
from .quality import inspect_image
from .security import PathPolicy


def _add_common(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--json", action="store_true", help="machine-readable JSON on stdout (exactly one document)")


def _add_run_opts(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("request", help="path to a request document, or - for stdin")
    ap.add_argument("--workspace", help="directory writes are confined to (default: current directory)")
    ap.add_argument("--timeout", type=float, default=600.0, help="seconds per tool invocation (default 600)")
    ap.add_argument("--no-reuse", action="store_true", help="do not reuse intermediates with a matching operation id")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="photo-grading",
                                 description=f"{PACKAGE_NAME} {VERSION}: deterministic photo color grading "
                                             "and photo corrections (not an AI agent)")
    ap.add_argument("--version", action="version", version=f"{PACKAGE_NAME} {VERSION}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("skill", "contract"):
        c = sub.add_parser(name, help="print the Skill contract")
        _add_common(c)
    d = sub.add_parser("doctor", help="diagnose the environment against the contract")
    d.add_argument("--workspace")
    _add_common(d)
    i = sub.add_parser("inspect", help="objective pixel statistics of a photo (clipping, saturation, cast)")
    i.add_argument("image")
    _add_common(i)
    a = sub.add_parser("analyze", help="OKLab report of a photo (no score, no target)")
    a.add_argument("image")
    a.add_argument("--reference", help="original image to measure deltas against (default: the image itself)")
    a.add_argument("--max-pixels", type=int, default=critic.DEFAULT_MAX_PIXELS)
    a.add_argument("--workspace")
    _add_common(a)
    s = sub.add_parser("score", help="score a photo against a caller-supplied target look")
    s.add_argument("image")
    s.add_argument("--target", required=True, help="target look JSON file, or - for stdin")
    s.add_argument("--reference", help="original image to measure deltas against (default: the image itself)")
    s.add_argument("--max-pixels", type=int, default=critic.DEFAULT_MAX_PIXELS)
    s.add_argument("--workspace")
    _add_common(s)
    o = sub.add_parser("optimize", help="run the deterministic critic loop and render the winning LUT")
    o.add_argument("image")
    o.add_argument("--target", required=True, help="target look JSON file, or - for stdin")
    o.add_argument("--out", required=True, help="graded output path (format from the extension)")
    o.add_argument("--lut-out", help="also copy the generated .cube LUT here")
    o.add_argument("--iterations", type=int, default=critic.DEFAULT_ITERATIONS,
                   help=f"coordinate-descent sweeps (default {critic.DEFAULT_ITERATIONS})")
    o.add_argument("--proxy-size", type=int, default=critic.DEFAULT_PROXY_SIZE)
    o.add_argument("--lut-size", type=int, default=critic.DEFAULT_LUT_SIZE, choices=list(critic.LUT_SIZES))
    o.add_argument("--workspace")
    o.add_argument("--timeout", type=float, default=600.0)
    o.add_argument("--overwrite", action="store_true", help="allow replacing an existing output")
    _add_common(o)
    v = sub.add_parser("validate", help="validate a request document; runs nothing, reads no media")
    v.add_argument("request")
    _add_common(v)
    p = sub.add_parser("plan", help="dry run: plan without writing media")
    _add_run_opts(p)
    _add_common(p)
    r = sub.add_parser("run", help="execute a request document")
    _add_run_opts(r)
    r.add_argument("--dry-run", action="store_true", help="same as plan")
    _add_common(r)
    return ap


def _read_document(spec: str) -> Any:
    try:
        text = sys.stdin.read() if spec == "-" else open(spec, "r", encoding="utf-8").read()
    except OSError as e:
        raise PhotoError("INVALID_REQUEST", f"cannot read request document: {e}")
    if len(text) > 16 * 1024 * 1024:
        raise PhotoError("INVALID_REQUEST", "request document is larger than 16 MiB")
    try:
        return json.loads(text)
    except ValueError as e:
        raise PhotoError("INVALID_REQUEST", f"request document is not valid JSON: {e}")


def _read_target(spec: str) -> Any:
    """Read a target look as a JSON object: six numbers, no look name."""
    try:
        text = sys.stdin.read() if spec == "-" else open(spec, "r", encoding="utf-8").read()
    except OSError as e:
        raise PhotoError("INVALID_REQUEST", f"cannot read target document: {e}")
    try:
        return json.loads(text)
    except ValueError as e:
        raise PhotoError("INVALID_REQUEST", f"target document is not valid JSON: {e}")


def _optimize_command(args) -> dict:
    """Run PHOTO_OPTIMIZE through the normal executor path: validation, LUT render, report."""
    policy = PathPolicy(args.workspace, overwrite=args.overwrite)
    src = policy.check_input(args.image, "input")
    ext = Path(args.out).suffix.lower()
    fmt = ext.lstrip(".")
    if fmt not in OUTPUT_FORMATS:
        raise PhotoError("UNSUPPORTED_FORMAT", f"output format must be one of {sorted(OUTPUT_FORMATS)}",
                         {"out": args.out})
    target = _read_target(args.target)
    document = {
        "schema": "photo-grading/request@1",
        "project": {
            "project_id": "optimize",
            "options": {"overwrite": bool(args.overwrite), "timeout": float(args.timeout)},
            "source": {"source_id": "source", "path": str(src)},
            "operations": [{"op_id": "opt", "type": "PHOTO_OPTIMIZE", "input": "source",
                            "parameters": {"target": target, "iterations": args.iterations,
                                           "proxy_size": args.proxy_size, "lut_size": args.lut_size}}],
            "outputs": [{"output_id": "optimized", "operation": "op:opt", "path": args.out, "format": fmt}],
        },
    }
    project = parse_request(document)
    executor = Executor(policy, timeout=project.options["timeout"])
    install_cancel_handlers(executor)
    doc = executor.response(project, dry_run=False)
    if doc.get("ok") and args.lut_out:
        report = doc["results"][0].get("report") or {}
        lut = report.get("lut") or {}
        if not lut.get("path"):
            raise PhotoError("OUTPUT_ERROR", "the optimize report did not produce a LUT", {})
        lut_out = policy.check_output(args.lut_out, [])
        lut_out.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(lut["path"], lut_out)
        doc["lut"] = {"path": str(lut_out), "sha256": lut.get("sha256")}
    return doc


def _error_document(e: PhotoError, dry_run: bool) -> dict:
    return {"schema": f"{SKILL_ID}/response@1", "skill": {"id": SKILL_ID, "version": VERSION}, "ok": False,
            "status": "cancelled" if e.code == "CANCELLED" else "error", "dry_run": dry_run,
            "error": e.to_dict(), "warnings": []}


def _emit(doc: dict, as_json: bool) -> None:
    if as_json:
        sys.stdout.write(json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    else:
        _human(doc)
    sys.stdout.flush()


def _print_report(rep: dict) -> None:
    kind = rep.get("kind")
    if kind == "analyze":
        m = rep["metrics"]
        print(f"OKLab median L {m['median_L']:.3f}  spread {m['spread_p95_p5']:.3f}  "
              f"clip hi {m['white_clip_pct']:.2f}% lo {m['black_clip_pct']:.2f}%  "
              f"M3 {m['colorfulness_m3']:.1f}  cast a {m['cast_a']:+.3f} b {m['cast_b']:+.3f}  "
              f"skin shift {m['skin_hue_shift_deg']:.2f} deg")
    elif kind in ("score", "optimize"):
        if kind == "score":
            print(f"score {rep['score']:.2f}/100 (penalty {rep['total_penalty']:+.2f})")
            parts = rep.get("parts", {})
        else:
            print(f"score {rep['score_before']:.2f} -> {rep['score_after']:.2f}/100  "
                  f"params {json.dumps(rep.get('params', {}))}")
            print(f"lut {rep.get('lut', {}).get('size')}^3 {rep.get('lut', {}).get('path')}")
            parts = rep.get("parts_after", {})
        for name, part in parts.items():
            if abs(part.get("penalty", 0.0)) > 0.0001:
                print(f"  {name:14} {part['penalty']:+8.2f}  measured {part.get('measured')} "
                      f"target {part.get('target')}")


def _human(doc: dict) -> None:
    if not doc.get("ok", True) and doc.get("error"):
        e = doc["error"]
        sys.stderr.write(f"error [{e['code']}]: {e['message']}" + (f" {json.dumps(e.get('details'))}" if e.get("details") else "") + "\n")
    if "results" in doc:
        for r in doc["results"]:
            art = r.get("measurements", {}).get("output") or {}
            print(f"{r['operation_id']:12} {r['type']:18} {r.get('status', 'completed'):10} reused={r.get('reused', False)} "
                  f"{art.get('width')}x{art.get('height')} sha={str(r.get('output_hash'))[:12]}")
            if r.get("report"):
                _print_report(r["report"])
        for o in doc.get("outputs", []):
            print(f"output {o['output_id']}: {o.get('status', 'planned')} {o.get('path')}")
    elif doc.get("kind") in ("analyze", "score"):
        _print_report(doc)
        for w in doc.get("warnings", []):
            print(f"warning: {w}")
    elif "validation" in doc:
        print(f"validation: ok ({[o.type for o in doc['validation']['project'].operations]})")
    elif "checks" in doc:
        print(f"{PACKAGE_NAME} {VERSION}: {doc['status']}")
        for k in ("ffmpeg", "ffprobe"):
            print(f"{k}: {doc['checks'][k]['status']} {doc['checks'][k].get('version') or ''}")
        for name, o in doc["checks"]["operations"].items():
            print(f"  {name:14} {o['status']:10} {o['required']}" + (f"  missing: {o['missing']}" if o.get("missing") else ""))
        for p in doc["problems"]:
            print(f"problem: {p}")
    elif "metrics" in doc:
        m = doc["metrics"]
        print(f"{m['width']}x{m['height']} {m['pix_fmt']}  luma mean {m['mean_luma']:.1f} "
              f"p05 {m['luma_p05']:.1f} p95 {m['luma_p95']:.1f}  "
              f"clip hi {m['highlight_clip_pct']:.2f}% lo {m['shadow_clip_pct']:.2f}%  "
              f"sat mean {m['mean_saturation']:.1f} p95 {m['p95_saturation']:.1f}  "
              f"neon {m['neon_pct']:.2f}%  neutral cast R-G {m['neutral_cast_r_minus_g']:+.1f} B-G {m['neutral_cast_b_minus_g']:+.1f}")
        for w in doc.get("warnings", []):
            print(f"warning: {w}")
    elif "operations" in doc:
        print(f"{doc['skill_id']} {doc['version']}: " + ", ".join(o["type"] for o in doc["operations"]))


def install_cancel_handlers(executor: Executor) -> None:
    """SIGINT / SIGTERM (SIGBREAK on Windows) cancel the run: the handler only asks the executor
    to cancel; it kills the running tool and the executor stops at its next checkpoint."""
    def _cancel(signum: int, frame: Any) -> None:
        executor.cancel()

    for sig in [signal.SIGINT, signal.SIGTERM] + ([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else []):
        try:
            signal.signal(sig, _cancel)
        except (ValueError, OSError):
            pass


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    as_json = bool(getattr(args, "json", False))
    if args.cmd in ("skill", "contract"):
        _emit(skill_contract(), as_json)
        return 0
    if args.cmd == "doctor":
        doc = doctor_report(args.workspace)
        _emit(doc, as_json)
        return 0 if doc["status"] != "fail" else 1
    if args.cmd == "inspect":
        try:
            doc = inspect_image(args.image)
        except PhotoError as e:
            doc = _error_document(e, False)
        _emit(doc, as_json)
        if doc.get("ok"):
            return 0
        return EXIT_CODES.get((doc.get("error") or {}).get("code", "INTERNAL_ERROR"), EXIT_CODES["INTERNAL_ERROR"])
    if args.cmd in ("analyze", "score", "optimize"):
        try:
            if args.cmd in ("analyze", "score"):
                policy = PathPolicy(args.workspace)
                src = policy.check_input(args.image, "input")
                ref = str(policy.check_input(args.reference, "reference")) if args.reference else None
                if args.cmd == "analyze":
                    doc = critic.analyze_file(str(src), ref, args.max_pixels)
                else:
                    doc = critic.score_file(str(src), _read_target(args.target), ref, args.max_pixels)
            else:
                doc = _optimize_command(args)
        except PhotoError as e:
            doc = _error_document(e, False)
        except Exception as e:
            doc = _error_document(PhotoError("INTERNAL_ERROR", f"unexpected error ({type(e).__name__}): {e}"), False)
        _emit(doc, as_json)
        if doc.get("ok"):
            return 0
        return EXIT_CODES.get((doc.get("error") or {}).get("code", "INTERNAL_ERROR"), EXIT_CODES["INTERNAL_ERROR"])
    dry_run = args.cmd == "plan" or bool(getattr(args, "dry_run", False))
    try:
        document = _read_document(args.request)
        if args.cmd == "validate":
            project = parse_request(document)
            doc = {"schema": f"{SKILL_ID}/response@1", "skill": {"id": SKILL_ID, "version": VERSION},
                   "ok": True, "status": "ok", "dry_run": True,
                   "validation": {"ok": True, "project": {"project_id": project.project_id,
                                  "source": project.source.source_id,
                                  "operations": [o.type for o in project.operations]}}, "warnings": []}
        else:
            project = parse_request(document)
            if getattr(args, "no_reuse", False):
                # --no-reuse was parsed but never applied: it must disable intermediate reuse.
                project.options["reuse_intermediates"] = False
            policy = PathPolicy(args.workspace, overwrite=project.options["overwrite"])
            executor = Executor(policy, timeout=project.options["timeout"])
            install_cancel_handlers(executor)
            doc = executor.response(project, dry_run=dry_run)
    except PhotoError as e:
        doc = _error_document(e, dry_run)
    except Exception as e:
        doc = _error_document(PhotoError("INTERNAL_ERROR", f"unexpected error ({type(e).__name__}): {e}"), dry_run)
    _emit(doc, as_json)
    if doc.get("ok"):
        return 0
    return EXIT_CODES.get((doc.get("error") or {}).get("code", "INTERNAL_ERROR"), EXIT_CODES["INTERNAL_ERROR"])


if __name__ == "__main__":
    sys.exit(main())
