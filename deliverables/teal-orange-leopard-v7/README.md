# Teal & Orange — Leopard (final)

**Status: locked.** Rated 6.5/10 on 2026-11-25; the remaining gap is source
resolution and JPEG blocking, not the grade.

Source: 221×148 compressed frame.

Pipeline (see `request_teal_orange_v7.json`):

1. `PHOTO_CORRECTION` — WB 6250/+3, exposure −0.12, contrast 27, vibrance 28,
   blacks −6, shadows −20, highlights −50, tone 0.008/0.08/0.48/0.78/0.99,
   chroma denoise 50.
2. `PHOTO_GRADING` — shadows 190/36/−12, midtones 0/52/0, highlights 350/92/−34,
   blending 76, balance 12.
3. `PHOTO_LUT_APPLY` — `warm_crisp.cube` (warm recovery + white-point shoulder).
4. `PHOTO_CORRECTION` — `whites −6`, `highlights −3` (ridge trim).

Final metrics: sky 144/169/181 (hue 200.6°, sat 28.3%, luma 164), leopard luma
144, rock luma 180, highlight clip 0.000%, shadow clip 2.50%, neon 0.018%,
cast −2.4/−7.1, no warnings. No pixel above 240 in the PNG or the JPEG.

Re-running this request on a higher-resolution original is the only way past
the current ceiling; the recipe itself is final.
