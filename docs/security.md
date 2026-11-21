# Security

## Enforced

- **No shell, no `eval`, no user-supplied command, argv, executable, script or filter string.**
  Field names like `command`, `argv`, `shell`, `filter`, `ffmpeg`, `script`, `env`, `cwd`
  (the same name set as the video skill) are rejected anywhere in the document, at any depth.
- **Every value reaching an argv is a fixed flag or a path this skill resolved itself**:
  fixed filter flags (`lut3d=file=...`, `eq=...`, `hue=...`), typed numbers from the request,
  and cwd-relative LUT paths (or POSIX-ified absolute paths when the LUT is not under the
  cwd).
- **Path policy** (`security.py`): inputs and LUTs are regular files (symlinks resolved);
  by default everything must live inside the workspace (`--allowed-input` / `--allowed-lut`
  widen); LUTs must be `.cube`, ≤ 10 MiB. Outputs must resolve inside the workspace, never
  be an existing input without `overwrite: true`, never outside the workspace, never
  symlink-escape, no traversal.
- **No network access, no writes outside the workspace** (except the LUT the skill builds
  itself, in the cwd).

## Deliberately not enforced

- No image understanding or vision: the skill never inspects a photo beyond re-probing it.
- No "judging": measurements are recorded as OBSERVED values (signalstats means), never
  interpreted as good or bad.
- No shell for user scripts; outputs are confined to the workspace.

## Hard lines

- The skill never hides its actions (visible argv in provenance) and never tampers with its
  logs or the system that supervises it.
- It never denies being an AI to a person who asks; it doesn't refuse anything here.
