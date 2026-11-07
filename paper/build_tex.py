"""paper.md -> paper.tex, the arXiv source.

    python3 build_tex.py          # writes paper.tex
    tectonic paper.tex            # paper.pdf; pdfLaTeX is the intended target for arXiv

The Markdown stays the one source. Here the title, byline and abstract become LaTeX
metadata, "[n]" citations become \\cite, the reference list becomes a thebibliography,
"Table n." and "Figure n." prefixes are left to LaTeX's own numbering.
"""
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def section(text: str, start: str, end: str | None) -> str:
    """The text after `start`, up to the first `end` that follows it."""
    a = text.index(start) + len(start)
    return text[a:text.index(end, a)] if end else text[a:]


def to_latex(markdown: str) -> str:
    return subprocess.run(["pandoc", "-f", "markdown", "-t", "latex"], input=markdown,
                          capture_output=True, encoding="utf-8", check=True).stdout.strip()


def authors(md: str) -> list[str]:
    """The byline under the title, each name in bold; a following \\* marks the author the
    corresponding-author line names."""
    byline = next(line for line in md.splitlines() if line.startswith("**"))
    email = re.search(r"^\\\*Corresponding author: <([^>]+)>$", md, re.M)[1]
    thanks = f"\\thanks{{Corresponding author: \\href{{mailto:{email}}}{{{email}}}.}}"
    return [name + (thanks if star else "")
            for name, star in re.findall(r"\*\*(.+?)\*\*(\\\*)?", byline)]


def references(text: str) -> list[tuple[str, str]]:
    """The numbered entries of the reference list. An entry wrapped over lines is one entry."""
    entries = (re.match(r"(\d+)\. (.+)", e, re.S) for e in re.split(r"\n(?=\d+\. )", text.strip()))
    return [(m[1], re.sub(r"\s*\n\s*", " ", m[2].strip())) for m in entries]


def cite(markdown: str, known: set[str]) -> str:
    """'[n]' and '[n, m]' become \\cite when every number names a reference-list entry and the
    bracket does not follow a word, so an interval or an index stays as written."""
    def one(m: re.Match) -> str:
        numbers = [n.strip() for n in m[1].split(",")]
        if not set(numbers) <= known:
            return m[0]
        return "\\cite{" + ",".join(f"r{n}" for n in numbers) + "}"
    return re.sub(r"(?<![\w\]])\[(\d+(?:,\s*\d+)*)\](?!\()", one, markdown)


def tidy(tex: str) -> str:
    """What pandoc's LaTeX needs here: LaTeX numbers captions; graphicx in older TeX Live lacks
    `alt`, whose text may hold escaped braces and groups; "et al." keeps its citation on the
    same line however pandoc wrapped it; long paths and test names may break."""
    tex = re.sub(r"\\caption\{(Table|Figure) \d+\. ", r"\\caption{", tex)
    tex = re.sub(r",alt=\{(?:\\.|\{[^{}]*\}|[^{}\\])*\}", "", tex)
    tex = re.sub(r"et al\.\s+\\cite", r"et al.~\\cite", tex)
    return re.sub(r"\\texttt\{([^{}]*)\}",
                  lambda m: "\\texttt{" + m[1].replace("\\_", "\\_\\allowbreak{}")
                  .replace("/", "/\\allowbreak{}") + "}", tex)


def main() -> None:
    md = (HERE / "paper.md").read_text(encoding="utf-8")
    title = md.splitlines()[0].removeprefix("# ").strip()
    items = references(section(md, "## References\n", "## Appendix A."))
    known = {n for n, _ in items}
    abstract = cite(section(md, "## Abstract\n", "## 1. Introduction").strip(), known)
    # the final newline matters: without it pandoc ends the abstract's paragraphs with \\
    abstract = "\\noindent " + abstract.replace("\n\n", "\n\n\\smallskip\\noindent ") + "\n"
    body = "## 1. Introduction" + section(md, "## 1. Introduction", "## References")
    appendix = "## Appendix A." + section(md, "## Appendix A.", None)

    bib = "\n".join(f"\\bibitem{{r{n}}} {to_latex(text)}" for n, text in items)
    bibliography = ("```{=latex}\n\\begin{thebibliography}{99}\n" + bib
                    + "\n\\end{thebibliography}\n```\n\n")

    source = (f"---\ntitle: {json.dumps(title)}\nauthor: {json.dumps(authors(md))}\n"
              f"abstract: {json.dumps(abstract)}\n---\n\n"
              + cite(body, known) + bibliography + "\\clearpage\n\n" + cite(appendix, known))
    tex = subprocess.run(
        ["pandoc", "-f", "markdown", "-t", "latex", "-s",
         "-V", "documentclass=article", "-V", "fontsize=11pt", "-V", "geometry:margin=1in",
         "-V", "colorlinks=true", "-V", "linkcolor=blue", "-V", "urlcolor=blue",
         "-V", "citecolor=blue", "-V", "header-includes=\\setlength{\\tabcolsep}{4pt}"],
        input=source, capture_output=True, encoding="utf-8", check=True, cwd=HERE).stdout
    (HERE / "paper.tex").write_text(tidy(tex), encoding="utf-8")


if __name__ == "__main__":
    main()
