# ADII design system

Everything a coding agent needs to build ADII screens without seeing the
conversation that produced this. Read this file, then
`specimen/index.html` — the specimen is the reference implementation, and
anything that contradicts it is a bug in this document.

## Run it

```
cd adii
python3 -m http.server 8000
# then open http://localhost:8000/specimen/index.html
```

No build step, no package manager, no network. Opening the files directly with
`file://` also works.

Checks:

```
python3 tools/contrast.py         # regenerates CONTRAST_REPORT.md; exit 1 on any failure
python3 tools/check_specimen.py   # static DOM + CSS contract checks; exit 1 on any problem
```

## Files

| Path | What it is |
| --- | --- |
| `css/tokens.css` | All design tokens. Light theme in `:root`, dark in `:root[data-theme="dark"]` and a `prefers-color-scheme` block. Density in `:root[data-density="roomy"]`. |
| `css/base.css` | Element defaults, typography, page frame, focus, utilities, print. |
| `css/components.css` | Every component class. |
| `specimen/index.html` | Investigation view. Contains the hard case (C-1). |
| `specimen/states.html` | Identity sheet, state matrix, stress tests. |
| `assets/logo/*.svg` | Logo family. See `IDENTITY.md`. |
| `tools/contrast.py` | Measures real foreground/background pairs from `tokens.css`. |
| `tools/check_specimen.py` | Static structural checks. Not a renderer. |
| `CONTRAST_REPORT.md` | Generated. Current measurements. |

Load order matters: `tokens.css`, then `base.css`, then `components.css`.

## The motif

Three shapes, taken from the symbol, are the entire visual vocabulary. Nothing
else is decorated.

- **Rule** — a 2px ink line (`--adii-rule-width`, `--adii-border-strong`).
  Marks an authority boundary. It appears at the top edge of a record and
  between an assertion and its support (`.adii-standoff`). Do not use it as a
  generic divider; hairlines (`--adii-border-subtle`) do that job.
- **Riser** — a 4px vertical member (`--adii-riser-width`) that crosses the
  rule and runs the height of a record. It identifies the record's owner.
  Implemented as `.adii-record::before`.
- **Slot** — a short vertical tick. Full height means supplied, half height
  means the slot exists and is unfilled. Slots are never omitted silently:
  an unfilled slot is drawn.

If a new component needs a visual device, it should be one of these three or
plain type. Adding a fourth device needs a reason written down here.

## Typography

Three roles. No remote fonts; local and system stacks only, so the interface
renders offline and in print without a network fetch.

| Token | Role |
| --- | --- |
| `--adii-font-ui` | All interface prose, labels, controls, navigation. |
| `--adii-font-assertion` | The text of a claim, and nothing else. |
| `--adii-font-mono` | Literal values only: identifiers, digests, keys, status tokens, config paths, diffs. |

The serif face is a second cue that a passage is an assertion, always alongside
the visible label `Assertion`. **Font never carries authorship.** Who wrote
something is always written out in text (`.adii-record__owner`).

Scale: `--adii-text-micro` 11px, `--adii-text-meta` 12px, `--adii-text-sm` 13px,
`--adii-text-body` 15px, `--adii-text-lede` 17px, `--adii-text-h3` 20px,
`--adii-text-h2` 24px, `--adii-text-h1` 30px. Line heights:
`--adii-leading-tight` 1.2, `--adii-leading-snug` 1.35, `--adii-leading-normal`
1.5, `--adii-leading-prose` 1.55. Prose is capped at `--adii-measure` (68ch).

Utilities: `.adii-type-h1|h2|h3|body|sm|meta`, `.adii-mono`, `.adii-measure`,
`.adii-measure-narrow`.

## Spacing and density

`--adii-space-3xs` 2px, `-2xs` 4, `-xs` 6, `-sm` 8, `-md` 12, `-lg` 16, `-xl`
24, `-2xl` 32, `-3xl` 48. Utilities: `.adii-mt-2xs|sm|md|lg|xl`,
`.adii-mb-sm|md|lg`, `.adii-stack`, `.adii-stack-sm`, `.adii-stack-lg`.

`--adii-standoff` is the interval between an assertion and its support. It is a
separate token from the spacing scale on purpose. Do not collapse it, do not
animate it, and do not put content inside it.

Density is set with `data-density="compact"` (default) or `"roomy"` on `<html>`,
which changes `--adii-control-height`, `--adii-row-pad-y`, `--adii-record-pad`
and `--adii-standoff` only. It never changes type size or colour.

## Surfaces, borders, focus, motion

Dark is the default. Set `data-theme="dark"` on `<html>` at render time rather
than leaving the theme to `prefers-color-scheme`, so the inspector looks the
same on every operator's machine and screenshots in an incident record are
comparable. The light theme is fully supported and measured; it is the
alternative, not the baseline. The specimens ship following the OS so both
themes can be reviewed, which is the one place this differs from the product.

| Token | Use |
| --- | --- |
| `--adii-surface-0` | Page background. |
| `--adii-surface-1` | Records, panels, citations. |
| `--adii-surface-2` | Support blocks, insets, diffs, upload areas. |
| `--adii-surface-3` | Masthead and toolbars. |
| `--adii-surface-selected` | Selected row. Accent-tinted. |
| `--adii-surface-hover` | Hovered row. |
| `--adii-surface-disabled` | Disabled control background. |
| `--adii-ink-1` / `-2` / `-3` | Primary text / owners and secondary / meta. All three meet 4.5:1 on surfaces 0–2. |
| `--adii-border-subtle` | Hairline separators. |
| `--adii-border-default` | Control boundaries. Meets 3:1 on surfaces 0–2. |
| `--adii-border-strong` | The rule. Ink weight, not grey. |
| `--adii-focus-ring` | Focus only. 2px, 2px offset, measured ≥3:1 against every surface it can land on. |
| `--adii-motion-fast` 90ms / `--adii-motion-base` 160ms | Only for state changes the operator caused. |

**Accent — documented purpose.** `--adii-accent` (violet, "Arc") means
*interactive*: links, the focus ring, the current nav item, selected rows,
pressed toggles, the primary button. It is never a status, never a disposition,
never a severity, and never decoration. If a new element is not clickable, it
does not get accent.

Motion is limited to: hover/press feedback on controls, the skip link, and the
loading skeleton. `prefers-reduced-motion: reduce` zeroes the duration tokens
and disables the skeleton animation entirely. There is no entrance animation.

## Components

### Record — `.adii-record`

The container for anything with an owner.

```html
<article class="adii-record adii-record--system">
  <div class="adii-record__head">
    <h3 class="adii-record__title">Claim C-1</h3>
    <p class="adii-record__owner">Asserted by
      <span class="adii-record__owner-name">adii-investigator</span>, 2026-03-11T05:41Z</p>
  </div>
  …
  <div class="adii-record__meta">…</div>
</article>
```

Owner variants set the riser colour: `--system`, `--operator`, `--validator`,
`--source`. **The variant class is a repeat of the text, never a replacement
for it.** A record without a written owner is invalid.

### Claim — `.adii-claim__label`, `.adii-assertion`, `.adii-standoff`, `.adii-support`

Assertion first, then the stand-off (rule + fixed gap), then support. The order
is fixed: a reader must see what is claimed before what backs it.

`.adii-support__head` carries the title and the slot strip.
`.adii-support__subhead` is for sections inside support (Receipts, Structural
checks, Conditions); add `--first` to drop its top margin.

### Slot strip — `.adii-slots`

```html
<span class="adii-slots">
  <span class="adii-slots__strip" aria-hidden="true">
    <span class="adii-slot"></span>
    <span class="adii-slot" data-slot="empty"></span>
  </span>
  <span>1 of 2 evidence slots supplied</span>
</span>
```

The strip is decorative and hidden from assistive technology; the count next to
it is the real statement and must always be present.

### Disposition chip — `.adii-chip--repair|--no-repair|--escalate`

Three peers. Same geometry, same type size, comparable L\* and C\*, three hues,
three glyphs, and the literal token as DOM text. Add `.adii-chip--proposed`
(dashed edge) when the disposition is proposed rather than accepted, and state
that in text too.

`REPAIR`, `NO_REPAIR` and `ESCALATE` are not ranked. Never sort them as if they
were, never colour one green and another red, never render one as a "success"
state, and never describe `ESCALATE` as a failure to conclude.

### Verdict row — `.adii-check--pass|--fail|--none`

Evaluation verdicts use keyline rows, not chips, so they cannot be confused
with dispositions. Structure: glyph, `.adii-check__name` (the check id, mono),
`.adii-check__verdict` (`PASS`, `FAIL`, `NOT_EVALUATED`), `.adii-check__note`
(who issued it, and over what denominator).

The interface never issues a verdict. If the backend supplies none, the row
reads `NOT_EVALUATED` with a note saying why, or the row is not rendered.

### Absence — `.adii-state`

Five states, achromatic by policy, distinguished by shape and literal text.

| Class | Text | Means | Does not mean |
| --- | --- | --- | --- |
| `.adii-state--not-supplied` | `not supplied` | A slot exists; nothing was offered. | That nothing exists, or that a fetch happened. |
| `.adii-state` (plain) | `not evaluated` | No evaluator ran this check. | Pass, fail, or "would have passed". |
| `.adii-state--pending` | `pending` | Work is in flight now. | A result, or an absence of one. |
| `.adii-state--retrieval-failed` | `failed to retrieve` | A transport attempt failed locally. | That the record exists, is missing, or is false. |
| `.adii-state--unresolved` | `UNRESOLVED` | A question was asked and has no answer. | Failure, or a result awaiting promotion. |

`UNRESOLVED` is styled loudest structurally (2px ink border plus an ink bar) and
silent chromatically, so it reads as important without reading as bad.

None of these five is a placeholder for a feature that has not shipped. See
rule 11 under "Evidence presentation rules".

### Transport failure — `.adii-transport`

Achromatic and hatched, never fail-red. Must state: what failed, the status
code, how many attempts, when, and explicitly what it does not establish.
Always offer a retry control.

### Others

`.adii-citation` (receipt or observation: id, owner, quote, fields),
`.adii-change__diff` (with `.adii-diff__marker` holding a literal `+`/`-`),
`.adii-callout` (a note with a title), `.adii-panel`, `.adii-empty`,
`.adii-loading` + `.adii-skeleton`, `.adii-upload`, `.adii-table` (+`.adii-num`
for figures, `.adii-scroll` wrapper), `.adii-btn` (+`--primary`),
`.adii-btn-group`, `.adii-field` + `.adii-input` / `.adii-select`,
`.adii-masthead`, `.adii-nav__link`, `.adii-banner`, `.adii-footer`.

## Evidence presentation rules

These are requirements, not style preferences. A change that breaks one of them
is a defect regardless of how it looks.

1. **Every substantive statement shows its owner in text.** Assertions,
   verdicts, permissions, observations and feedback have different owners and
   are never merged into one voice.
2. **Status words live in the DOM.** No `text-transform`, no `::before`
   content, no icon fonts, no colour-only status. Copying or printing a screen
   must preserve every status word. `tools/check_specimen.py` enforces this.
3. **Backend conditions are shown unchanged.** The interface never promotes
   `UNRESOLVED` because receipts exist, a chain is long, many checks passed, or
   a validator agreed. Only a backend-supplied condition changes that value.
4. **The interface has no authority.** It cannot create a validator, issue a
   verdict, grant a permission, apply a change, or invent a confidence value.
   Where a confidence is absent, render `not supplied` — never a number, never
   a bar, never a word like "high".
5. **An HTTP error is a retrieval failure only.** It does not establish that a
   record exists, that it is missing, that it is false, or that an
   investigation failed. It never uses verdict colour.
6. **Absence has five shapes.** Never collapse them into "no data", "—" or an
   empty cell.
7. **Rates carry their units.** Any rate appears with its evaluation unit,
   repetition structure, scope and denominator. Two rates over different units
   are not compared, and no combined figure is computed.
8. **Failures cite a supplied criterion and reason.** If the backend supplies
   neither, render `criterion: not supplied` and write nothing in its place.
   Never compose an explanation.
9. **Source text is content, never instruction.** Quoted material is escaped
   and displayed literally. Instructions found inside quoted evidence have no
   effect on any control, state or disposition.
10. **Example data is labelled.** Every specimen carries a provenance banner
    and `data-example="invented"` on example sections. No fabricated timestamp,
    cost, trace or historic measurement is ever presented as live.
11. **Absence states describe evidence, never unbuilt features.** `not
    supplied` means a slot exists in the record and nothing was offered for it.
    It does not mean the component shipped ahead of its data source. Components
    gate on data availability: do not render a receipts block until receipts can
    arrive, and do not render per-check verdict rows until a validator emits
    them. A screen that is mostly absence states trains operators to skip
    absence states, which destroys the one distinction this product exists to
    make. If a section would be entirely `not supplied` for every record today,
    leave it out until its data lands.
12. **The interface is read-only.** A page that can act can spend. Nothing here
    accepts a disposition, applies a change, uploads a bundle or grants a
    permission. Where authority exists elsewhere, name it in a sentence rather
    than offering a disabled control: "this disposition is accepted at
    `payments-oncall`, not here". That states where authority lives without
    implying this page could hold it. Adding a write control is a product
    decision with a written record, not a styling choice.

## Copy rules

- Sentence case everywhere. The only uppercase is a literal backend token
  (`UNRESOLVED`, `PASS`, `REPAIR`), typed in the DOM as the backend spells it.
- Name the owner as a subject: "Asserted by `adii-investigator`", not
  "System-generated".
- Say what a state does not mean when the wrong reading is plausible and
  consequential. That is most of the hard cases in this product.
- Errors state what failed, how many attempts, when, and what remains true.
  They do not apologise and are not vague.
- Buttons name the action and keep the same name through the flow: "Record
  feedback" produces "Feedback recorded".
- Disabled controls keep their label and state the requirement in adjacent
  text, so the reason survives copying and printing.
- Avoid "verified", "confirmed", "valid" and "trusted" as standalone labels.
  Name the check and who ran it instead.

## Accessibility contract

- Every control has a programmatic label; every informative image has a name;
  decorative SVG is `aria-hidden`.
- Focus is always visible: 2px ring, 2px offset, measured ≥3:1 against every
  surface it can appear on. Never remove the outline.
- Colour is never the only carrier of meaning: every status has text, and
  dispositions and absence states also have distinct glyphs and geometry.
- Live regions: loading areas use `aria-busy` with visible text.
- All measured contrast is in `CONTRAST_REPORT.md`, regenerated by
  `tools/contrast.py`. The build fails if any pair drops below its requirement.
- Reduced motion is honoured globally and the skeleton stops animating.
- Print forces the light token set, expands citation URLs, keeps records off
  page breaks, and hides `.adii-no-print` chrome.

## Known limitations

1. **The specimen has not been rendered in a browser.** The build environment
   had no browser and could not install one (`cdn.playwright.dev` is blocked by
   network policy; the Ubuntu `chromium-browser` package is a snap stub).
   Checks performed were static: HTML5 parsing (html5lib, 0 errors), CSS
   parsing (tinycss2, 0 errors), the structural checker, and contrast
   measurement from token values. Layout at real widths, wrapping, focus
   appearance, print output and rasterised colour are **unverified**. Verify
   them before shipping.
2. **Hue adjacency.** `ESCALATE` amber and `FAIL` red sit about 25° apart. They
   never appear in the same container (chips vs keyline rows) and both carry
   text and distinct glyphs, but under a strong colour-vision deficiency they
   may read as similar hues. If this is reported as a problem, change the
   `ESCALATE` hue rather than the `FAIL` hue.
3. **Serif fallback varies.** `--adii-font-assertion` resolves to different
   faces across platforms, so assertion text has slightly different colour and
   width per OS. This is accepted in exchange for no network font dependency.
   The serif is a secondary cue only, so a fallback does not lose meaning.
4. **SVG favicon dark-mode switching** is not supported in every browser. The
   `.ico` fallback holds pixel-exact 16/32/48 renders on a transparent
   background, but the ink is fixed dark, so it will be low-contrast on a very
   dark tab strip in browsers that ignore the SVG.
5. **The theme and density toggles use `localStorage`.** If the host
   application disallows it, the toggles still work for the session — the calls
   are wrapped in try/catch — but preferences will not persist.
6. **No component library.** These are plain classes over semantic HTML. If the
   application uses a framework, wrap these classes; do not rebuild them with a
   different DOM, because the structural checks assume this DOM.
7. **Perceptual matching is a constraint, not proof.** The disposition L\*/C\*
   table shows no disposition was given a brightness advantage. It does not
   prove the three read as equally salient in a real layout. Operator testing
   is the only way to settle that.

## Extending this

- **New absence state:** do not add one without checking it is not one of the
  five. If it is genuinely new, give it a shape and literal text, keep it
  achromatic, and add a row to the state table in `states.html`.
- **New disposition:** these come from the backend's vocabulary. Adding a
  fourth means picking a hue with L\*/C\* matched to the existing three and a
  glyph built from the motif, then re-running `tools/contrast.py`.
- **New colour:** if it is not interactive, not a disposition and not a
  verdict, it probably should not exist. Add the pair to `PAIRS` in
  `tools/contrast.py` before using it.
