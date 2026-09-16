# 03_assets — visual material

Everything the presentation and the submission need to look at, and nothing the system
needs to run.

```text
diagrams/       architecture diagrams, decision-flow figures
screenshots/    captures of the demo and of real runs, for the final presentation
design/         HTML prototypes explored while deciding what the front door should be
identity/       the identity and design-system handoff: tokens, components, specimens,
                the logo family, and its own checks (python3 tools/check_specimen.py)
```

`design/` is history, not specification. The prototypes were how the team argued about
shape; the answer they produced lives in `02_src/adii/demo/`. Nothing imports from here,
and nothing here is tested — if a file in this folder has to be correct for the system to
work, it is in the wrong folder.

Export diagrams to PNG or SVG and commit the export, not only the source. A diagram
nobody can open without a licence is not documentation.
