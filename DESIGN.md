---
name: EdgeLegal
description: Contract contradiction checking with evidence you can see.
colors:
  night-ink: "hsl(260 38% 5%)"
  night-panel: "hsl(258 32% 8%)"
  night-raised: "hsl(258 28% 13%)"
  night-line: "hsl(258 25% 19%)"
  moon-text: "hsl(240 20% 97%)"
  dusk-muted: "hsl(258 15% 66%)"
  counsel-violet: "hsl(258 90% 69%)"
  orchid-glow: "hsl(280 85% 68%)"
  signal-cyan: "hsl(189 94% 58%)"
  paper-bg: "hsl(258 40% 98%)"
  paper-ink: "hsl(260 25% 10%)"
  paper-line: "hsl(258 25% 88%)"
  paper-violet: "hsl(263 70% 58%)"
  verdict-entail: "#10b981"
  verdict-contra: "#ef4444"
  evidence-amber: "#fbbf24"
typography:
  display:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(2.25rem, 5vw, 3.75rem)"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.5
  body:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.625
    fontFeature: "\"cv11\", \"ss01\""
  label:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    letterSpacing: "0.05em"
rounded:
  sm: "0.5rem"
  md: "0.75rem"
  xl: "1rem"
  2xl: "1.25rem"
  3xl: "1.75rem"
  full: "9999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    textColor: "#ffffff"
    rounded: "{rounded.xl}"
    padding: "8px 20px"
    height: "44px"
  button-secondary:
    textColor: "{colors.moon-text}"
    rounded: "{rounded.xl}"
    padding: "8px 16px"
    height: "36px"
  card-panel:
    backgroundColor: "{colors.night-panel}"
    textColor: "{colors.moon-text}"
    rounded: "{rounded.2xl}"
    padding: "24px"
  chip-source:
    rounded: "{rounded.full}"
    padding: "2px 8px"
---

# Design System: EdgeLegal

## Overview

**Creative North Star: "The Night Counsel"**

EdgeLegal is a premium AI product that lives in the dark. Dark is the default
theme. Surfaces are deep violet-black ink, lit from inside by a violet →
orchid → cyan brand glow. Frosted glass, soft blurred colour blobs, a faint
noise grain and a gradient-lit call to action make every screen feel like a
lit instrument panel at night.

The glow goes everywhere, `/app` included, but it is always *behind* or
*around* the evidence, never on top of it. Verdicts, reasoning and clause text
sit on surfaces opaque enough to read comfortably. The mood is confident,
calm and a little cinematic. Motion is smooth and physical, never bouncy
or playful.

A light "paper" theme exists and must keep working, but it follows dark rather
than leading.

**Key Characteristics:**
- Dark-first, violet-black ink with a three-stop brand gradient.
- Frosted glass for chrome (headers, toolbars, tabs) and premium panels.
- Ambient life: slow morphing blobs and grain behind content.
- Evidence always legible: text on near-opaque surfaces.
- Semantic verdict colours (emerald / red / neutral) never replaced by brand hues.

## Colors

Deep night ink with a luminous violet-to-cyan brand, plus strictly semantic
verdict colours.

### Primary
- **Counsel Violet** (counsel-violet): primary actions, focus rings, step
  numbers, active states. Light-theme equivalent is **Paper Violet**.

### Secondary
- **Orchid Glow** (orchid-glow): the middle stop of the brand gradient; glow
  and blob tint only, never text.

### Tertiary
- **Signal Cyan** (signal-cyan): the far end of the brand gradient; progress
  fills and "live" accents.

### Neutral
- **Night Ink** (night-ink): page background.
- **Night Panel** (night-panel): card / panel base.
- **Night Raised** (night-raised): secondary surfaces, inputs, list rows.
- **Night Line** (night-line): borders and dividers.
- **Moon Text** (moon-text): primary text.
- **Dusk Muted** (dusk-muted): secondary text, captions.
- Light theme: **Paper Bg**, **Paper Ink**, **Paper Line**.

### Semantic
- **Verdict Entail** (verdict-entail): Entailment, success, classifier-accepted.
- **Verdict Contra** (verdict-contra): Contradiction, errors.
- **Evidence Amber** (evidence-amber): the citation highlight in the PDF viewer.

### Named Rules
**The Verdict Owns Its Colour Rule.** Emerald means Entailment and red means
Contradiction. No decorative use of either, and never recolour a verdict with
the brand gradient.

**The Gradient Is A Light Source Rule.** The brand gradient appears as glow,
fills, and the primary CTA, and on a single emphasised word in the display
text at most. It is not a background for body text.

## Typography

**Display / Body Font:** Inter (with ui-sans-serif, system-ui)

**Character:** One neutral grotesk throughout; hierarchy comes from weight,
size and tracking, with stylistic sets cv11 and ss01 on for a crisper, more
technical feel.

### Hierarchy
- **Display** (700, clamp 2.25–3.75rem, 1.1): landing hero only; one word may
  carry the brand gradient.
- **Title** (600, 1rem): panel headings in `/app`.
- **Body** (400, 0.875rem, 1.625): reasoning text and clause quotes.
- **Label** (600, 0.75rem, uppercase, 0.05em): section labels, verdict label.

## Layout

`/app` is a dashboard: a 400px left column (Upload → Hypothesis → Report,
stacked and independently scrolling) and a flexible PDF viewer on the right,
inside a 1600px max container with 24px gutters. It collapses to a single
column below `lg` (1024px). The sticky 64px glass header spans the full width.
The landing page uses a 72rem (max-w-6xl) container with generous vertical
sections.

## Elevation & Depth

Depth comes from light, not heavy shadows: translucent glass layers over
ambient blobs, hairline borders, and coloured glow shadows under brand
elements (`shadow-primary/25`, rising to /40 on hover). Base cards carry
only a small shadow.

### Named Rules
**The Readable Glass Rule.** Glass may frame and float panels, but any surface
holding reasoning or clause text is at least ~85% opaque in dark and ~90% in
light.

## Shapes

Soft, generous rounding: 12px (`xl`) on buttons and inputs, 20px (`2xl`) on
cards and panels, fully round pills for chips and badges. Hairline 1px borders
everywhere; dashed 2px only for the drop zone.

## Components

### Buttons
- **Shape:** gently rounded (12px).
- **Primary:** brand gradient fill, white text, violet glow shadow; brightens
  on hover.
- **Secondary:** glass fill with foreground text.
- **Ghost / Outline:** transparent, subtle tint on hover.
- **Focus:** 2px violet ring with background offset.

### Chips / Badges
- **Source chip:** pill with a coloured hairline border. Emerald for
  "Classifier", violet for "LLM-verified".
- **Glass badge:** landing-page eyebrow with a pulsing live dot.

### Cards / Containers
- **Corner Style:** 20px.
- **Background:** Night Panel (dark) / white (light).
- **Border:** 1px Night Line.
- **Internal Padding:** 24px.
- **Step header:** a 24px violet-tinted square with the step number, then a
  semibold title.

### Inputs / Fields
- **Style:** 12px radius, 1px border, background fill.
- **Focus:** 2px violet ring with offset.

### Navigation
- Sticky frosted glass header with logo, theme toggle, secondary button.

### Evidence Highlight (signature)
- Amber outlined box with a warm glow over the cited region of the PDF page.

## Do's and Don'ts

### Do:
- **Do** default to dark and verify every change in light too.
- **Do** keep reasoning and clause text on near-opaque surfaces.
- **Do** use the brand gradient for the primary action and progress fills.
- **Do** keep motion smooth and short (≤ 400ms for UI state changes).

### Don't:
- **Don't** use emerald or red decoratively.
- **Don't** put body text directly on blobs, gradients, or low-opacity glass.
- **Don't** add new typefaces; Inter carries everything.
- **Don't** show accuracy, savings, or latency figures that the project has not
  measured.
