"""paper.md -> paper.tex, the arXiv source.

    python3 build_tex.py          # writes paper.tex
    tectonic paper.tex            # optional check; arXiv compiles it with pdfLaTeX

The Markdown stays the one source. Here the title, byline and abstract become LaTeX
metadata, "[n]" citations become \\cite, the reference list becomes a thebibliography,
"Table n." and "Figure n." prefixes are left to LaTeX's own numbering, and the
pre-publication note is dropped.
"""
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUTHORS = ["Malek Alhazmi\\thanks{Corresponding author.}", "Joorie Alsakran",
           "Ibrahem Altowalah", "Nasser Alzaid"]


def section(text: str, start: str, end: str | None) -> str:
    a = text.index(start) + len(start)
    return text[a:text.index(end)] if end else text[a:]


def to_latex(markdown: str) -> str:
    return subprocess.run(["pandoc", "-f", "markdown", "-t", "latex"], input=markdown,
                          capture_output=True, text=True, check=True).stdout.strip()


def cite(markdown: str) -> str:
    return re.sub(r"\[(\d+(?:,\s*\d+)*)\](?!\()",
                  lambda m: "\\cite{" + ",".join(f"r{n.strip()}" for n in m[1].split(",")) + "}",
                  markdown)


def main() -> None:
    md = (HERE / "paper.md").read_text(encoding="utf-8")
    title = md.splitlines()[0].removeprefix("# ").strip()
    abstract = section(md, "## Abstract\n", "## 1. Introduction").strip()
    abstract = "\\noindent " + abstract.replace("\n\n", "\n\n\\smallskip\\noindent ")
    body = "## 1. Introduction" + section(md, "## 1. Introduction", "## References")
    body = re.sub(r"\n\[Before submission:[^\]]*\]\n", "\n", body)
    refs = section(md, "## References\n", "## Appendix A.")
    appendix = "## Appendix A." + section(md, "## Appendix A.", None)

    items = re.findall(r"^(\d+)\. (.+)$", refs, flags=re.M)
    bib = "\n".join(f"\\bibitem{{r{n}}} {to_latex(text)}" for n, text in items)
    bibliography = ("```{=latex}\n\\begin{thebibliography}{99}\n" + bib
                    + "\n\\end{thebibliography}\n```\n\n")

    source = (f"---\ntitle: {json.dumps(title)}\nauthor: {json.dumps(AUTHORS)}\n"
              f"abstract: {json.dumps(abstract)}\n---\n\n"
              + cite(body) + bibliography + "\\clearpage\n\n" + cite(appendix))
    tex = subprocess.run(
        ["pandoc", "-f", "markdown", "-t", "latex", "-s",
         "-V", "documentclass=article", "-V", "fontsize=11pt", "-V", "geometry:margin=1in",
         "-V", "colorlinks=true", "-V", "linkcolor=blue", "-V", "urlcolor=blue",
         "-V", "citecolor=blue", "-V", "header-includes=\\setlength{\\tabcolsep}{4pt}"],
        input=source, capture_output=True, text=True, check=True, cwd=HERE).stdout
    tex = re.sub(r"\\caption\{(Table|Figure) \d+\. ", r"\\caption{", tex)
    tex = re.sub(r",alt=\{[^}]*\}", "", tex)       # graphicx in older TeX Live lacks `alt`
    tex = tex.replace("et al. \\cite", "et al.~\\cite")
    tex = re.sub(r"\\texttt\{([^{}]*)\}",          # long paths and test names may break
                 lambda m: "\\texttt{" + m[1].replace("\\_", "\\_\\allowbreak{}")
                 .replace("/", "/\\allowbreak{}") + "}", tex)
    (HERE / "paper.tex").write_text(tex, encoding="utf-8")


if __name__ == "__main__":
    main()
