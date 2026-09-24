# 03_assets — visual material

Everything the presentation and the submission need to look at, and nothing the system
needs to run.

```text
diagrams/       architecture diagrams, decision-flow figures
screenshots/    captures of the inspector and of real runs, for the final presentation
identity/       the identity and design-system handoff: tokens, components, specimens,
                the logo family, and its own checks (python3 tools/check_specimen.py)
```

Nothing in `02_src/` imports from here. The front door serves a *copy* of the logo from `identity/assets/logo/`,
made by `python 02_src/scripts/sync_identity.py` and held byte-identical by a test — so the
handoff stays exactly as delivered and the system needs nothing from this folder to run.
If a file in this folder had to be correct for the system to work, it would be in the
wrong folder.

Export diagrams to PNG or SVG and commit the export, not only the source. A diagram
nobody can open without a licence is not documentation.
