# The paper

`paper.md` is the manuscript's only source. The PDF, the LaTeX and the arXiv bundle are built
from it, and `02_src/scripts/paper_claims.py` holds it to the evidence: every result it
reports is recomputed from the published run archives, and the check fails on any
disagreement.

```bash
python 02_src/scripts/paper_claims.py      # from the repository root
cd paper
python3 build_tex.py                       # paper.tex, the arXiv source; needs pandoc
pandoc paper.md -s --css paper.css --embed-resources -o paper.html   # then print it to PDF
```

`permission-is-not-justification.pdf` is a copy for reading, built from `paper.md` with
`build_tex.py`; if the two ever differ, `paper.md` is the paper.

`figures/fig2-admission.html` is Figure 2's source, rendered at 672 × 367 at twice the pixel
density. Figure 1 is kept as rendered.

The manuscript is © the authors and is not covered by the repository's licenses.
