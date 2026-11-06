# The paper

`paper.md` is the manuscript's only source. The PDF, the LaTeX and the arXiv bundle are built
from it, and `02_src/scripts/paper_claims.py` holds it to the evidence: every result it
reports is recomputed from the published run archives, and the check fails on any
disagreement.

```bash
python 02_src/scripts/paper_claims.py      # from the repository root
cd paper
python3 build_tex.py                       # paper.tex, the arXiv source; needs pandoc
tectonic paper.tex                         # paper.pdf; needs tectonic
cp paper.pdf permission-is-not-justification.pdf
zip paper-arxiv.zip paper.tex figures/fig1-system.png figures/fig2-admission.png
pandoc paper.md -s --css paper.css --embed-resources -o paper.html   # to read in a browser
```

`permission-is-not-justification.pdf` is a copy for reading, compiled from `paper.tex` by
tectonic. pdfLaTeX is the intended target for arXiv, and a tectonic build does not show the
source compiles there. If the PDF and `paper.md` ever differ, `paper.md` is the paper.

`figures/fig2-admission.html` is Figure 2's source, rendered at 672 × 367 at twice the pixel
density. Figure 1 is kept as rendered.

The manuscript is © the authors and is not covered by the repository's licenses.
