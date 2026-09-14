#!/usr/bin/env python3
"""Static checks on the ADII specimens.

This is NOT a rendering check. It parses the HTML and CSS as text and verifies
the contract that rendering depends on: labelled controls, accessible names,
unique ids, resolvable references, defined tokens, and status words present as
real DOM text. Layout, wrapping, focus appearance, print output and colour as
actually rasterised still require a browser.

Usage: python3 tools/check_specimen.py
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECIMENS = sorted((ROOT / "specimen").glob("*.html"))
CSS_FILES = sorted((ROOT / "css").glob("*.css"))

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr", "use", "rect", "path"}
CONTROLS = {"input", "select", "textarea"}
NO_LABEL_NEEDED = {"hidden", "submit", "reset", "button"}

# Status words that must exist as real text nodes, not as CSS content.
REQUIRED_TEXT = [
    "UNRESOLVED", "PASS", "FAIL", "NOT_EVALUATED", "not supplied",
    "not evaluated", "pending", "failed to retrieve",
    "REPAIR", "NO_REPAIR", "ESCALATE",
]


class Doc(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids = []
        self.controls = []      # (tag, attrs, inside_label, lineno)
        self.labels_for = []
        self.imgs = []
        self.svgs = []
        self.uses = []
        self.symbols = []
        self.headings = []
        self.text = []
        self.hrefs = []
        self.srcs = []
        self.in_label = 0
        self.legend_ok = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag not in VOID:
            self.stack.append(tag)
        if "id" in a:
            self.ids.append((a["id"], self.getpos()[0]))
        if tag == "label":
            self.in_label += 1
            if "for" in a:
                self.labels_for.append(a["for"])
        if tag in CONTROLS:
            self.controls.append((tag, a, self.in_label > 0, self.getpos()[0]))
        if tag == "img":
            self.imgs.append((a, self.getpos()[0]))
        if tag == "svg":
            self.svgs.append((a, self.getpos()[0]))
        if tag == "use" and "href" in a:
            self.uses.append(a["href"])
        if tag == "symbol" and "id" in a:
            self.symbols.append(a["id"])
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append((int(tag[1]), self.getpos()[0]))
        if tag == "a" and "href" in a:
            self.hrefs.append(a["href"])
        if "src" in a:
            self.srcs.append(a["src"])
        if tag == "link" and a.get("href"):
            self.srcs.append(a["href"])

    def handle_endtag(self, tag):
        if tag == "label" and self.in_label:
            self.in_label -= 1
        if self.stack and tag in self.stack:
            while self.stack:
                if self.stack.pop() == tag:
                    break

    def handle_data(self, data):
        if data.strip():
            self.text.append(data)


def check_html(path, problems, notes):
    src = path.read_text()
    d = Doc()
    d.feed(src)
    rel = path.relative_to(ROOT)

    # 1. lang / title / viewport
    if not re.search(r"<html[^>]+lang=", src):
        problems.append(f"{rel}: <html> has no lang attribute")
    if "<title>" not in src:
        problems.append(f"{rel}: no <title>")
    if 'name="viewport"' not in src:
        problems.append(f"{rel}: no viewport meta")

    # 2. unique ids
    seen = {}
    for i, line in d.ids:
        if i in seen:
            problems.append(f"{rel}: duplicate id '{i}' (lines {seen[i]}, {line})")
        seen[i] = line

    # 3. every control labelled
    for tag, a, wrapped, line in d.controls:
        if tag == "input" and a.get("type", "text").lower() in NO_LABEL_NEEDED:
            continue
        has = (
            a.get("id") in d.labels_for
            or "aria-label" in a
            or "aria-labelledby" in a
            or wrapped
        )
        if not has:
            problems.append(f"{rel}:{line}: <{tag}> has no label")

    # 4. images and informative svg have accessible names
    for a, line in d.imgs:
        if "alt" not in a:
            problems.append(f"{rel}:{line}: <img> without alt")
    for a, line in d.svgs:
        role = a.get("role")
        if role == "img" and not (a.get("aria-label") or a.get("aria-labelledby")):
            if "<title" not in src:
                problems.append(f"{rel}:{line}: <svg role=img> without accessible name")
        if role != "img" and "aria-hidden" not in a and "class" in a and \
                "visually-hidden" not in a.get("class", ""):
            notes.append(f"{rel}:{line}: decorative <svg> without aria-hidden")

    # 5. <use> targets exist in the same document
    for href in d.uses:
        if href.startswith("#") and href[1:] not in d.symbols:
            problems.append(f"{rel}: <use> references missing symbol {href}")

    # 6. heading order: no level skipped
    prev = 0
    for lvl, line in d.headings:
        if prev and lvl > prev + 1:
            problems.append(f"{rel}:{line}: heading jumps h{prev} to h{lvl}")
        prev = lvl
    if not d.headings or d.headings[0][0] != 1:
        notes.append(f"{rel}: first heading is not h1")

    # 7. referenced local files exist
    for ref in d.srcs + [h for h in d.hrefs if not h.startswith("#")]:
        if ref.startswith(("http:", "https:", "data:", "mailto:")):
            problems.append(f"{rel}: remote reference {ref} (offline specimen)")
            continue
        target = (path.parent / ref).resolve()
        if not target.exists():
            problems.append(f"{rel}: missing referenced file {ref}")

    # 8. status words present as real text
    joined = " ".join(d.text)
    for word in REQUIRED_TEXT:
        if word in src and word not in joined:
            problems.append(f"{rel}: '{word}' appears in source but not as DOM text")

    # 9. no fabricated-live-data smell: banner must be present
    if "Invented demonstration data" not in joined:
        problems.append(f"{rel}: no provenance banner naming the data as invented")
    # Rule 10 wants the marker as well as the banner: the banner is for the
    # reader, data-example is what a later tool can grep for before anything
    # in this tree is mistaken for a real record.
    if 'data-example="invented"' not in src:
        problems.append(f"{rel}: no data-example=\"invented\" marker on any section "
                        f"(the provenance banner alone is not machine-readable)")

    return d


def check_css(problems, notes):
    tokens_src = (ROOT / "css" / "tokens.css").read_text()
    defined = set(re.findall(r"(--adii-[a-z0-9-]+)\s*:", tokens_src))
    used = set()
    for f in CSS_FILES + SPECIMENS:
        used |= set(re.findall(r"var\((--adii-[a-z0-9-]+)", f.read_text()))
    # locally-scoped custom properties declared outside tokens.css
    local = set()
    for f in CSS_FILES:
        local |= set(re.findall(r"(--adii-[a-z0-9-]+)\s*:", f.read_text()))
    for u in sorted(used - defined - local):
        problems.append(f"css: var({u}) used but never defined")

    comp = (ROOT / "css" / "components.css").read_text()
    if re.search(r"text-transform\s*:\s*uppercase", comp + tokens_src):
        problems.append("css: text-transform:uppercase found - status text must be "
                        "literal in the DOM, not produced by CSS")
    for m in re.finditer(r"content\s*:\s*\"([^\"]{3,})\"", comp):
        if m.group(1).strip():
            problems.append(f"css: pseudo-element content '{m.group(1)}' may carry "
                            "meaning that will not copy or print")
    if "prefers-reduced-motion" not in (ROOT / "css" / "base.css").read_text():
        problems.append("css: no reduced-motion handling in base.css")
    if "@media print" not in (ROOT / "css" / "base.css").read_text():
        problems.append("css: no print treatment in base.css")
    # alpha colours defeat contrast measurement
    for f in CSS_FILES:
        for m in re.finditer(r"rgba?\([^)]*?,\s*0?\.\d+\s*\)", f.read_text()):
            notes.append(f"{f.name}: alpha colour {m.group(0)} is not measurable")

    # Logo artwork must stay clean. An export pipeline silently injected ~8 KB
    # of C2PA manifest into every SVG once; these are canonical brand files and
    # should carry nothing but geometry and an accessible title.
    for f in sorted((ROOT / "assets").rglob("*.svg")):
        src = f.read_text()
        rel = f.relative_to(ROOT)
        if "<metadata" in src or "c2pa" in src.lower():
            problems.append(f"{rel}: embedded metadata in canonical artwork "
                            f"({len(src)} bytes) - strip it")
        if "<title" not in src:
            problems.append(f"{rel}: no <title> for an accessible name")


def main():
    problems, notes = [], []

    # A checker that finds no input must fail, not pass quietly. Zero files
    # scanned is the failure mode that produces a green result on a broken or
    # renamed tree, which is worse than any defect it could have found.
    if not SPECIMENS:
        print(f"FATAL: no specimens found in {ROOT / 'specimen'}")
        print("Nothing was checked. This is a failure, not a pass.")
        return 2
    if not CSS_FILES:
        print(f"FATAL: no stylesheets found in {ROOT / 'css'}")
        print("Nothing was checked. This is a failure, not a pass.")
        return 2

    for p in SPECIMENS:
        check_html(p, problems, notes)
    check_css(problems, notes)

    print(f"Specimens checked: {', '.join(p.name for p in SPECIMENS)}")
    print(f"CSS checked: {', '.join(f.name for f in CSS_FILES)}")
    print()
    if notes:
        print("Notes:")
        for n in notes:
            print("  -", n)
        print()
    if problems:
        print(f"PROBLEMS ({len(problems)}):")
        for p in problems:
            print("  -", p)
        return 1
    print("No structural problems found.")
    print("Not covered by this tool: layout, wrapping, focus appearance, colour as "
          "rasterised, print output, and anything requiring a browser.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
