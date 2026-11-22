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
---

## 16. DaVinci Resolve color grading transcript tips (video review)

A DaVinci Resolve color grading walkthrough ("Mitchell Mullins" style — a free professional
workflow video; the video was transcribed and read; tips adapted to the photo skill).
Key tips/trick extraction (DaVinci-specific, cross-applicable):

### Two pillars: Corrections vs Look development

- **Corrections** — "where is the image actually living how are we perceiving this image" —
  exposure, balance, contrast; fix the camera/light problems. The photo skill: `PHOTO_CORRECTION`.
- **Look development** — "how does this image feel how does it come across what is our intention
  right how does this fit into the story" — color separation/hue — mood, depth. The photo skill:
  `PHOTO_GRADING` + `PHOTO_LUT_APPLY`.
- Order: **corrections first, then look** ("if we were to adjust our offset... you'd shift the
  middle gray point and all of your other Corrections later down the line no longer stay the same").

### Corrections (the biggest brush strokes — work photometrically, keep the camera's light levels)

- **Exposure**: use the **HDR Global wheel** (lifts/lowers uniformly, anchored at the blacks) —
  NOT the Offset wheel (it shifts the whole image and changes the middle gray point — destructive).
  The skill: `exposure` in `PHOTO_CORRECTION`.
- **Linear balance**: set gamma to "linear" (void of log space) and gain to where the image should
  live. The skill: `white_balance_temperature`/`white_balance_tint`.
- **Contrast**: "the biggest tip... contrast is the separation between black and white"; there's a
  **pivot point** (middle gray ~336 — "the fulcrum of our contrast") — steer the eye: increase
  contrast if "we want to make it feel more pleasing" — but only if "the question for us is does it
  need to do". Avoid cranking contrast past where it clips. The skill: `contrast`.
- "much of knowing what NOT to do" — don't overdo; "a lot of people just have too much contrast".

### Split toning (the signature look — "color separation")

- **Everything split toning happens in your curves**: anchor at middle gray (Da Vinci's
  "Nano Middle Gray" — poke the curve to nail down the red/green/blue center), raise reds/greens in
  the highlights (warm highlights), drop greens/blues in the shadows (cool shadows). That hue split
  is the color separation — "we're separating our colors in the same way we did with our luminance
  Channel and the contrast".
- BUT: **I personally never do this — a lot of colorists rely on LUTs** ("we can rely on LUTs to give
  us that split toning effect"). Film emulation LUTs (Kodak 2383, Fuji stocks, Tera, "the Legacy L
  Collection") "are emulating film... finely-tuned to what our eyes find most preferable". LUTs
  "look great they look awesome" and "you can dial it back... take the look too far — there's really
  no rules". The skill: `PHOTO_LUT_APPLY` (+ `strength`), plus DIY wheels via `PHOTO_GRADING`.

### Post-L granular tweaks (from the transcript, mapped to the skill)

- **Saturation**: Da Vinci has three tools — `Saturation` (multiplier: "multiply some of the color
  values" — blows out super-saturated elements), `Color Slice` ("deeper color values, more natural
  — personally like the deeper color values"), `Color Boost`/vibrance (additive — "adding colors that
  aren't there"). The skill: `saturation` in `PHOTO_CORRECTION` (like Color Slice).
- **Matrix**: channel-strength tweaks per channel ("skin correction": push the skin toward magenta,
  balance red/blue). The skill: `white_balance_temperature`/`white_balance_tint` in `PHOTO_CORRECTION`.
- **HSV tweaks post-L**: "Hue vs Hue"/`Hue` + `Hue Saturation` — "adjust our hue... we can adjust
  our blue saturation... similar to our Matrix". The skill: wheels.
- **Log wheels post-L**: "drop some of the blacks to give us a little deeper of a feel" — log
  wheels as finishing tweaks. The skill: wheels' `luminance`.
- **HK — subtle luminance**: a post-L "hue/hue secondary" — humans perceive certain saturation
  values as more luminous; tacks subtle luminance onto the colors (leaves out the moments of the
  film look). The skill: the global `strength` dial ("dimming everything by N%").

### Other tips

- **Color space sandwich** (any camera → working space → display): input color space → Da Vinci wide
  gamut → output color space (Rec 709 gamma 2.2 — "optimized for YouTube / macOS"). The skill:
  `pix_fmt` measured at validation; `PHOTO_GRADING` works on the wide gamut.
- **Teal & Orange** — "the classic teal and orange you know — push the highlights warmer, push the
  highlights cooler" — the most recognized cinematic split (complementary). The skill: the default
  look (shadows hue 190, highlights hue 40).
- **Skin protection** ("much of the color difference is when you see the blood underneath the
  skin"): hue-rotate skin back (magenta → yellow) and dial back saturation; "I don't mind where it's
  at" nuance. The skill: `PHOTO_GRADING.balance`, wheels' saturation, `white_balance_tint`.
- **Workflow philosophy**: "the biggest unlock is figuring out what each of those are and then
  identifying what the most preferable approach is"; "do more with less"; "never be afraid to take
  the look too far — there's really no rules"; "a lot of people are just doing too much — these
  couple adjustments make the image look better than most things I've graded in my entire career";
  "much of what makes a grade feel cinematic is subtlety: 'I'd say a lot of the difference is you
  don't really want to see the effect'".
- **Simplicity**: "the whole philosophy here is keep things as simple as possible"; end-of-grade
  check: "whenever you think you're finished — try turning the look off and on — if 'before' looks
  broken, you've overcooked it" (the skill: `photo-grading plan`/`doctor` as checks).
- **Film stocks as inspiration**: "a lot of what we're trying to emulate in these split tones is the
  characteristics of film... finely-tuned and tailored to what our eyes find most preferable"
  (Kodak 2383, Fuji, Tera). The skill: wheels emulate the same splits.

### Strength semantics (new, implemented in the skill)

"Dial it back" — `PHOTO_GRADING.strength` (0..1): effective blend = `blending/100 * strength` — a
"look dial" (strength 0.5 = half the grade, 0 = identity). `PHOTO_LUT_APPLY.strength` scales a user
LUT toward identity (`out' = in + strength*(entry - in)`), so `strength 0.5` gives the same result
as `PHOTO_GRADING.strength 0.5` on the same wheels (verified empirically).
"Film grain" (transcript: "film grain this is really important... use it sparingly") — `grain`
(0..50) → `noise=alls=N` (verified filter exists in ffmpeg 8.0.1).
"Much of what makes a grade feel cinematic is subtlety: 'a lot of the difference is you don't
really want to see the effect'".

---

## 18. Color theory fundamentals (video review)

A general color-theory walkthrough (RYB painter's wheel, hue/saturation/luminance).
Key tips/trick extraction (cross-applicable to photo color grading):

### The color wheel & basic terms

- Wheel: 3 primaries (Red/Yellow/Blue - the painter's wheel), secondaries, tertiary colors.
- **Hue** - "simply the color itself" (name any color - red, orange, blue - "pun intended").
- **Saturation** - intensity of the color: pure blue -> reduced saturation -> gray; darker blue ->
  black, lighter blue -> white.
- **Luminance** - how bright/dark the color is. "The reason why luminous is so important is because
  it mainly controls the contrast between the colors."

### Luminous contrast - the B&W check trick

- "Simple trick, convert your image into black and white. If everything looks flat, it means there is
  not much of luminous contrast." - the skill's before/after signalstats measurements (YAVG/UAVG/VAVG)
  record the same idea (luminance + chroma before/after) as OBSERVED values.

### Color associations (guidelines, not rules)

- Red = passion, energy; Blue = stability, trust (also isolation). Etc. "At the end, these are just
  on paper associations. It need not always be true." - the skill: don't force associations; wheels.

### Frame composition with color

- "If everything in the frame is super saturated and vibrant, the viewer might get confused about what
  to focus on" - "some colors are comparatively more saturated than others - the eyes naturally be
  drawn to them. Let's divide the frame into two groups, saturated colors and neutral colors.
  Saturated colors as the main subject and neutral colors as the negative space" - balance: "one or
  two colors can dominate while the other colors can play supporting roles" - "prevents chaos".

### Warm/cool colors

- Warm = reds, oranges, yellows (lows on the color wheel's "temperature"); cool = blues, greens,
  purples (higher temperatures). Note the opposite convention from white-balance "temperature" -
  don't get confused (skill: white_balance_temperature).

### Famous looks: Teal & Orange

- "The famous teal and orange look works because it's a contrast between warm and cool colors. Skin
  tones usually fall on the warm side while the background or the shadows can be pushed towards the
  teal side" - the skill: the default wheels (shadows hue 190, highlights hue 40).

### Color harmony (cheat sheet)

- **Monochrome** - one color, different shades (not black and white!).
- **Complementary** - opposite on the wheel (Teal & Orange is the example).
- **Analogous** - three side by side, natural, easy on the eyes.
- Guidelines; "you don't have to always stick to it".

### Applying theory to shots

- Mindful framing: "which colors help my subject to stand out and which are distracting" - portraits:
  outfits (pop vs blend); products/food: pop colors.
- "Color actually plays a huge role in a consistent visual style" - style from story/emotion.
- "don't mistake... experimenting - developing a style is important but if you don't experiment, you
  won't learn" - the skill: contrast/strength/strength dials, virtual copies.
- "Color doesn't just make your images look good - different colors feel different."
- Practical advice for styles: "Colors can basically be divided into two groups... warm colors and
  cool colors... you can stick to warm or cool or use a combination".

---

## 19. Adobe Lightroom color grading tips (video review — Lightroom Color Grading panel)

A Lightroom color grading tutorial (photo-specific tips). Extracted from the transcript:

### Foundation first

- **Establish a color foundation with the Basic panel** (temperature + tint) before touching the
  Color Grading panel: "you should not even be touching that color grading panel until you first
  set a foundation of color for your image... This is the first place I always recommend starting
  out when you're editing color because it allows us to establish a general mood... And the white
  balance adjustments creatively" — "if you shot an auto white balance, your camera probably did a
  fantastic job of balancing that scene... go up here and select auto".

### The Color Grading panel (the 3-way wheels)

- Three circles: **Shadows** (shadow areas), **Midtones** (gray/middle of the photo), **Highlights**
  (brightest areas). Each wheel: **hue** (the color), **saturation** (purity), **luminance**
  (brightness of that color).
- **Blacks don't light up**: "black is going to stay black" — "if we change the luminance values of
  those shadows, we can bring those blacks up" (drag the luminance slider right — "adding gray into
  that black, allowing it to be affected by that shadow adjustment").
- **Blending**: smooths gradients (right = smooth, left = abrupt). **Balance**: favors highlights
  (right) or shadows (left). Play with both.
- **Global** wheel: add over the entire image ("if you really want to lean into a certain color").
- **Bigger circles**: finer color selection.
- **Sliders**: click a circle, drag the hue/saturation/luminance sliders for fine control.

### Color combinations (the most common in Lightroom)

- **Complimentary colors** — opposite on the wheel:
  - **Blue & orange** — "a color combination that I use in so many of my images because it's
    incredibly pleasing on the eye and it's also naturally occurring. So, a lot of our scenes
    already have these complimentary colors built into them" — enhance: "add some blue into the
    shadows... add some warm tones into those highlights" — the skill: the default wheels.
  - **Green & red** — "while it's not entirely natural... it kind of gives your images a classic
    Fujif film aesthetic".
  - **Purple & green** — for night photos.
- **Monochromatic** — one hue, different luminances ("going all in on one specific color").
- **Analogous** — close colors on the wheel ("leaning into one color family").
- Experiment: "there's no right or wrong way to color grade an image" — "every photo is a little bit
  different... make a few different variations" via snapshots ("snapshot number two" — reset with
  option, create variants, compare) — the skill: plan/doctor as checks; stable wheels.

### Workflow tips

- **Subtle changes**: "even the smallest changes to the colors in your images can completely change
  the mood or the vibe of your image" — "the more detailed and specific you can get with editing
  color, the better your color grades will ultimately be" (work back and forth with HSL + color
  grading).
- **Color fatigue**: "when you're staring at the same edit for 10, 20, 30 minutes... take a step
  back... looking back at this image here that we just covered... it looks way off... it's a little
  bit too green... I'd probably warm it up a little bit... I always recommend taking breaks so you
  can come back to that image with a fresh set of eyes".
- **Find your color profile**: "the more you play around... the more you're going to kind of find
  what works for you and what works for your images" — "when you do find what works for you, I would
  highly recommend incorporating those grades into presets of your own... they don't have to be
  super strong, crazy presets" (the skill: the skill's strength dial = preset dial; wheels).
- **Family style**: "you might vibe with a slightly different color combination" — "my Film Vibes
  preset pack has color grading built in" — the skill: users can compose their wheels per photo.

### Skill mapping notes

- LRS wheels == skill wheels (hue, saturation, luminance per tonal range) — documented in
  knowledge.md section 16 and docs/architecture.md.
- Complimentary combos: Teal & Orange is the skill default (§16); green & red, purple & green are
  also native combos (§19).
- The "dial back" concept (§16) and LUTs — consistent with this video's "make a few different
  variations" workflow.
