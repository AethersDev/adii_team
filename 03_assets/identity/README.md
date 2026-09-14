# ADII identity and design system

An identity and interface design system for ADII, an evidence-driven incident
investigation system. Self-contained: no build step, no package manager, no
network, no remote fonts.

## Transfer this as an archive, not as files

Do not download these files individually from a chat window. That path stamps
an embedded C2PA content-credential manifest into every SVG on the way out
("Claude provided this file at the request of a user…"), which rewrites
canonical brand artwork, and it depends on someone retyping the folder names by
hand. One partial copy already reached a reviewer with eight assets missing, a
mistyped `specimen` directory and freshly stamped SVGs.

Use the archive. It carries the folder names, every file, and unstamped bytes:

```
tar -xzf adii-identity.tar.gz --strip-components=1 -C 03_assets/identity
cd 03_assets/identity
sha256sum -c MANIFEST.sha256        # every file, byte for byte
python3 tools/check_specimen.py     # exits 2 if it scanned nothing
python3 tools/contrast.py
```

`MANIFEST.sha256` is the check that would have caught the bad copy immediately:
a re-stamped SVG changes its digest, and a missing file is reported as missing
rather than passing silently.

## Run

```
cd adii
python3 -m http.server 8000
```

- Investigation view: <http://localhost:8000/specimen/index.html>
- States and identity sheet: <http://localhost:8000/specimen/states.html>

`file://` also works. Theme follows the OS by default; the masthead has a theme
toggle and a density toggle.

## What to look at first

`specimen/index.html`, claim **C-1**. It is the hard case: three receipts were
supplied and retrieved, all four structural checks returned `PASS`, and both
authority and freshness are `UNRESOLVED`. All three facts stay visible at once,
the overall failure cites a backend-supplied criterion and reason, and nothing
is promoted because the evidence pile is large.

## Contents

```
adii/
├── README.md               this file
├── IDENTITY.md             three concepts, why one was chosen, asset spec
├── DESIGN_SYSTEM.md        token names, component anatomy, state meanings,
│                           copy rules, asset paths, known limitations
├── CONTRAST_REPORT.md      generated measurements
├── assets/logo/            SVG logo family, favicon, clear space, misuse
├── css/                    tokens.css → base.css → components.css
├── specimen/               index.html, states.html
└── tools/                  contrast.py, check_specimen.py
```

## Checks

```
python3 tools/contrast.py         # 55 real fg/bg pairs per theme; exit 1 on failure
python3 tools/check_specimen.py   # labels, names, ids, refs, tokens, DOM status text
```

Current status: contrast 0 failures across both themes; structural checks 0
problems; html5lib 0 HTML parse errors; tinycss2 0 CSS parse errors; no CSS
rules cancelling each other.

## Not verified

**The specimen has not been opened in a browser.** No browser was available in
the build environment and none could be installed (`cdn.playwright.dev` returns
`x-deny-reason: host_not_allowed`; Ubuntu's `chromium-browser` package is a snap
stub). Layout at real widths, text wrapping, focus ring appearance, print
output and rasterised colour are unverified. Everything above is static
analysis of the source. Open both specimens in a browser before shipping — see
"Known limitations" in DESIGN_SYSTEM.md.

## Provenance of the content

Every identifier, timestamp, digest, key name, rate and service name in the
specimens is invented for design review. Nothing describes a real system,
person or measurement. Both pages carry a banner saying so.

The logo is original artwork. No trademark search was performed; see the note
at the end of IDENTITY.md.
