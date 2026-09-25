# 03_assets — images and visuals

```text
identity/assets/   the logo family, as SVG: lockups, symbol, wordmark, app icon, favicon,
                   and the clear-space and misuse sheets
diagrams/          architecture and decision-flow figures
screenshots/       the page and real runs
```

Nothing in `02_src/` imports from here: the page serves its own copy of the logo, held
byte-identical to `identity/assets/logo/` by a test.
