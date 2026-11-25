# Photo Color Grading — Knowledge Base

A practical, scene-first guide to grading photographs: what each control does, when to use it,
where it belongs in the pipeline, and how to tell whether it worked. It is written as a
reference, not a diary. Every rule here exists because a specific failure mode was observed and
measured; the failures are described as technique, not as history.

The governing idea: **a grade should support the subject, not announce itself.** The best color
work is felt before it is noticed, and it survives being toggled off.

---

## Contents

1. The non-negotiables
2. Read the frame before touching a slider
3. The pipeline: correct, shape, color, finish
4. White balance
5. Exposure and tone
6. Color: saturation, vibrance, HSL
7. Split toning and classic looks
8. Local control without masks
9. Scene playbooks
10. Finishing: clarity, sharpness, grain, output
11. Quality control: measure, don't guess
12. Parameter reference
13. Engine invariants: why grades fail
14. Glossary
15. References

---

## 1. The non-negotiables

1. **Correct before grading.** White balance, exposure and tone endpoints come first. Grading a
   cast means the mood fights a problem that was never removed.
2. **Protect the anchors.** Skin, sky, water, snow and neutral stone are what viewers use to judge
   whether an image is "right". A grade that wins the foliage but turns the boulder green is a
   failed grade.
3. **Change one variable at a time.** If three sliders move together, you cannot tell which one
   helped. Make a variant, compare, keep the winner.
4. **If the grade is obvious, halve it.** Saturation, contrast and split tones all read stronger
   after a break. The toggle test: turn the look off; if the "before" looks broken rather than
   merely flatter, the grade is doing too much.
5. **Measure the result.** Eyes adapt to a screen in minutes. Percentiles, clipping, neutral-pixel
   cast and region contrast do not.
6. **Stop before the texture breaks.** On a small or compressed file, the last 10% of contrast or
   sharpening costs more detail than it adds punch.

### Working method

Professional grading practice maps onto this engine as a set of habits, not extra controls.

- **Broad before narrow; neutralize before correcting.** Fix exposure, balance and tone with
  `PHOTO_CORRECTION` before reaching for wheels or HSL. A narrow hue fix on an unbalanced base
  treats the symptom and leaves the cause.
- **Overshoot once, then retreat.** Make one deliberately exaggerated variant to find the boundary,
  then back off toward the sweet spot. Creeping up in small steps wastes passes and produces
  exports that look identical to the last one.
- **Know when to do nothing.** Compare a candidate against the current best with region
  measurements. If sky, subject and anchors moved by only a point or two, do not ship it; reset and
  try a different axis.
- **Eyes first, numbers second.** Judge the image, then use `inspect` as a reality check for
  clipping, cast and chroma. A cast warning on an intentionally teal sky is expected; a moved
  anchor is not.
- **Separation comes from tone, not just hue.** Push warm tones up and cool tones down with
  `shadows`, `highlights` and wheel luminance, then rebalance after raising saturation. Boosting
  saturation alone makes imbalance more visible, not less.
- **Protect the highlight shoulder.** Lower `highlights`, `tone_highlights` and negative wheel
  luminance before adding warmth, so bright sand, stone and fur keep texture instead of going
  pastel or peach.

---

## 2. Read the frame before touching a slider

Before choosing a look, answer five questions.

| Question | Why it matters | What to do with the answer |
|---|---|---|
| What is the subject? | The grade should separate it, not compete with it | Put the strongest contrast and warmth on the subject; mute the rest |
| Where is the light coming from? | Warm/cool direction should follow the light | Warm the lit side, cool the shade; do not invert the sun |
| What are the anchors? | Skin, sky, water, snow, stone set the viewer's expectations | Protect their hue and luminance; grade around them |
| What is the dynamic range? | Clipped highlights or crushed shadows limit recovery | Recover what exists; do not invent what does not |
| How much detail is in the file? | Resolution and compression set the sharpening ceiling | Small/soft file: tone curve over clarity, low sharpening |

### Choose the look from the scene, not from a preset

- **Alpine / lake:** cool water and haze, neutral stone, natural greens, warm sunlit edges.
- **Forest:** deep greens, restrained saturation, cool shade, soft light.
- **Desert / canyon:** warm highlights, neutral sand, blue shadows, high clarity.
- **Coast / sea:** cyan-to-blue separation, clean horizon, cool atmosphere.
- **Golden hour / portrait:** warm skin and highlights, cool shade, gentle contrast.
- **Night / city:** mixed practicals, protected highlights, blue shadows, selective warmth.
- **Snow:** neutral whites, cool shadows, very gentle contrast.
- **Product / food:** neutral white balance, clean highlights, modest saturation, crisp detail.

### The black-and-white check

Convert a copy to grayscale. If the frame looks flat, the problem is luminance separation, not
color. Fix it with the tone curve before adding saturation. If the frame looks busy, the problem
is too many competing colors; simplify the palette with HSL instead of raising contrast.

---

## 3. The pipeline: correct, shape, color, finish

Order matters because every step becomes the input to the next.

| # | Step | Primary controls | What it fixes | Stop condition |
|---|---|---|---|---|
| 1 | Read the frame | eyes, grayscale check | unknown subject/palette | you can name the anchor and the intended mood |
| 2 | White balance | `white_balance_temperature`, `white_balance_tint` | cast, mixed light | neutrals read neutral, mood intact |
| 3 | Exposure and endpoints | `exposure`, `highlights`, `shadows`, `blacks`, `whites` | clipped highlights, dead shadows | highlight clip near zero, shadow detail present |
| 4 | Tone shape | `contrast`, `tone_*` anchors | flat midtones, harsh shoulder, matte finish | separation without crunch |
| 5 | Palette cleanup | `PHOTO_HSV` families | neon foliage, cyan haze, oversaturated water | offending family fixed, other families unchanged |
| 6 | Overall chroma | `saturation`, `vibrance` | dull or excessive color | neon share low, saturation not above the source unless intended |
| 7 | Look / split tone | `PHOTO_GRADING` wheels, LUT + strength | mood, warm/cool separation | neutrals clean, skin safe, grade reversible |
| 8 | Finish | `clarity`, `sharpness`, `grain` | softness, local flatness, banding | no halos, no blocky crunch |
| 9 | QA and export | `inspect`, format encode | hidden clipping/cast | metrics pass, one final encode |

**Why this order:**

- WB first, because every later LUT assumes the input is balanced.
- Endpoints before contrast, because contrast around a clipped highlight only clips more.
- Tone before HSL, because the HSL families need stable luminance to judge.
- HSL before global saturation, because targeted fixes should not be re-amplified by a global boost.
- Split tone after palette cleanup, so the look sits on a clean base.
- Sharpening last, because it amplifies noise, compression blocks and color fringing.
- One final encode, because repeated JPEG passes destroy exactly the fine texture being judged.

---

## 4. White balance

### What it does

White balance sets which color is treated as neutral. Temperature moves the image between blue
(cool) and yellow (warm); tint moves it between green and magenta. In this engine, temperature
above 6500 K warms (lifts red, lowers blue), below 6500 K cools; positive tint adds magenta,
negative tint adds green.

### When to use it

- At the start of every edit.
- When a neutral surface (rock, concrete, cloud, white shirt, gray card) has a visible cast.
- When mixed light makes the subject and background disagree; balance for the subject.
- When a deliberate warm/cool mood needs a foundation (slightly warm stone, slightly cool shade).

### When not to use it

- Do not neutralize a sunset, candlelit interior or neon scene. The cast *is* the light.
- Do not chase a whole-frame average. A green landscape is not a green cast.
- Do not use auto WB blindly; it can flatten the warm/cool split that makes the image work.

### How to do it

1. Find a near-neutral patch (saturation below ~12%) in the midtones or highlights.
2. Measure its R−G and B−G. Aim for both near zero; ±4–5 is usually acceptable, and some source
   cast can be intentional.
3. Adjust temperature first, then tint. Temperature fixes blue/yellow; tint fixes green/magenta.
4. Re-check the anchors: skin, sky, water and stone. If warming the stone turns the lake warm,
   compensate the water separately with HSL blue/cyan instead of undoing the warmth.
5. Keep a copy of the pre-WB frame. If the corrected version feels lifeless, the original cast may
   have been part of the mood.

### Typical moves

| Intent | Temperature | Tint |
|---|---|---|
| Neutral daylight | 6500 K | 0 |
| Gentle warmth on stone/skin | +100 to +250 K | 0 to +3 |
| Strong golden-hour warmth | +400 to +800 K | 0 to +5 |
| Cool shade / overcast | −200 to −600 K | −2 to 0 |
| Correct fluorescent green | 0 | −8 to −15 |
| Correct magenta shade | 0 | +8 to +15 |

### Failure modes

- **Whole-frame cast "fix"**: the average moves, the neutrals do not. Measure neutral pixels only.
- **Warm lake**: a global warm WB warms water too. Warm the land, then pull cyan/blue back.
- **Gray snow**: neutralizing every channel in snow kills the blue shade that gives it form.
- **Skin sunburn**: warming highlights globally pushes skin orange. Warm the light, then protect
  orange with HSL luminance rather than more saturation.

---

## 5. Exposure and tone

### Exposure

Expose for the subject, not the sky. If the subject is correctly exposed and the sky is clipped,
recover the sky with highlight compression; do not darken the subject to save a background that
carries no detail anyway.

- `exposure` is a uniform lift/drop. Small moves: ±0.1 to ±0.3; strong: ±0.5 or more.
- Check the highlights after every raise. A bright sky can clip before the subject looks correct.

### Highlight recovery: levels vs tone curve

This distinction matters more than any single slider value.

| Control | Behavior | Use it for | Avoid it for |
|---|---|---|---|
| `highlights` (levels band) | Proportional compression weighted by luma, soft headroom | Recovering bright sky/cloud/mist while keeping gradient shape | Adding a matte look |
| `tone_whites` (tone anchor) | Lowers the white ceiling; compresses the top range toward a flat value | Muting the whole top end, matte finish | Recovering detail; it flattens the gradient |
| `tone_highlights` (tone anchor) | Moves the 85% luma anchor; shapes the shoulder | Gentle shoulder shaping | Rescuing a blown sky on its own |

**Rule:** recover with `highlights`; shape with `tone_*`. If the sky looks flat after recovery,
the white anchor was used as a compressor.

### The tone curve

The curve is defined by five anchors on BT.709 luma:

| Anchor | Input luma | Default output | What it controls |
|---|---|---|---|
| `tone_blacks` | 0.00 | 0.00 | deepest blacks; raising lifts/crushes them |
| `tone_shadows` | 0.15 | 0.15 | shadow density; lowering deepens gullies and pines |
| `tone_midtones` | 0.50 | 0.50 | overall midtone placement |
| `tone_highlights` | 0.85 | 0.85 | shoulder brightness; raising lifts sunlit tops |
| `tone_whites` | 1.00 | 1.00 | white ceiling; lowering softens/flattens the top end |

The curve adds the same delta to every channel (preserving hue relationships), then clamps each channel.
A channel can therefore reach its ceiling before luma does; check channel clipping, not only
luma.

### Three useful curve shapes

**Gentle S-curve (depth without crunch)**

```
tone_blacks 0.005 · tone_shadows 0.13 · tone_midtones 0.515
tone_highlights 0.85 · tone_whites 0.99
```

Effect: darker shadows, slightly brighter upper midtones, open shoulder. This is the preferred
way to add three-dimensionality on a small or compressed file.

**Matte film shoulder**

```
tone_blacks 0.02–0.05 · tone_shadows 0.16–0.18 · tone_midtones 0.50
tone_highlights 0.80–0.84 · tone_whites 0.94–0.97
```

Effect: lifted blacks and a soft white ceiling. Use sparingly on landscapes; it removes the
deep black that gives rock and pine their weight.

**Highlight-recovery curve**

```
tone_blacks 0.00 · tone_shadows 0.14 · tone_midtones 0.50
tone_highlights 0.82–0.84 · tone_whites 0.98–1.00
```

Effect: the shoulder starts lower while the white point stays open, so bright areas roll off
without becoming a flat band.

### Contrast

`contrast` is a linear expansion around mid-gray. It is fast and blunt.

- Landscape: 10–18.
- Portrait: 8–15.
- Product: 10–20.
- Low-res/compressed: 8–14; prefer the curve above 20.
- Above ~25, check highlights and shadows immediately; the ends move first.

### Sky handling

A near-white sky contains whatever gradient the sensor recorded. If it is a uniform bright mist,
no slider will create cloud detail.

- Lower `highlights` (levels) until the brightest sky sits below the clipping threshold.
- Keep `tone_whites` close to 1.0 unless the goal is a matte look.
- Accept that the corner may stay nearly uniform; graying it further does not add information.
- If the sky is genuinely featureless and the composition allows it, crop or reframe rather than
  over-processing it.

### Low-resolution and compressed sources

- Prefer tone curves over clarity and contrast.
- Keep sharpening at 2–4 and clarity at 2–5.
- Do not add grain to "fix" blockiness; it adds noise on top of noise.
- The detail ceiling is the file, not the grade. The only real fix is the full-resolution original.

---

## 6. Color: saturation, vibrance, HSL

### Saturation vs vibrance

| Control | Behavior | Best use | Risk |
|---|---|---|---|
| `saturation` | Multiplies every pixel's chroma | Small global lift on a flat file | Clips already-saturated pixels into flat neon blocks |
| `vibrance` | Weighted toward low-chroma pixels; gated away from near-neutrals | "Make it vibrant" on landscapes, skin, mixed scenes | Too high re-amplifies the exact greens being tamed |

For a scene that is already vivid, the correct move is often **negative saturation plus targeted
HSL**, not a vibrance boost. Vibrance is for lifting the under-saturated middle, not for pushing
an already-saturated subject.

### HSL: per-family control

`PHOTO_HSV` adjusts hue, saturation and luminance per color family. The families overlap with soft
Gaussian weights, and the whole adjustment is gated out below ~30% saturation and full above ~50%.
That gate is deliberate: rock, concrete, haze and compression noise have unstable hue, and a
per-color LUT would turn their texture into mottled patches.

Hue is a slider: ±100 maps to ±40°. Positive/negative direction depends on the family.

| Family | Hue direction | Saturation | Luminance | When to use | Trap |
|---|---|---|---|---|---|
| Red | + toward orange, − toward magenta | −10 to +10 | ±5 | Lips, flowers, brick, fall leaves | Skin redness becomes sunburn |
| Orange | + toward yellow, − toward red | −5 to +10 | +5 to +15 | Skin, warm stone, autumn, sunset | Too much sat = orange skin |
| Yellow | + toward green, − toward orange | −10 to 0 | +5 to +20 | Sunlit grass, dry fields, gold light | Lifting too far creates neon |
| Green | + toward cyan, − toward olive | −30 to −10 | −15 to 0 | Foliage, grass, forest | Over-desaturating turns grass gray |
| Cyan | + toward blue, − toward green | −30 to −10 | −10 to 0 | Water, haze, distant ridges | Draining the lake while fixing the ridge |
| Blue | + toward violet, − toward cyan | −5 to +15 | −10 to 0 | Sky, water, shadows | Electric blue shadows |
| Magenta | + toward red, − toward blue | −15 to +10 | ±5 | Flowers, neon, some skin shadows | Unnatural skin/foliage |

### How to fix the common palette problems

**Neon foliage.** The problem is usually saturation, not hue. Lower `green_saturation` by 15–30,
lower `green_luminance` by 8–15, and shift `green_hue` slightly negative (toward olive). Do not
raise yellow luminance at the same time unless the goal is specifically to lift sunlit grass.
Check that the grass still has tonal variation; dead-flat green is over-correction.

**Cyan ridge or haze.** Shift `cyan_hue` positive (toward blue) by 8–15 and lower
`cyan_saturation` by 15–30. If the lake was praised, test it after the ridge fix: cyan controls
both. A hue-rotation-only fix can preserve the lake better but may leave cyan banding on rock; a
saturation cut cleans the ridge but drains water. Choose based on which element carries the frame.

**Orange skin.** Lower `orange_saturation`, raise `orange_luminance` slightly, and check white
balance. Warm highlights globally will warm faces first; protect orange before adding more
warmth. Do not push `orange_hue` toward red to "fix" saturation; that reads as sunburn.

**Dull water.** Raise `blue_saturation` modestly (5–12), lower `blue_luminance` slightly, and keep
`cyan_saturation` from dropping too far. If the water turns electric, the blue lift is too high.

**Green rock.** This is a gating failure in spirit: low-chroma stone should not be tinted by HSL.
Check neutral cast and WB first, then confirm `neutral_pixels_pct` is meaningful in `inspect`.
If the rock is genuinely green from lichen, leave it; not every green is a cast.

### Saturation targets

- Judge saturation **relative to the source**, not against a fixed ideal.
- If the source mean saturation is already 54 and the grade reads natural at 48, that is a success,
  not a failure. "Vibrant" means alive, not maximum chroma.
- Keep neon share (pixels at ≥90% saturation and high value) under ~1%; lower is better on foliage.
- A global saturation boost above +10 is usually a warning sign on an already-vivid landscape.

---

## 7. Split toning and classic looks

### What split toning does

Split toning puts one hue in the shadows and another in the highlights. The classic is warm
highlights and cool shadows, because skin and sunlight sit in the orange family while shade and
sky sit in the blue family. The separation creates depth: warm advances, cool recedes.

### How the wheels behave in this engine

- `hue` (0–360) **rotates** existing hue; it does not add a tint to neutral pixels.
- `saturation` **scales** existing chroma (1 + sat/100); a neutral pixel stays neutral.
- `luminance` lifts/lowers that tonal zone.
- `blending` (0–100, default 50) mixes the tinted LUT back toward identity. Lower = more abrupt
  zone separation; higher = smoother, potentially muddier.
- `balance` (−100..100) moves the zone boundaries. Positive widens midtones; negative lets the
  shadow/highlight zones take more of the frame.
- `strength` (0–1) is the look dial: effective blend = blending/100 × strength.

Because the wheels rotate and scale rather than tint, a global warmth move belongs in
`white_balance_temperature`, not in a highlight wheel with saturation. Use the wheels when the
image already has chroma to rotate; use WB or a LUT when neutral surfaces need a tint.

### Canonical teal-and-orange

| Zone | Hue | Saturation | Luminance | Notes |
|---|---|---|---|---|
| Shadows | 200–210° | 10–25 | −5 to 0 | Teal, not green; keep it blue-leaning |
| Midtones | neutral or 30–40° | 0–8 | 0 | A tiny warm bridge; do not let teal take the skin |
| Highlights | 35–45° | 10–20 | 0 to +5 | Warm skin and sun; lower sat than shadows |
| Global | 0 | 0 | 0 | Leave off unless the whole frame needs a unifying tint |

Blending 50–80; balance 0 to +20. Protect neutrals: white shirts, gray concrete and clouds must
stay neutral, or the image reads as tinted rather than designed.

### Teal and orange when there is no skin (wildlife, nature, architecture)

The look does not need a human face. The warm side can be fur, sand, wood, autumn leaves or sunlit
stone; the cool side can be sky, haze, water or shade. The mechanics stay the same, but three
things change.

**1. The subject's lit side and the sky can share the highlights zone.** On a bright outdoor frame
the pale sky and the brightest fur both sit above the 0.80 luma boundary, so one highlights wheel
does two jobs: it rotates the sky toward teal and the warm fur toward orange. That is efficient —
but always check both. If the sky turns mint while the fur turns yellow-green, the rotation is
wrong for one of them; move the hue a few degrees and re-measure.

**2. Never rotate neutral stone.** Beige rock, sand and dry grass sit in the midtones with almost
no chroma. A positive midtone rotation turns them olive; a negative one turns them salmon. Set
`midtones_hue` to **0** and get the warmth from `white_balance_temperature` plus midtone
saturation. Saturation preserves hue; rotation does not.

**3. Near-black markings stay neutral for free.** Leopard rosettes, zebra stripes and dark
crevices have almost no chroma, and the wheel scales saturation rather than adding a tint, so a
teal shadow wheel leaves them black. What it does affect is *coloured* shade — shadowed brown fur,
moss, dust — which is exactly the cool detail that sells the split.

**Low-chroma sources need the wheels, not HSL.** HSL is gated out below ~30% saturation. A source
whose mean saturation is under 20% (hazy daylight, compressed web JPEG, pale desert) will barely
respond to `PHOTO_HSV`; the wheel LUT is ungated and carries the look. Use HSL only for the few
pixels that are genuinely saturated.

**High-key sources need weight before warmth.** On a bright, sandy frame a warm WB plus a moderate
highlights wheel turns lit rock and fur chalky peach and leaves the sky pastel. Small repeated tweaks
do not fix this. The remaining cause is highlight luminance: bring the upper sky and brightest sand
down another 10–15 luma points with `blacks −10`, `shadows −22`, `highlights −58`, `tone_shadows
0.07`, `tone_highlights 0.74` and highlights `luminance −34`. Lower luminance gives chroma room;
tiny curve nudges are invisible on a thumbnail-sized file. `PHOTO_HSV` stays gated until sky chroma
clears 30%, so on a 17%-saturation source it is nearly inert; use a hue-targeted LUT if sky and
subject must move in opposite directions. On a file this small set `clarity 0` and `sharpness 0`:
the crunch is in the source and added sharpening only emphasises it.

**Worked recipe — deep teal and amber wildlife.** Source: 221×148, mean saturation 19%, pale blue
sky, warm beige rock, leopard with near-neutral rosettes.

```
WB 6250 K, tint +3
exposure −0.16 · contrast 28 · saturation +4 · vibrance 28
blacks −10 · shadows −22 · highlights −58
tone 0 / 0.07 / 0.48 / 0.74 / 0.96
clarity 0 · sharpness 0
wheels: shadows 190/36/−12 · midtones 0/52/0 · highlights 350/92/−34
blending 76 · balance 12
HSL: blue +4 hue / +16 sat / −22 lum; cyan +4 hue / +12 sat / −18 lum
```

What each part does: `blacks −10` and `tone_shadows 0.07` deepen the spots and crevices;
`highlights −58`, `tone_highlights 0.74` and highlights `luminance −34` pull sky and bright sand down
about 15 luma points; midtones 0/52 warms stone without rotating its hue. The HSL pass runs after
the wheel, once sky chroma clears the 30% gate, and only touches blue/cyan. Clarity and sharpness 0
stop the engine from adding crunch to an already compressed file.

Measured: sky 132/156/168 (hue 200.7°, saturation 29.1%), rock 157/148/117 (hue 48.8°, saturation
34.6%), shadow clip 2.88%, highlight clip 0.000%, neon 0.021%, mean saturation 29.5% against 19%
source, cast −2.8/−5.0 and no warnings. The earlier pass sat at sky luma 170 / hue 202° and rock
luma 162; this one reaches sky luma 152 and rock luma 148.

**Selective recovery.** A deep grade drags the subject's bright fur and sand down with the sky. Apply
a warm-hue LUT after the wheels — 15–65°, saturation above 0.08, value above 0.5, luminance +14% —
to lift only sunlit warm surfaces. On this source it raised fur from 127 to 138 luma and rock from
148 to 170 while the sky stayed at 164 and shadow clip fell to 2.44%. Above ~20% *uniform* lift the
peach returns; a shoulder that desaturates as it lifts avoids that. A hue-targeted LUT is the only
split available here: sky and bright fur share the highlights zone, so a single wheel always moves
both.

**White point on a compressed source.** The warm recovery still leaves the brightest fur and lit rock
about 20 luma below white. A second warm-hue LUT with a shoulder — 12–74°, value ramping 0.50–0.80,
`v += (1 − v) · 0.8 · w`, saturation −18% on the lifted pixels — raises the warm p90 from 203 to 222
and p99 from 218 to 240 with 0.000% highlight clip. Start the ramp lower (value 0.5) and the whole
coat turns chalky; the shoulder is what keeps it sunlit. Compose this with the +14% recovery LUT into
one `.cube`: sequential LUT passes add interpolation error for no visual gain.

**Trim after the LUT.** A white-point shoulder can still leave the brightest ridge within a few
luma of clipping. A final `PHOTO_CORRECTION` with `whites −6` and `highlights −3` placed after the
LUT pulls the ridge peak from 229 to 223 and clears every channel above 240, while the sky moves
0.7 luma and keeps its hue. Keep it as a separate op after the LUT rather than rebuilding the cube:
the correction is scene-specific, the LUT is reusable, and −6/−3 is small enough to read as recovered
headroom rather than a second grade. Past about −10 whites the sunlit rock starts to flatten.

Compression cleanup runs first, not last. `chroma_denoise 50` on the correction op applies `hqdn3d`
with luma at 0.001 and chroma at 5; on this source it cut sky chroma high-frequency from 0.178 to
0.160 without touching spot edges. It cannot remove luma blockiness — that is source-limited. Do not
add clarity or sharpness to compensate.

Final measured: sky 144/169/182 (hue 201.4°, saturation 28.7%, luma 165), leopard luma 145, rock
194/182/145 (luma 182), shadow clip 2.49%, highlight clip 0.000%, neon 0.018%, cast −2.6/−7.0, no
warnings. Against the previous pass the sky moved +1 luma, the leopard +7 and the rock +12; the top
decile of warm pixels moved +19. The delivered pass adds the −6/−3 trim: ridge peak 223, leopard
peak 225, no pixel above 240 in either PNG or JPEG, sky unchanged at 164 luma.

Reading the result: a sky at 200–203° with ~29% saturation and luma 150–165 reads deep teal; the same
hue at luma 170 reads pale blue. Rock at 170–182 with 33–35% saturation reads golden-cream; below
~150 it is dull, above ~190 at low saturation it turns chalky. A grade cannot add detail that the
221×148 source never had; run the same recipe on a higher-resolution original if one exists. If the
subject's shade turns olive, the midtones were rotated — return `midtones_hue` to 0.

### Other looks

| Look | Shadows | Highlights | Contrast | When it fits |
|---|---|---|---|---|
| Golden hour | Cool blue, low sat | Warm amber, moderate sat | Medium | Backlit portraits, late sun, nostalgia |
| Moody forest | Deep green-blue, low sat | Soft neutral, low sat | Medium-low | Overcast forest, fog, quiet mood |
| Bleach bypass | Neutral, lifted blacks | Silvery, desaturated | High | Gritty, overcast, concrete, editorial |
| Night blue | Deep blue, medium sat | Warm practicals untouched | Medium-high | City night, neon, rain |
| Autumn dusk | Deep brown/red, low sat | Burnt orange, moderate sat | Medium | Fall foliage, warm/cool sunset |
| Monochrome | — | — | High | Graphic subjects, texture, architecture |
| Analogous | One family | Neighboring hue | Low-medium | Soft, cohesive, minimal scenes |

### Restraint

- One side of the split should carry the scene; the other appears only where it matters.
- If the grade is visible as a "look" before it is visible as an image, reduce strength.
- The toggle test is mandatory: compare the graded and ungraded frame side by side.

---

## 8. Local control without masks

This engine is global: there are no brush, gradient or subject masks. Local-looking results come
from **selectivity**, not from spatial masks.

| Goal | Global technique | Why it works |
|---|---|---|
| Deepen mountain gullies | Lower `tone_shadows`; `shadows -3..-8` (levels) | Dark pixels are weighted more than bright ones |
| Lift sunlit grass | `yellow_luminance +10..+20` | The sunlit band is yellow-green; gray rock is untouched |
| Darken foreground foliage | `green_luminance −8..−15` | Green chroma is gated; neutral stone is not affected |
| Warm sunlit stone | Small WB warmth; `orange_luminance` modest | Warmth lands on lit, warm-hued surfaces; lake stays cool |
| Cool the shade | `cyan/blue` hue/saturation; shadows wheel | Cool chroma is concentrated in shade and haze |
| Separate water from sky | `cyan_hue` toward blue; `blue_saturation` modest | Water and haze sit in cyan; deep sky sits in blue |
| Add depth without clarity | S-curve on `tone_*` | Luminance separation, not local sharpening |

When a result genuinely requires a mask (a face that must stay warm while the background cools,
a sky replacement, a localized dodge), do it in an external editor and bring the file back. Do not
fake a mask with extreme global moves; the rest of the frame pays for it.

---

## 9. Scene playbooks

These are starting points, not laws. Adjust to the source's own palette and light.

### Alpine / lake (neutral stone, cool water, natural greens)

```
WB 6650–6800 K, tint 0–3
exposure +0.10 to +0.15 · contrast 14–18
shadows −3 · highlights −12 to −18
tone_blacks 0.005 · tone_shadows 0.13 · tone_midtones 0.515
tone_highlights 0.85 · tone_whites 0.99
saturation −8 to −10 · vibrance 22–26
clarity 4–5 · sharpness 2
HSL: yellow −2 hue / −9 sat / +18 lum
     green −6 hue / −24 sat / −11 lum
     cyan +10 hue / −30 sat / −5 lum
     blue +3 hue / +6 sat / −2 lum
```

Why: warm the stone without warming the lake; pull green chroma and luminance to keep grass out
of neon; rotate cyan toward blue and cut its saturation so the ridge reads atmospheric; keep the
finish soft for a small file.

### Vivid landscape (more punch, still natural)

Increase `vibrance` to 30–40, `contrast` to 18–22, and `clarity` to 6–8 only if the file is large.
Keep `green_saturation` negative and `cyan_saturation` negative. Add a gentle S-curve rather than
more global saturation.

### Moody forest

```
WB neutral or slightly cool
exposure −0.10 to 0 · contrast 12–16
tone_shadows 0.11–0.13 · tone_highlights 0.80–0.84
saturation −10 to −15 · vibrance 10–18
HSL: green −30 to −20 sat / −15 to −8 lum / hue toward olive
     cyan −20 sat (mist)
clarity 3–5 · sharpness 2–3
```

### Desert / canyon

```
WB 6800–7200 K · exposure +0.10
contrast 16–22 · highlights −10 to −20
saturation −5 · vibrance 20–30
HSL: orange +5 lum / +5 sat; yellow +8 lum; blue −5 lum / +5 sat
clarity 5–7 (large file) · sharpness 3–4
```

### Snow / winter

```
WB 6400–6600 K (keep a slight cool cast) · exposure +0.15 to +0.30
contrast 8–12 · highlights −20 to −30 · shadows +5 to +10
tone_whites 0.97–0.99 (do not flatten the snow)
saturation −5 · vibrance 10–15
HSL: blue −5 lum / +5 sat (shade); cyan −10 sat
clarity 2–4 · sharpness 2
```

### Coast / sea

```
WB 6500–6700 K · exposure +0.05
contrast 14–18 · highlights −10 to −18
vibrance 20–30 · saturation −5
HSL: cyan +8 hue / −15 sat; blue +8 sat / −5 lum
clarity 3–5 · sharpness 2–3
```

### Golden-hour portrait

```
WB 7000–7500 K · exposure +0.10
contrast 10–14 · highlights −10
tone_shadows 0.14 · tone_highlights 0.86
vibrance 15–25 · saturation −5
HSL: orange +8 to +12 lum / −3 sat; yellow +5 lum; blue −5 lum
clarity 2–3 · sharpness 2–4
```

Protect skin first: if the face turns orange, lower `orange_saturation` before lowering global
warmth.

### Studio / natural portrait

```
WB neutral (6500 K, tint 0)
exposure per subject · contrast 8–12
highlights −5 to −10 · shadows +3 to +8
vibrance 8–15 · saturation 0
HSL: orange +5 lum / −5 sat; red −5 sat
clarity 0–2 · sharpness 3–5
```

### Night / city

```
WB 3200–4500 K or keep the mixed cast
exposure −0.10 to +0.20 (protect practicals)
contrast 14–20 · highlights −15 to −25 · shadows −5 to +5
saturation −5 · vibrance 15–25
HSL: blue +5 sat / −5 lum (shade); orange +5 lum (practicals)
clarity 2–4 · sharpness 2–3 · grain 3–8
```

### Product / food

```
WB neutral · exposure per highlight
contrast 10–16 · highlights −15 to −25
saturation +5 to +10 · vibrance 10–20
clarity 4–6 · sharpness 4–6
```

Keep the background neutral and the specular highlights clean; colored gels are a lighting
decision, not a grading fix.

### Monochrome

Set `saturation −100` (or use a black-and-white conversion externally), then build separation
with `contrast`, `tone_*`, `clarity` and `grain`. Color filters (red/orange for skin, blue for
fog) are a shooting decision; do not fake them with HSL after desaturation.

---

## 10. Finishing: clarity, sharpness, grain, output

### Clarity

`clarity` is Contrast Adaptive Sharpen (`cas`): local midtone contrast with fewer halos than a
fixed unsharp kernel.

- Landscape: 3–6.
- Portrait: 0–3.
- Product: 4–6.
- Low-res/compressed: 2–5; above 6 starts amplifying blocks.
- Do not use clarity to fix flat midtones; use the tone curve. Clarity adds edge contrast, not
  tonal separation.

### Sharpness

`sharpness` is `unsharp` (lx=3, ly=3). **The default is 25**, which is strong for a small file.
Always set it explicitly.

- Low-res/compressed: 2–4.
- Full-res landscape: 3–6.
- Portrait: 3–5.
- Product: 4–8.
- Check at 100% for halos on high-contrast edges (horizon, branches, roof lines).

### Grain

`grain` maps to `noise=alls=N` (0–50).

- 2–5: subtle texture, can mask mild banding.
- 6–12: visible film character.
- Above 12: stylistic; it will soften detail and should not be used to hide compression blocks.

### Chroma denoise

`chroma_denoise` (0–100) runs `hqdn3d` at the start of a `PHOTO_CORRECTION` op: luma 0.001, chroma
`value / 10`, temporal 0.001. It smooths U/V only, so spots, whiskers and fur edges keep their luma
detail. Use 30–60 on a compressed sky or a noisy colour cast. It removes colour blotches, not luma
blockiness; if the sky is banded in brightness, the fix is a larger source, not more denoise. Keep
`clarity` and `sharpness` at 0 afterwards. Do not pass 0 for the luma terms — `hqdn3d` treats 0 as
"use the default", which silently turns on luma and temporal smoothing.

### Output

- Grade in 16-bit; encode once at the end.
- PNG/TIFF for the master; JPEG q2 4:4:4 for delivery when the platform accepts it.
- Avoid repeated JPEG round-trips; each one erodes fine foliage and rock texture.
- Keep the final resolution; do not upscale to fake detail.

---

## 11. Quality control: measure, don't guess

`photo-grading inspect IMAGE --json` reports:

- luma percentiles and mean;
- highlight/shadow clipping percentages;
- mean and p95 saturation;
- neon share (high saturation + high value);
- hue-family distribution;
- neutral-pixel cast (R−G, B−G) and the neutral share;
- conservative warnings.

### Reading the numbers

| Metric | Healthy range | What a bad value means |
|---|---|---|
| Highlight clipping | <0.1%, ideally 0% | Blown sky/rock; recover with `highlights`, not `tone_whites` |
| Shadow clipping | <1% | Crushed detail; lift `shadows` or `tone_shadows` |
| Neutral cast R−G / B−G | within ±4–5 of zero | Green/magenta or blue/yellow cast on neutrals |
| Mean saturation | source-relative; not above source by >5–8 unless intended | Over-saturated grade |
| Neon share | <1% | Flat neon blocks in foliage/water |
| p95 saturation | <90% | Pushing into clipping territory |
| Hue families | matches the scene | Unexpected magenta/cyan dominance = cast or HSL error |
| Region luma std | compare variants; +1–2 is meaningful | Flat midtones or lost separation |

### Region checks that catch what the whole frame hides

Measure small crops, not just the full image:

- **Mountain/slope:** luma std, p10/p90. Rising std = more depth; falling std = flatter.
- **Pine/shadow band:** p10. Falling p10 = deeper shadows.
- **Sunlit grass:** p90. Rising p90 = lifted highlights; if saturation also rises, watch neon.
- **Sky:** mean, p90, max, and share above 245. A sky can be unclipped and still read blown if it
  sits at 236–243 with no variation.
- **Boulder/neutral:** R−B and R−G. Warming should raise R−B slightly; a green shift is a cast.
- **Lake/water:** saturation and hue. Fixing the ridge can drain the lake; check both.

### Comparison method

1. Same crop, same zoom, same display.
2. Toggle between variants; do not compare from memory.
3. Check the grayscale version for luminance separation.
4. Check skin, sky, water and neutral stone first.
5. Take a break before the final judgment; color fatigue exaggerates saturation and warmth.

### Symptom → cause → fix

| Symptom | Likely cause | Fix |
|---|---|---|
| Neon green foliage | Green saturation/vibrance too high | `green_saturation −15..−30`, `green_luminance −8..−15` |
| Cyan/aqua ridge | Cyan hue too green or saturation too high | `cyan_hue +8..+15`, `cyan_saturation −15..−30` |
| Orange skin | Global warmth + orange saturation | Lower `orange_saturation`, raise `orange_luminance`, check WB |
| Flat midtones | Not enough luminance separation | S-curve on `tone_*`; do not reach for clarity |
| Crunchy edges | Clarity/sharpness too high for the file | Lower both; use tone curve for depth |
| Clipped sky | Highlights pushed by exposure/WB | Lower `highlights` (levels); keep `tone_whites` near 1 |
| Flat white sky | `tone_whites` used as a compressor | Restore `tone_whites` to 0.98–1.0; recover with levels |
| Gray/dead grass | Over-desaturated green | Raise `green_saturation` slightly; check luminance |
| Electric blue shadows | Blue saturation too high | Lower `blue_saturation`; shift hue toward cyan |
| Muddy split tone | Blending too high or both zones saturated | Lower blending/saturation; keep midtones neutral |
| Banding in gradients | 8-bit pipeline or heavy curves | 16-bit intermediates; gentle curve; light grain |
| Halos on edges | Unsharp too strong | Lower `sharpness`; prefer `clarity` at low values |
| Green cast on rock | HSL touching low-chroma pixels / WB | Check neutral cast; rely on the 30% chroma gate |

---

## 12. Parameter reference

### PHOTO_CORRECTION

| Parameter | Range | Default | Typical | Notes |
|---|---|---|---|---|
| `white_balance_temperature` | 2500–10000 | 6500 | 6500–7000 | Higher = warmer |
| `white_balance_tint` | −100..100 | 0 | −5..+5 | Positive = magenta |
| `exposure` | −10..10 | 0 | −0.3..+0.3 | Uniform lift |
| `contrast` | −100..100 | 0 | 8–20 | Linear around mid-gray |
| `highlights` | −100..100 | 0 | −10..−25 | Soft levels band; recovery |
| `shadows` | −100..100 | 0 | −8..+8 | Soft levels band |
| `blacks` | −100..100 | 0 | −5..+5 | Black point |
| `whites` | −100..100 | 0 | −5..+5 | White point |
| `saturation` | −100..100 | 0 | −12..+10 | Global multiplier |
| `vibrance` | −100..100 | 0 | 10–30 | Low-chroma weighted |
| `clarity` | 0–100 | 0 | 2–6 | CAS local contrast |
| `sharpness` | 0–100 | 25 | 2–5 | Always set explicitly |
| `grain` | 0–50 | 0 | 0–8 | `noise=alls` |
| `chroma_denoise` | 0–100 | 0 | 30–60 | `hqdn3d`, chroma only |
| `tone_blacks` | 0–2 | 0.00 | 0.00–0.02 | Anchor at L=0 |
| `tone_shadows` | 0–2 | 0.15 | 0.12–0.15 | Anchor at L=0.15 |
| `tone_midtones` | 0–2 | 0.50 | 0.49–0.52 | Anchor at L=0.50 |
| `tone_highlights` | 0–2 | 0.85 | 0.82–0.87 | Anchor at L=0.85 |
| `tone_whites` | 0–2 | 1.00 | 0.97–1.00 | Anchor at L=1.00; ceiling |

### PHOTO_HSV

| Parameter | Range | Notes |
|---|---|---|
| `{family}_hue` | −100..100 | ±40°; direction depends on family |
| `{family}_saturation` | −100..100 | Soft headroom; no channel clip |
| `{family}_luminance` | −100..100 | Soft headroom; lifts/darkens that family |

Families: red, orange, yellow, green, cyan, blue, magenta. Gated below 30% saturation, full at 50%.

### PHOTO_GRADING

| Parameter | Range | Default | Notes |
|---|---|---|---|
| `shadows_hue` / `midtones_hue` / `highlights_hue` / `global_hue` | 0–360 | 0 | Rotates existing hue |
| `*_saturation` | 0–100 | 0 | Scales existing chroma |
| `*_luminance` | −100..100 | 0 | Lifts/lowers that zone |
| `blending` | 0–100 | 50 | Higher = smoother, potentially muddier |
| `balance` | −100..100 | 0 | Positive widens midtones |
| `strength` | 0–1 | 1.0 | Look dial |

### Canonical natural-alpine recipe (reference)

```json
{"op_id": "corr", "type": "PHOTO_CORRECTION", "input": "source", "parameters": {
  "white_balance_temperature": 6800, "white_balance_tint": 2,
  "exposure": 0.13, "contrast": 16, "saturation": -10, "vibrance": 24,
  "clarity": 5, "sharpness": 2,
  "shadows": -3, "highlights": -18,
  "tone_blacks": 0.005, "tone_shadows": 0.13, "tone_midtones": 0.515,
  "tone_highlights": 0.85, "tone_whites": 0.99}}
{"op_id": "hsl", "type": "PHOTO_HSV", "input": "op:corr", "parameters": {
  "yellow_hue": -2, "yellow_saturation": -9, "yellow_luminance": 18,
  "green_hue": -6, "green_saturation": -24, "green_luminance": -11,
  "cyan_hue": 10, "cyan_saturation": -30, "cyan_luminance": -5,
  "blue_hue": 3, "blue_saturation": 6, "blue_luminance": -2}}
```

Measured on a 195×183 alpine source: 0% highlight clipping, 0.6% shadow clipping,
neutral cast −5.2/−2.3, mean saturation 48, neon 0.07%. The recipe is a starting point; the
source's own palette determines the final values.

---

## 13. Engine invariants: why grades fail

These are not style opinions. They are properties of the pipeline that determine whether a
recipe survives execution.

### Color math

- **Cube LUT order is red-fastest, blue-slowest** (Adobe Cube 1.0). A transposed axis turns hue
  and saturation moves into false-color orange/blue blocks. Every builder uses one iterator.
- **HSV sector math must be round-trip correct.** A scrambled sector table corrupts every hue
  rotation, wheel and HSL move.
- **White-balance gains are normalized and black-preserving.** Gains are relative to green, the
  largest gain is exactly 1 (no channel clip), and black stays black. Adding headroom to every
  channel turns dark pixels into colored speckles.
- **HSL and vibrance are chroma-gated.** Below ~30% saturation they are identity; full at ~50%.
  This keeps rock, concrete, haze and compression noise out of the color math.
- **Saturation and luminance use soft headroom.** Lifts approach white asymptotically and cuts
  approach black asymptotically, so a strong move cannot hard-clip a channel into a flat block.

### Tone math

- **The tone curve adds a luma delta to all channels, then clamps.** Hue relationships are
  preserved, but an individual channel can hit its ceiling before luma does. Check channel clipping.
- **`tone_whites` is a ceiling, not a recovery tool.** Lowering it compresses the top range toward
  a flat value. Use `highlights` (levels) for recovery.
- **Levels bands use smoothstep weights.** A hard threshold leaves a visible step where the band
  starts. If a band looks like a line across the image, the math regressed to a hard mask.

### Execution

- **Operations form a DAG.** Each op reads `source` or `op:<id>`; branches are independent. A
  silently linear chain grades a second branch on top of the first.
- **Intermediates are 16-bit PNG.** Heavy curves on 8-bit data posterize. The requested output
  format is encoded exactly once at the end.
- **Reuse identity hashes the actual input artifact, the engine version and the LUT builder
  fingerprint.** Hashing the original source lets a changed upstream op reuse a stale downstream
  file.
- **`sharpness` defaults to 25.** If a recipe omits it, the file is sharpened more than intended.
  Set it explicitly in every request.
- **JPEG delivery is q2 4:4:4.** Chroma subsampling smears fine foliage; 4:4:4 keeps color detail.
  The master stays PNG/TIFF.

### When a grade "doesn't apply"

| Observation | Check |
|---|---|
| Colors look transposed/orange-blue | LUT axis order |
| A hue rotation produces psychedelic colors | HSV sector table |
| Dark pixels have colored speckles | WB LUT black preservation |
| The second branch looks double-graded | Operation `input` wiring / DAG |
| Re-running after a code fix changes nothing | Reuse identity / cache |
| The same recipe looks different on another file | Source gamut, bit depth, resolution |
| The sky is flat after recovery | `tone_whites` used as a compressor |
| The grass is gray after taming | Green saturation/luminance over-cut |

---

## 14. Glossary

- **Cast** — an unwanted global tint, usually measured on near-neutral pixels.
- **Chroma** — color intensity independent of brightness; saturation in HSV terms.
- **Clipping** — a channel or luma hitting 0 or its maximum; information is lost.
- **Correction** — restoring neutral, exposure and tone to match the scene.
- **Grading** — deliberately moving away from neutral toward a mood or style.
- **HSL** — hue, saturation, luminance; per-color-family adjustment.
- **LUT** — a lookup table mapping input RGB to output RGB; used for looks and calibration.
- **Neon** — high-saturation, high-value pixels that read as artificial color.
- **Neutral pixel** — low-saturation pixel used to judge white balance.
- **Split toning** — different hues in shadows and highlights.
- **S-curve** — contrast curve that darkens shadows and brightens highlights.
- **Tone curve** — mapping of input luminance to output luminance at fixed anchors.
- **Vibrance** — saturation weighted toward low-chroma pixels, with neutrals protected.

---

## 15. References

The technique in this guide is consistent with the following sources; the implementation details
are specific to this skill.

- Adobe — Color Grading panel documentation and Camera Raw workflow guides.
- Fstoppers — cinematic orange-and-teal grading workflow.
- Impact Photography — three-way wheel values and blending/balance guidance.
- Markus Hagner Photography — restrained cinematic grading for portraits.
- Skylum — color correction vs grading, neutral protection, film-look attributes.
- PHLEARN — HSL and color mixer workflows.
- PhotographyIcon — RGB vs RYB wheels, complementary contrast, warm/cool depth.
- DaVinci Resolve colorist workflows — corrections vs look development, split toning, LUT
  strength, "do more with less".
- Lightroom color grading tutorials — foundation-first workflow, blending/balance, color fatigue,
  variation comparison.
- Pro Color Grading Playbook (Cullen Kelly, Walter Volpatto, Charles Haine; paraphrased) — working
  method: broad before narrow, overshoot then retreat, eyes first/scopes second, separation before
  saturation.
