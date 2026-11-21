"""photo-grading CLI.

stdout: with --json exactly one JSON document (contract / doctor / response), on success and failure alike.
stderr: diagnostics only. Exit code: 0 on success, otherwise errors.EXIT_CODES[error.code].

  photo-grading skill --json               contract (alias: contract --json)
  photo-grading doctor --json              environment diagnosis
  photo-grading validate - --json          validate a request document, run nothing
  photo-grading plan - --json              dry run: plan without writing media
  photo-grading run - --json [--dry-run]   execute a request document
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
from typing import Any, List, Optional

from . import PACKAGE_NAME, SKILL_ID, VERSION
from .contract import skill_contract
from .doctor import doctor_report
from .errors import EXIT_CODES, PhotoError
from .executor import Executor
from .model import parse_request
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


def _human(doc: dict) -> None:
    if not doc.get("ok", True) and doc.get("error"):
        e = doc["error"]
        sys.stderr.write(f"error [{e['code']}]: {e['message']}" + (f" {json.dumps(e.get('details'))}" if e.get("details") else "") + "\n")
    if "results" in doc:
        for r in doc["results"]:
            art = r.get("measurements", {}).get("output") or {}
            print(f"{r['operation_id']:12} {r['type']:18} {r['status']:10} reused={r.get('reused', False)} "
                  f"{art.get('width')}x{art.get('height')} sha={str(r.get('output_hash'))[:12]}")
        for o in doc.get("outputs", []):
            print(f"output {o['output_id']}: {o.get('status', 'planned')} {o.get('path')}")
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
