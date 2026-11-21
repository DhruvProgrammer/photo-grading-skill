# Photo Color Grading — Research Knowledge Base

Everything learned from sources (online articles, docs, tutorials) about how to
color grade *photos* — the creative technique used to make images look
cinematic, moody, warm, cool, etc. This is the foundation for the new
photo-grading skill. Research conducted 2026-11-21.

Note: photo color grading shares DNA with video color grading, but it is its
own discipline with different tools and emphasis (one frame, permanent result,
subject separation). Video grading is temporal/perceptual; photo grading is
permanent, so restraint and correctness matter more.

---

## 1. What Is Color Grading? (Concept + Correction vs Grading)

From Adobe and multiple sources:

- **Color correction** = fixing problems that exist in the original capture
  (bad white balance, a cast, exposure problems, muddy colors). The goal is
  "neutral and true": what you see is approximately what the scene looked like.
  Correction is the invisible, necessary first step. It is done with White
  Balance, exposure, neutral grays (grey card / magic wand), and neutral
  Curves.
- **Color grading** = walking away from neutral on purpose, on the way to a
  *feeling* or *style* ("warm and nostalgic, cool and clinical, muted and
  expensive"). Teal-and-orange is grading. It is applied after correction.

Order: **grade after you correct, never before** — grading on top of an
uncorrected image means your mood fights a color cast you never removed
(ABrush, Markus Hagner Photography, Skylum).

- Correction = removing what the camera/light got wrong (Abrush).
- Grading = pushing toward a feeling (Abrush, Skylum, Adobe, Fstoppers).

## 2. Correction vs Grading — Why This Split Exists

- If color looks right but flat → you may want grading (Skylum).
- If the color looks wrong (cast, wrong temp) → correction.
- Correction: white balance, exposure, crop, fine tweaks.
- Grading: creative direction, atmosphere, mood.

## 3. White Balance Fundamentals (Correction First Step)

- Set white balance so neutrals look neutral BEFORE grading
  (Starts slightly cool gives teal something to sit against — Sklum).
- Set exposure for the subject, not the sky.
- Pull Highlights down, lift Shadows a little for detail at both ends.
- Set Whites/Blacks for a real black point without crushing.
- Getting odd colors from auto white balance: use a fixed WB (daylight) or
  shoot raw and set it in post (PhotographyIcon).
- Use a grey card or a neutral surface (white shirt, grey concrete, road
  sign) to set the neutral point with a Curves middle-eyedropper
  (Abrush, PhotographyIcon).

## 4. Color Theory for Grading

### The two color wheels (why names vary)
- **Painter's wheel (RYB)**: Red/Yellow/Blue primaries; complements:
  Red–Green, Blue–Orange, Yellow–Purple, plus mixed pairs
  (PhotographyIcon).
- **Light/RGB wheel (used by cameras, screens, editing software)**:
  Red/Green/Blue primaries; complements:
  Red–Cyan, Green–Magenta, Blue–Yellow.
  This is the wheel graders use; temperature slider runs blue→yellow;
  tint slider runs green→magenta. Adding one color removes its opposite
  (PhotographyIcon).

### Complementary colors
- Complementary = the one pair directly opposite the wheel with the most hue
  contrast possible.
- Why they work:
  - **Simultaneous contrast**: opposite colors look more saturated/vivid next
    to each other (a red jacket in a green field pops) (PhotographyIcon).
  - Separate subject from background (warm subject vs cool background).
  - Feel balanced — a complementary pair covers both warm and cool sides.
  - Create depth — warm colors (orange) seem to come forward, cool (blue)
    falls back → warm subject over cool background looks more separated.
- Examples in the world: skin tones vs blue/teal background/sky; golden hour
  vs blue shadows; warm windows against blue dusk streets; autumn leaves vs
  blue water.

### Warm/cool contrast
- Warm = advance, Cool = recede (PhotographyIcon). Used to guide the eye:
  warm subject + cool environment = subject pops forward; cool subject in
  warm field = integrated/distant.

## 5. The Signature Look: TEAL & ORANGE

- **Teal & Orange** is the most popular cinema look and for good reason.
  - Orange sits in the highlights, mostly in skin tones.
  - Teal tints the shadows (colorsys: shadows/backgrounds/skies).
  - Works because **orange and teal are complementary** — maximum visual
    contrast between subject (skin) and world (sky/shadows).
  - Preserves depth and separation. Used because "human skin sits in the
    orange family" and cool backgrounds increase separation (Fstoppers,
    PhotographyIcon, Skylum).

### Why it works
- Skin of every tone sits in the narrow hue range between red and yellow —
  the "skin-tone line" on the vectorscope (Flashboards/Yaroflasher).
- Pushing everything else toward the opposite hue (teal shadows, cyan skies)
  separates the subject (Skylum, PhotographyIcon).

### How to build it (the canonical recipe)

From **Fstoppers** (create-cinematic-orange-and-teal-color-grade-lightroom):
1. **Start with Shadows wheel**: reach a sufficient teal hue in the shadows.
   Don't saturate too much — you still need other grades.
2. **Warm up the Highlights wheel**: orange toward the top-right edge (most
   saturated corner).
3. **Control Midtones**: a slight orange/red tint bridges darker and lighter
   areas; don't let the teal overpower the image; strike balance early.
4. **Blend & Balance sliders**: blending 21 (lower = harsher cutoffs,
   higher = smoother; 100 = all overlap, can get muddy). Balance (14 here):
   left = more teal midtones, right = more highlight color.
5. **Finish with Tone Curve**: mute blacks, slightly brighter highlights.

From **PhotoshopTrainingChannel**: most popular movie look is teal & orange;
teal tints shadows, orange sits in highlights/skin tones; works because they
are complementary.

From **PhotographyIcon**: teal shadows + warm highlights, restrained — the
difference between generic and intentional is restraint. "One side of the
pair carries the scene; the other appears only where it matters."
- Restriction for grading: **Protect neutrals.** If white shirts/grey concrete/
  daylight all go cyan, the image looks tinted, not designed. Keep true
  neutrals in the frame (Skylum).
- Motivate it in the lighting: blue dusk or daylight behind you, warm
  practicals.

From **Impact Photography**: keep the gate:
- Shadows: hue ~210 (teal-cyan-blue), saturation ~25 (lower start ~10–25,
  build up).
- Highlights: hue ~40 (amber-orange), saturation ~20 (10–20).
- Midtones: leave neutral, or hint of shadow color at saturation ~3–8.
- Blending: ~60–80 (smoother transitions; higher for smoother).
- Balance: negative → teal takes more of frame; positive → highlight color
  extends down. Small moves make big differences.
- Protected: keep skin warm but not orangish; lift shadows slightly to avoid
  green.

From **JustAdobe** (grading values for cinematic):
- Shadows: Hue 210, Saturation 25, Luminance -5
- Midtones: Hue 30, Saturation 8, Luminance 0
- Highlights: Hue 40, Saturation 20, Luminance +5
- Global wheel: leave 0
- Blending: ~60, Balance: +15 (skin glows without losing teal shadows)

From **Markus Hagner Photography**:
- Shadows wheel: hue ~200–210, saturation 15–30.
- Highlights wheel: orange, saturation ~10–25 (warm for portraits enhances
  skin).
- Midtones: small bridging color, or neutral.

From **Fstoppers** (canonical 5 steps):
1. Shadows wheel: teal (~200–210°), modest saturation.
2. Highlights wheel: warm orange (30–45°), lower saturation than shadows.
3. Midtones: neutral, or tiny warmth.
4. Blend & balance: blending ~50–80; balance left = teal more, right = highlight
   color more.
5. Tone Curve: slightly lift black point, pull white point down (soft,
   matte look).

## 6. Other Classic cinematic looks (all built the same way)
From Fstoppers/Impact/Skylum:
- **Teal & amber**: shadows teal (~200°), highlights amber (~30–45°), good for
  portraits/city at golden hour.
- **Bleach bypass**: low saturation, high contrast, silvery highlights —
  suits gritty/overcast.
- **Night blue**: deep blue shadows & midtones, warm practical lights untouched.
- **Autumn dusk**: burnt orange highlights over deep brown shadows, warm/nostalgic.
- **Orange + blue**, **Green + magenta**, **Deep blue + magenta neon**, or a
  single cold tone for winter scenes.

## 7. Lightroom/Camera Raw Color Grading Panels (the tool)

From Adobe Introducing Color Grading blog + Usage Guides:
- The Color Grading panel has three color wheels: Shadows, Midtones,
  Highlights (+ a Global wheel).
- Each wheel has a hue/saturation handle (angle = hue, distance = saturation;
  center = no tint; edge = max saturation).
- Below each wheel: a dedicated **luminance** slider (adjusts brightness of
  that tonal range; e.g. lift shadows = -5 in Fstoppers example).
- **Blending slider**: how much the three ranges overlap. 0 = minimal overlap
  (each range independent, not hard cutoff). 100 = all overlap → smooth look,
  colors can mix/blend and get muddy. Default 50; raise to soften transitions
  (Skylum: 50–80).
- **Balance slider**: shifts where the midtone boundary sits (left = midtones
  darker, right = lighter).
- **Global wheel**: adds a universal tint on top of the three-way toning;
  subtle combos; try it.

### How to use:
1. Handle inside wheel: angle = hue, distance = saturation.
2. Blending & Balance for transitions.
3. Make base edit first (Adobe): adjust white balance, exposure, contrast
   BEFORE visiting the Color Grading panel. Grade the good base.

## 8. HSL / Color Mixer (secondary precision tool)

From PhotographyIcon, PHLEARN, Sklum, impact photos, darkroom:
- HSL lets you shift hue/saturation/luminance per color (Reds, Oranges,
  Yellows, Greens, Aqua, Blues, Purples, Magentas).
- Used for skin tones and skies BEFORE grading (order: HSL then Color Grading,
  or both).

Example values (Impact Photography,marketing):
- Orange Hue: leave near 0, or slightly warmer/redder. Orange Saturation:
  small change, often down slightly. Orange Luminance: slightly up for
  brighter skin.
- Yellow Hue: nudge toward orange (negative). Yellow Sat: down a little.
- Green Hue: shift toward aqua (positive). Green Sat: down a lot (kill neon
  foliage). Green Lum: down slightly.
- Aqua Hue: toward blue (positive) for teal; Sat: to taste; Lum: to taste.
- Blue Hue: toward aqua (negative) for teal; Sat: moderate; Lum: down for
  deeper skies.
- Pull Purples/Magentas down if they don't belong in the scene.

### Skin tone protection (HSL)
- Skin lives mostly in midtones + highlights. When you warm the highlights,
  watch faces first — the moment skin turns jaundiced, reduce highlight
  saturation or shift hue toward yellow-orange rather than pure orange.
- The Midtones wheel is the skin-tone guardian: many leave it neutral or add
  faintest warmth, and keep shadows teal.
- Keep highlight saturation modest. Use HSL to counter unwanted shifts.

### Common failures to avoid:
- Oversaturated grade: halve teal saturation — the grade should be felt, not
  seen (it should be able to toggle off without killing the image).
- Orange skin = grader warmed highlights globally and forgot the face; mask
  subject (Select Subject mask), pull saturation back or shift temp.
- Orange skin cause: pushing Orange Sat up, or pushing Orange Hue toward
  red/yellow (sunburn); fix: lower highlight saturation, bring Orange
  Luminance up so skin reads brighter not oranger (ABrush, Markus Hagner).
- Muddy or green shadows cause: teal leaning too green, heavy faded blacks,
  leftover green. Fix: move shadow hue toward blue, cut Green Sat in HSL,
  restore black point via curve.
- Automatic white balance can kill your warm/cool contrast; shoot raw and set
  WB in post or set fixed daylight.

## 9. Tonal Curve (base + finish)

From Adobe + Fstoppers:
- Lift black point slightly, pull white point down → "muted, matte film look"
  (soft blacks, highlights roll off gently, no hard clipping).
- Add a soft S-curve in midtones for contrast.
- Tone curves are the "finish": polish wood to show the desired look.

## 10. Wider cinematic workflow (multiple sources combined)

### Canonical workflow (Impact Photography, Markus Hagner, Fstoppers):
1. **Crop** (if desired): wider aspect ratio, motivated light.
2. **Set base**: white balance, exposure, contrast.
3. **Grade**: Color Grading wheels (Shadows/Midtones/Highlights), blending,
   balance.
4. **HSL**: tidy palette, protect skin/skies.
5. **Tonal curve**: matte + S-curve.
6. **Vignette / grain** (optional): subtle, to draw eye inward.

### shoots for cinematic edit:
- Underexpose slightly (-0.3 to -0.7 EV) so practicals/skies keep detail.
- Use raw so the grade has room to move.
- "Motivated light": blue ambient (dusk/night) + warm practicals give natural
  warm-cool split.
- Skin in orange family: designed so warm subjects read against cool
  backgrounds.

### "Film look" attributes (Mikkolagerstedt, Sklum):
- Sparse palette, controlled contrast, grain (small, roughness ~50).
- Soft highlights, muted blacks.

### Step-by-step (non-AWARE from various tutorials):
1. Fix color casts (WHITE_BALANCE / correction) — click a neutral, e.g.
   grey card or white shirt.
2. Fix exposure, contrast, highlights/shadows.
3. Grade shadows (teal), midtones, highlights (warm), blending, balance.
4. HSL adjustments.
5. Curves for tone.
6. Vignette, grain (optional).

## 11. Different cinematic looks worth knowing

- **Golden Hour / Warm Mood**: warm highlights, cool shadows → nostalgia.
- **Teal & Orange**: modern blockbuster, depth, subject separation.
- **Desaturated / Moody**: low saturation, cool tones, restrained.
- **Retro / Vintage**: warm blacks, grain, faded highlights.

## 12. Tools & Software Covered

- **Adobe Lightroom / Camera Raw**: 5-step cinematic workflow; Color Grading
  wheels + HSL + basic panel + curve.
- **Adobe Photoshop**: Selective Color Adjustment Layer for teal/orange;
  curves S-curve; channel curves; new layer trick (fill grey, Difference
  threshold) for neutral.
- **Photoshop Training Channel** (teal/orange tutorial).
- **abrsuh / PHLEARN / Fstoppers /iosyncrasies / Darkroom / Sklum / Lutland /
  Adobe Blog / JustAdobe / Markus Hagner / Impact Photography** — all
  Lightroom color grading tutorials.
- **Viewport tools (modern web apps)**: auto-detection (Ctrl+click on wheel)
  etc. (Adobe Advanced).

## 13. Equipment & Shoot Notes (to make grading work)

- Shoot RAW (more color information, greater headroom).
- Underexpose slightly.
- Avoid harsh midday light (flat).
- Motivate lighting (warm windows against blue dusk).
- (Video-skills carry over for light, lens, color temperature physically.)

## 14. Key Principles (TL;DR, the "rules" of photo color grading)

1. **Correction before grading** — grade after correct; grade mood on a
   corrected image.
2. **Teal in shadows, orange in highlights/skin = the classic cinematic split.**
   Composed of complementary colors (blue/yellow opposites).
3. **Modest saturation + restraint.** If the grade is obvious, halve it.
4. **Complementary contrast** = strongest hue contrast, separates subject
   from background, creates depth and balance.
5. **Warm = advance, cool = recede** — use to guide the eye.
6. **Protect skin/neutrals.** Orange skin, green skin, and lack of true
   neutrals are failure modes; fix with masking or reducing saturation.
7. **Balance hue and saturation in the 3 wheels (shadows/midtones/highlights);
   Use Blending for smoothness; use Balance for where the split sits.**
8. **Tonal Curve for matte finish + soft highlights.**
9. **"A grade should support the subject, not announce itself. The best
   grading is felt, not seen."** (Abrush)
10. **Best grades are per-image.** Different looks (warm, cool, muted,
    desert, forest) depend on the image's own palette and story.

## 15. Source URLs (citable)

Fstoppers, PHLEARN, Astronomy-news — primary sources used for research.