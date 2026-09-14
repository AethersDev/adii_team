# ADII identity

## Three concepts explored

Each was drawn as vector geometry and rasterised at 16, 24, 48 and 128px on
light and dark before judging. Small-size behaviour decided the outcome.

**A — Stand-off.** An assertion rule, a riser crossing it, and a row of support
slots below with one slot left unfilled. The distance between the rule and the
slots is the interval that evidence has to cross before it justifies anything.

**B — Caliper.** Two opposing jaws bracketing a subject: inspection as
measurement. It reads as `[ · ]` at 16px, which is the house style of a
hundred developer tools, and it says nothing about absence or authority. Its
half-unit arm thicknesses also blurred at 16 and 24px.

**C — Custody seam.** Two offset planes joined by a perpendicular jog, with a
notch: a handoff between owners. At small sizes it reads as a descending step,
which looks like a metric falling — the wrong connotation for a system whose
outcomes are peers. It also encodes nothing about evidence.

## Selected: A, Stand-off

It is the only one of the three that carries three of the product's
non-negotiables in a single piece of geometry:

- **An assertion is separate from its support.** The rule sits above the slots
  with a visible gap. They are not the same object and are not touching.
- **Absence is a state, not a blank.** One slot is deliberately drawn at half
  height. The mark contains something unfinished, permanently. An investigation
  system whose logo looks complete is lying in its first impression.
- **Crossing a boundary is an act.** The riser is the one member that passes
  through the rule. That is what escalation is: not a failure, a transfer to a
  party with authority the system does not hold.

It also yields an interface grammar rather than a sticker. The rule, the riser
and the slot are used throughout the UI as structure — record ownership, the
stand-off between a claim and its support, evidence counts, and the three
disposition glyphs — so the identity is load-bearing rather than applied.
See DESIGN_SYSTEM.md, "The motif".

Rejected on purpose: brains, circuits, sparkles, shields, chat bubbles, and a
gradient letter A.

## Geometry

Drawn on a 32-unit grid, all coordinates even, so the mark lands on whole
pixels at 16px and 32px.

| Element | Rect (x, y, w, h) |
| --- | --- |
| Riser | 4, 4, 4, 24 |
| Rule | 4, 12, 24, 4 |
| Support slot 1 | 12, 20, 4, 8 |
| Unfilled slot | 18, 24, 4, 4 |
| Support slot 2 | 24, 20, 4, 8 |

Wordmark: monolinear geometric, 4-unit stroke, 24-unit cap height, flat-apex A.
The A's crossbar sits at y 12–16 — the same band as the symbol's rule — so in
the horizontal lockup the crossbar and the rule are one continuous line. The
high crossbar is not a styling flourish; it is that alignment.

The mark is monochrome and has no colour variant. It uses `currentColor`, so it
inherits ink from its context and cannot drift into a status colour.

## Assets

| File | Use |
| --- | --- |
| `adii-symbol.svg` | Canonical symbol, 32-unit grid, `currentColor`. Use at 24px and above. |
| `adii-symbol-16.svg` | 16-unit grid with `shape-rendering="crispEdges"`. Use below 24px. |
| `adii-wordmark.svg` | Wordmark alone. |
| `adii-lockup-horizontal.svg` | Default lockup. |
| `adii-lockup-stacked.svg` | Square placements. |
| `favicon.svg` | 16-unit grid, switches ink for dark browser chrome. |
| `favicon.ico` | 16/32/48 raster fallback, transparent background, generated from the SVG. |
| `adii-appicon.svg` | Dark tile with reversed mark, 26-unit corner radius. |
| `adii-clearspace.svg` | Clear-space diagram. |
| `adii-misuse.svg` | Six misuse examples. |

The SVGs are the canonical artwork. No raster file is canonical; `favicon.ico`
is derived output and is regenerated from the SVG, never edited.

The SVGs carry geometry and a `<title>` and nothing else. An export pipeline
once injected an 8 KB C2PA manifest into every one of them, which is 94 % of the
file and a provenance claim nobody authored. `tools/check_specimen.py` now fails
if `<metadata>` reappears in `assets/`. Keep these files hand-editable.

## Clear space and minimum sizes

Clear space is **x = one quarter of the symbol height** (8 of 32 design units)
on all four sides. Nothing enters it.

| Asset | Screen minimum | Print minimum |
| --- | --- | --- |
| Symbol | 16px (use the 16-grid file) | 5mm |
| Horizontal lockup | 96px | 25mm |
| Stacked lockup | 64px | 18mm |

Below 96px, drop the wordmark and pair the symbol with ordinary text.

## Misuse

Do not stretch or condense; do not recolour into verdict or disposition
colours; do not fill the empty slot; do not rotate; do not outline, emboss or
add a shadow; do not place below 3:1 contrast against the background. Filling
the empty slot is the worst of these — it inverts what the mark says.

## Accessibility

Where the mark conveys information it carries an accessible name: `role="img"`
with `<title>` in the standalone files, and `aria-label="ADII"` where inlined
in the masthead. Where it is decorative and adjacent text already names the
product, it is `aria-hidden`. The disposition glyphs are always `aria-hidden`
because the chip text carries the meaning.

## No legal clearance

This is original artwork made for this brief. **No trademark, design-right or
prior-use search has been performed, and nothing here should be read as
clearance.** Before public use, have the wordmark and symbol cleared in the
relevant classes and jurisdictions.
