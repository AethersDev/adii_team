#!/usr/bin/env python3
"""Measure real foreground/background pairs used by the ADII specimen.

Reads css/tokens.css, extracts the light and dark theme values, and checks the
combinations that actually occur in the DOM -- including hovered, selected,
disabled and tinted surfaces, which are the ones usually skipped.

Also reports CIELAB L* and C* for the three disposition families. Matched
perceptual coordinates are a starting constraint, not proof of equal salience:
size, glyph weight, surrounding density and reading order all move salience.
Treat the L*/C* table as evidence that no disposition was accidentally given a
brightness advantage, not as evidence that all three read equally.

Usage: python3 tools/contrast.py [--fail-under-report]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKENS = ROOT / "css" / "tokens.css"

HEX = re.compile(r"(--adii-[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;")


def parse_themes(css: str):
    """Return (light, dark) token dicts.

    Light = the :root block. Dark = :root overridden by [data-theme=dark].
    """
    light, dark_over = {}, {}
    root_block = re.search(r":root\s*\{(.*?)\n\}", css, re.S)
    dark_block = re.search(r':root\[data-theme="dark"\]\s*\{(.*?)\n\}', css, re.S)
    if root_block:
        light = dict(HEX.findall(root_block.group(1)))
    if dark_block:
        dark_over = dict(HEX.findall(dark_block.group(1)))
    dark = dict(light)
    dark.update(dark_over)
    return light, dark


def srgb_to_lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rel_lum(hexstr):
    r, g, b = (int(hexstr[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * srgb_to_lin(r) + 0.7152 * srgb_to_lin(g) + 0.0722 * srgb_to_lin(b)


def ratio(fg, bg):
    a, b = rel_lum(fg), rel_lum(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def to_lab(hexstr):
    r, g, b = (srgb_to_lin(int(hexstr[i:i + 2], 16)) for i in (1, 3, 5))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 1.00000
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)
    fx, fy, fz = f(x), f(y), f(z)
    L = 116 * fy - 16
    a_ = 500 * (fx - fy)
    b_ = 200 * (fy - fz)
    return L, (a_ ** 2 + b_ ** 2) ** 0.5


# (foreground, background, where it occurs, required ratio, note)
PAIRS = [
    ("ink-1", "surface-0", "body text on the page", 4.5, "text"),
    ("ink-1", "surface-1", "body text inside a record", 4.5, "text"),
    ("ink-1", "surface-2", "text on a support / inset block", 4.5, "text"),
    ("ink-1", "surface-3", "text in the masthead and toolbars", 4.5, "text"),
    ("ink-1", "surface-selected", "text in a selected row", 4.5, "text"),
    ("ink-1", "surface-hover", "text in a hovered row", 4.5, "text"),
    ("ink-2", "surface-1", "owner attribution in a record", 4.5, "text"),
    ("ink-2", "surface-2", "owner attribution on a support block", 4.5, "text"),
    ("ink-2", "surface-selected", "secondary text, selected row", 4.5, "text"),
    ("ink-3", "surface-0", "meta text on the page", 4.5, "text"),
    ("ink-3", "surface-1", "meta text in a record", 4.5, "text"),
    ("ink-3", "surface-2", "meta text on a support block", 4.5, "text"),
    ("ink-disabled", "surface-disabled", "disabled control label", 3.0, "disabled"),
    ("accent", "surface-0", "interactive text on the page", 4.5, "text"),
    ("accent", "surface-1", "interactive text in a record", 4.5, "text"),
    ("accent", "surface-2", "interactive text on a support block", 4.5, "text"),
    ("accent", "surface-selected", "active tab label", 4.5, "text"),
    ("accent-on", "accent", "label on a filled primary button", 4.5, "text"),
    ("accent-on", "accent-hover", "label on a hovered primary button", 4.5, "text"),
    ("focus-ring", "surface-0", "focus ring against the page", 3.0, "nontext"),
    ("focus-ring", "surface-1", "focus ring against a record", 3.0, "nontext"),
    ("focus-ring", "surface-2", "focus ring against a support block", 3.0, "nontext"),
    ("focus-ring", "surface-selected", "focus ring on a selected row", 3.0, "nontext"),
    ("border-default", "surface-1", "control boundary in a record", 3.0, "nontext"),
    ("border-default", "surface-0", "control boundary on the page", 3.0, "nontext"),
    ("border-strong", "surface-1", "the authority rule", 3.0, "nontext"),
    ("disp-repair-fg", "disp-repair-bg", "REPAIR chip text", 4.5, "text"),
    ("disp-no-repair-fg", "disp-no-repair-bg", "NO_REPAIR chip text", 4.5, "text"),
    ("disp-escalate-fg", "disp-escalate-bg", "ESCALATE chip text", 4.5, "text"),
    ("disp-repair-border", "surface-1", "REPAIR chip edge on a record", 3.0, "nontext"),
    ("disp-no-repair-border", "surface-1", "NO_REPAIR chip edge on a record", 3.0, "nontext"),
    ("disp-escalate-border", "surface-1", "ESCALATE chip edge on a record", 3.0, "nontext"),
    ("disp-repair-fg", "surface-1", "REPAIR glyph outside its chip", 3.0, "nontext"),
    ("disp-no-repair-fg", "surface-1", "NO_REPAIR glyph outside its chip", 3.0, "nontext"),
    ("disp-escalate-fg", "surface-1", "ESCALATE glyph outside its chip", 3.0, "nontext"),
    ("eval-pass-fg", "surface-1", "PASS verdict text", 4.5, "text"),
    ("eval-pass-fg", "surface-2", "PASS verdict on a support block", 4.5, "text"),
    ("eval-fail-fg", "surface-1", "FAIL verdict text", 4.5, "text"),
    ("eval-fail-fg", "surface-2", "FAIL verdict on a support block", 4.5, "text"),
    ("eval-none-fg", "surface-1", "NOT_EVALUATED verdict text", 4.5, "text"),
    ("eval-none-fg", "surface-2", "NOT_EVALUATED on a support block", 4.5, "text"),
    ("eval-pass-rule", "surface-2", "PASS keyline", 3.0, "nontext"),
    ("eval-fail-rule", "surface-2", "FAIL keyline", 3.0, "nontext"),
    ("absent-fg", "absent-bg", "absence chip text", 4.5, "text"),
    ("absent-border", "surface-1", "absence chip edge", 3.0, "nontext"),
    ("absent-border", "surface-2", "absence chip edge on support block", 3.0, "nontext"),
    ("unresolved-fg", "unresolved-bg", "UNRESOLVED chip text", 4.5, "text"),
    ("unresolved-border", "surface-1", "UNRESOLVED chip edge", 3.0, "nontext"),
    ("transport-fg", "transport-bg", "transport failure text", 4.5, "text"),
    ("transport-border", "surface-1", "transport failure edge", 3.0, "nontext"),
    ("transport-hatch", "transport-bg", "hatch texture (decorative)", 1.2, "decor"),
    ("owner-system", "surface-1", "owner keyline: system", 3.0, "nontext"),
    ("owner-operator", "surface-1", "owner keyline: operator", 3.0, "nontext"),
    ("owner-validator", "surface-1", "owner keyline: validator", 3.0, "nontext"),
    ("owner-source", "surface-1", "owner keyline: source", 3.0, "nontext"),
]

DISPOSITIONS = ["repair", "no-repair", "escalate"]


def run():
    css = TOKENS.read_text()
    light, dark = parse_themes(css)
    out = []
    failures = 0
    out.append("# ADII measured contrast report\n")
    out.append("Generated by `tools/contrast.py` from `css/tokens.css`. "
               "Ratios are WCAG 2.1 relative-luminance contrast. "
               "Required: 4.5 for text below 24px, 3.0 for boundaries, "
               "glyphs and focus rings.\n")
    for theme_name, theme in (("Light", light), ("Dark", dark)):
        out.append(f"\n## {theme_name} theme\n")
        out.append("| Foreground | Background | Where it occurs | Ratio | Need | Result |")
        out.append("| --- | --- | --- | ---: | ---: | --- |")
        for fg, bg, where, need, kind in PAIRS:
            fgv, bgv = theme.get("--adii-" + fg), theme.get("--adii-" + bg)
            if not fgv or not bgv:
                out.append(f"| {fg} | {bg} | {where} | - | - | TOKEN MISSING |")
                failures += 1
                continue
            r = ratio(fgv, bgv)
            ok = r + 1e-9 >= need
            if not ok and kind != "decor":
                failures += 1
            mark = "pass" if ok else "**FAIL**"
            if kind == "decor":
                mark = "n/a (decorative)"
            out.append(f"| `{fg}` {fgv} | `{bg}` {bgv} | {where} | {r:.2f} | {need:.1f} | {mark} |")

        out.append(f"\n### {theme_name}: disposition perceptual coordinates\n")
        out.append("| Disposition | Text L* | Text C* | Chip bg L* | Chip bg C* | Text/bg ratio |")
        out.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        for d in DISPOSITIONS:
            f_, b_ = theme[f"--adii-disp-{d}-fg"], theme[f"--adii-disp-{d}-bg"]
            lf, cf = to_lab(f_)
            lb, cb = to_lab(b_)
            out.append(f"| {d.upper().replace('-', '_')} | {lf:.1f} | {cf:.1f} | "
                       f"{lb:.1f} | {cb:.1f} | {ratio(f_, b_):.2f} |")
        spread_l = max(to_lab(theme[f"--adii-disp-{d}-fg"])[0] for d in DISPOSITIONS) - \
            min(to_lab(theme[f"--adii-disp-{d}-fg"])[0] for d in DISPOSITIONS)
        spread_c = max(to_lab(theme[f"--adii-disp-{d}-fg"])[1] for d in DISPOSITIONS) - \
            min(to_lab(theme[f"--adii-disp-{d}-fg"])[1] for d in DISPOSITIONS)
        out.append(f"\nMeasured spread across the three dispositions: "
                   f"L* {spread_l:.1f}, C* {spread_c:.1f}. Lightness is held close "
                   "so that no disposition is brighter, and therefore louder, than "
                   "its peers. Chroma is not equalised as tightly, because forcing "
                   "three hues to one chroma costs contrast against the surface; the "
                   "residual chroma difference is a known imprecision.\n\n"
                   "These coordinates constrain salience. They do not prove the three "
                   "read as equally salient in a real layout, and salience is not the "
                   "mechanism the operator reads anyway. The literal text (`REPAIR`, "
                   "`NO_REPAIR`, `ESCALATE`) and the glyph are.\n")

    out.append("\n## Summary\n")
    out.append(f"- Pairs measured per theme: {len(PAIRS)}")
    out.append(f"- Failures across both themes: {failures}")
    out.append("- Not measured here: rendered antialiasing, sub-pixel text rendering "
               "and printer output. Those need a rendering engine, which was not "
               "available in the build environment.")
    text = "\n".join(out) + "\n"
    (ROOT / "CONTRAST_REPORT.md").write_text(text)
    print(text)
    return failures


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
