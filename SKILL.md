---
name: photo-grading
description: Deterministic photo color grading / photo color correction execution Skill for AI photo agents. Use it when a caller has decided which color treatment to apply to a photo and needs it executed safely: the 3-way Color Grading wheels (Shadows / Midtones / Highlights + Global: hue, saturation, luminance per wheel; blending; balance), typed photo corrections (white balance temperature/tint, exposure, contrast, highlights/shadows/blacks/whites, saturation, vibrance, tone curve, sharpness, clarity, grain), per-hue-family HSL (PHOTO_HSV), or 3D LUT application (PHOTO_LUT_APPLY). Also measures a photo in OKLab (PHOTO_ANALYZE), scores it against a caller-supplied numeric target look (PHOTO_SCORE), and runs a deterministic critic/optimizer that bakes the winning grade into a LUT (PHOTO_OPTIMIZE). Executed as typed, deterministic operations through FFmpeg's photo filters (lut3d, eq, unsharp, cas), with output validation, objective inspection and provenance. Do NOT use it to decide which color treatment or look to apply, to judge a photo "cinematic", or to run arbitrary ffmpeg filters. The critic measures distance to a target the caller supplies; that is measurement, not judgment. WHITE_BALANCE is an alias of PHOTO_CORRECTION restricted to temperature/tint.
---

# photo-grading

Machine interface: `photo-grading run - --json` with a `photo-grading/request@1` document on
stdin; exactly one `photo-grading/response@1` document on stdout. `photo-grading skill --json`
prints the contract; `doctor --json` the environment; `plan - --json` a dry run;
`validate - --json` a schema check; `inspect IMAGE --json` objective pixel statistics
(clipping, saturation, neon share, neutral-pixel white-balance cast) + warnings;
`analyze IMAGE --json` an OKLab report; `score IMAGE --target TARGET --json` a score against
a caller-supplied target; `optimize IMAGE --target TARGET --out FILE --json` the critic loop
plus a full-size LUT render. The last three need `pip install -e ".[critic]"`.

Rules for a calling agent:
1. Decide first: which operation, which look (the caller already did this). This skill has
   no defaults for creative parameters: wheels/parameters come from the request.
2. Give explicit, typed parameters; each is independently optional unless marked required,
   range-checked, and "unchanged" when omitted. `PHOTO_GRADING`: `shadows_hue/shadows_saturation/shadows_luminance`,
   `midtones_*`, `highlights_*`, `global_*` (hue 0-360, saturation 0-100, luminance -100..100),
   `blending` (0-100, default 50), `balance` (-100..100, default 0). `PHOTO_CORRECTION`:
   `white_balance_temperature` (2500-10000, default 6500), `white_balance_tint` (-100..100),
   `exposure` (-10..10), `contrast` (-100..100), `highlights`/`shadows`/`blacks`/`whites`
   (-100..100), `saturation` (-100..100), `vibrance` (-100..100), `sharpness` (0..100),
   `clarity` (0..100), `grain` (0..50), `chroma_denoise` (0..100, chroma-only), `tone_blacks`/`tone_shadows`/`tone_midtones`/
   `tone_highlights`/`tone_whites` (0..2). `PHOTO_HSV`: `red_*`/`orange_*`/`yellow_*`/`green_*`/
   `cyan_*`/`blue_*`/`magenta_*` with `_hue` (-100..100 = -40..40 degrees), `_saturation`
   (-100..100), `_luminance` (-100..100). `PHOTO_LUT_APPLY`: `lut_path` (required), `strength` (0..1).
   `PHOTO_ANALYZE`: `max_pixels`. `PHOTO_SCORE`: `target` + `max_pixels`. `PHOTO_OPTIMIZE`:
   `target`, `iterations` (default 40), `proxy_size` (default 384), `lut_size` (17/33/65, default 33).
   Prefer `vibrance` over `saturation` for "make it vibrant": it protects already-saturated
   pixels and leaves low-chroma texture alone.
3. Never send commands, argv, filter strings or executable paths: the request is rejected.
4. Keep outputs inside the workspace, never at the input path; set `overwrite: true`
   deliberately. This skill never mutates inputs.
5. Read `doc.status`, `results[].report`, `outputs[].status` and `error` from the JSON; exit
   code 0 only when `ok` is true.
6. Measurements (signalstats means, OKLab reports) are OBSERVED values; report what you saw.
7. Verify the result with `photo-grading inspect IMAGE --json` and, when you have a target,
   `photo-grading score IMAGE --target TARGET --reference SOURCE --json`: compare clipping,
   saturation, neon share and neutral-pixel cast against the source, and read every penalty
   term. A grade should not add highlight clipping or a neutral-pixel cast, and should not
   raise the neon share.

Critic rules (PHOTO_ANALYZE / PHOTO_SCORE / PHOTO_OPTIMIZE):
- A target look is six required numbers: `shadow_hue`, `highlight_hue`, `tint_mag`,
  `colorfulness`, `median_L`, `spread`. No look names, no presets.
- Hue is an OKLab hue angle (0 = red/magenta, 90 = yellow, 180 = green, 270 = blue; teal
  ~200, orange ~55). It is absolute, not the wheel's hue rotation; do not copy wheel values.
- The score is 100 + penalties against the target, plus skin-hue and overcooked guards. It is
  a distance, not a quality rating. A strong look can score below 100 by design.
- `PHOTO_OPTIMIZE` accepts only improving steps and falls back to identity if the full render
  would score below the untouched image; it never returns a worse image. It is deterministic.
- Cast is measured and reported but not penalized. A target tint below 0.005 is treated as no
  tint. A learned aesthetic model is not part of the score; if one is added, it may only rank
  candidates of the same image.

Wheel semantics (PHOTO_GRADING): zones are BT.709 luma bands (shadows/midtones/highlights).
Each wheel with `saturation > 0` rotates a pixel's hue by the wheel's hue and scales its
saturation by saturation/100 within its zone. `blending` mixes the tinted LUT back toward
identity; `balance` moves the zone boundaries. The classic cinematic look is teal shadows
+ orange highlights.

See README.md for the schemas, operation table, error codes and provenance.
