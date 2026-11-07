"""paper/build_tex.py turns the manuscript into the arXiv source, and each way it can quietly
go wrong is shown failing.

The parsing is tested on its own, without pandoc. The build is then run whole, on the real
manuscript and on a small one written to trip every case, wherever pandoc is installed.
"""
from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PAPER = Path(__file__).resolve().parents[3] / "paper"
spec = importlib.util.spec_from_file_location("build_tex", PAPER / "build_tex.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def test_a_bracketed_number_is_a_citation_only_when_it_names_a_reference():
    text = "an interval [0, 1], an index `rows[3]`, a link [3](x), and see [3] and [2, 3]."
    assert build.cite(text, {"2", "3"}) == (
        "an interval [0, 1], an index `rows[3]`, a link [3](x), and see \\cite{r3} and "
        "\\cite{r2,r3}.")


def test_a_section_ends_at_the_first_marker_after_its_start():
    text = "## Appendix A. named early\n## References\n1. One.\n## Appendix A.\nlater"
    assert build.section(text, "## References\n", "## Appendix A.") == "1. One.\n"
    with pytest.raises(ValueError):
        build.section("## References\n1. One.\n", "## References\n", "## Appendix A.")


def test_a_wrapped_reference_is_one_entry():
    text = "\n1. A. Author. A title that\n   wraps onto a second line.\n2. B. Author. Short.\n\n"
    assert build.references(text) == [("1", "A. Author. A title that wraps onto a second line."),
                                      ("2", "B. Author. Short.")]


def test_the_byline_is_read_from_the_manuscript():
    md = "# T\n\n**Ann One**, **Bo Two**\\*\n\n\\*Corresponding author: <bo@example.org>\n"
    assert build.authors(md) == [
        "Ann One",
        "Bo Two\\thanks{Corresponding author: \\href{mailto:bo@example.org}{bo@example.org}.}"]


def test_pandocs_output_is_tidied_whatever_its_braces_and_line_breaks():
    assert build.tidy("\\includegraphics[keepaspectratio,alt={A \\{b\\} c\\_d "
                      "\\textbf{e} f}]{x.png}") == "\\includegraphics[keepaspectratio]{x.png}"
    assert build.tidy("as Yu et al.\n\\cite{r13} found") == "as Yu et al.~\\cite{r13} found"
    assert build.tidy("\\caption{Table 2. The packs.}") == "\\caption{The packs.}"


def built(folder: Path, md: str | None = None) -> str:
    """paper.tex from a copy of the build script, over the real manuscript or the one given."""
    if shutil.which("pandoc") is None:
        pytest.skip("pandoc is not installed; the build runs through it")
    shutil.copy(PAPER / "build_tex.py", folder / "build_tex.py")
    if md is None:
        shutil.copy(PAPER / "paper.md", folder / "paper.md")
    else:
        (folder / "paper.md").write_text(md, encoding="utf-8")
    subprocess.run([sys.executable, "-B", "build_tex.py"], cwd=folder, check=True,
                   capture_output=True, timeout=50)
    return (folder / "paper.tex").read_text(encoding="utf-8")


def abstract(tex: str) -> str:
    return tex[tex.index("\\begin{abstract}"):tex.index("\\end{abstract}")]


def flat(tex: str) -> str:
    """pandoc wraps its output at 72 columns, so a phrase is looked for across line breaks."""
    return " ".join(tex.split())


def test_the_manuscript_builds_with_every_citation_resolved_and_a_clean_abstract(tmp_path):
    tex = built(tmp_path)
    md = (PAPER / "paper.md").read_text(encoding="utf-8")
    assert not re.search(r"\\\\$", abstract(tex), re.M), "a paragraph of the abstract ends in \\\\"
    for name in build.authors(md):
        assert name.split("\\thanks")[0] in flat(tex)
    email = re.search(r"Corresponding author: <([^>]+)>", md)[1]
    assert f"\\href{{mailto:{email}}}" in flat(tex)
    entries = build.references(build.section(md, "## References\n", "## Appendix A."))
    bibitems = re.findall(r"\\bibitem\{(r\d+)\}", tex)
    assert bibitems == [f"r{n}" for n, _ in entries]
    cited = {key for group in re.findall(r"\\cite\{([^}]*)\}", tex) for key in group.split(",")}
    assert cited and cited <= set(bibitems)
    assert ",alt=" not in tex and not re.search(r"et al\.\s+\\cite", tex)


def test_a_manuscript_made_to_trip_the_build_comes_out_right(tmp_path):
    md = ("# A Title\n\n**Ann One**\\*, **Bo Two**\n\n"
          "\\*Corresponding author: <ann@example.org>\n\n"
          "## Abstract\n\nFirst paragraph cites [1].\n\nSecond paragraph.\n\n"
          "## 1. Introduction\n\nThe interval [0, 1] and `rows[1]` are not citations. As "
          "Doe et al. [2] found, and [1, 2] agree.\n\n![A caption with {braces}.](fig.png)\n\n"
          "## References\n\n1. A. Doe. A title that\n   wraps onto a second line.\n"
          "2. B. Roe. Another.\n\n## Appendix A. Extra\n\nMore, as in [2].\n")
    tex = built(tmp_path, md)
    assert "\\cite{r1}" in abstract(tex)
    assert not re.search(r"\\\\$", abstract(tex), re.M)
    assert "{[}0, 1{]}" in flat(tex) and "\\cite{r0" not in tex
    assert "\\bibitem{r1} A. Doe. A title that wraps onto a second line." in flat(tex)
    assert re.findall(r"\\bibitem\{(r\d+)\}", tex) == ["r1", "r2"]
    assert "et al.~\\cite{r2}" in flat(tex) and "\\cite{r1,r2}" in tex
    assert "Ann One\\thanks{Corresponding author: \\href{mailto:ann@example.org}" in flat(tex)
    assert ",alt=" not in tex
