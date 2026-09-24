"""The front door's design rules, made executable (final plan, decisions F1–F3 and W).

The page draws its own stylesheet but not its own mark: the logo is the identity handoff's,
copied by 02_src/scripts/sync_identity.py. The rules below are the ones prose would let
drift: text a model wrote never executes, nothing is fetched from anywhere but this server
(the page runs offline on a stage), the fonts travel with their licence, the logo is the
handoff's byte for byte, and the page reads only the record shapes it knows.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / "02_src" / "adii" / "demo" / "web"
LOGO = ROOT / "03_assets" / "identity" / "assets" / "logo"
SCRIPTS = ("app.js", "view.js")
CSS = (WEB / "front-door.css").read_text(encoding="utf-8")

# Every way a browser turns a string into markup or code. Text nodes are the only door.
EXECUTES = ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "srcdoc",
            "eval(", "new Function", "createContextualFragment", "DOMParser")


def code(script: str) -> str:
    """The script without its block comments, which are allowed to name what they forbid."""
    return re.sub(r"/\*.*?\*/", "", (WEB / script).read_text(encoding="utf-8"), flags=re.S)


@pytest.mark.parametrize("name", ["adii-lockup-horizontal.svg", "adii-symbol.svg",
                                  "adii-wordmark.svg", "favicon.svg"])
def test_the_mark_is_the_handoffs_byte_for_byte(name):
    """The logo does not change (decision W): the page serves a copy that may not drift by a
    byte — run python 02_src/scripts/sync_identity.py after a new delivery."""
    assert (WEB / "logo" / name).read_bytes() == (LOGO / name).read_bytes(), (
        f"{name} differs from the identity handoff; run 02_src/scripts/sync_identity.py")


def test_the_view_layer_never_executes_what_it_renders():
    """The day a live provider runs, every string in a record is model-written, and a page
    that executes what the model wrote is inherited defect D12. Text nodes cannot execute;
    every name in EXECUTES can."""
    for name in SCRIPTS:
        used = [door for door in EXECUTES if door in code(name)]
        assert not used, f"{name} turns strings into markup or code with {used}"


def test_the_page_fetches_nothing_from_anywhere_else():
    """On a stage the network is the venue's. Fonts, logo, scripts and styles are served by
    this server; the one absolute URL allowed is SVG's namespace, which is never fetched."""
    for path in WEB.rglob("*"):
        if path.suffix in (".js", ".css", ".html"):
            text = path.read_text(encoding="utf-8").replace("http://www.w3.org/2000/svg", "")
            assert not re.search(r"https?://|//fonts\.|@import", text), f"{path.name} fetches out"


def test_every_font_is_served_here_under_its_licence():
    used = set(re.findall(r'url\("fonts/([^"]+)"\)', CSS))
    assert used and all((WEB / "fonts" / f).is_file() for f in used)
    assert sorted(p.name for p in (WEB / "fonts").glob("*.woff2")) == sorted(used)
    licence = (WEB / "fonts" / "OFL.txt").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE Version 1.1" in licence
    assert all(name in licence for name in ("Newsreader", "Public Sans", "IBM Plex Mono"))


def test_every_colour_the_page_spends_is_declared_once():
    declared = re.findall(r"(--[a-z0-9-]+)\s*:", CSS)
    used = set(re.findall(r"var\((--[a-z0-9-]+)\)", CSS))
    assert len(declared) == len(set(declared)), "a token declared twice"
    assert used <= set(declared), f"used but never declared: {sorted(used - set(declared))}"


def test_the_page_refuses_a_record_shape_it_does_not_read():
    """A reader that guesses at an unknown shape is how the archive and the page drift apart
    without anyone noticing. The schema strings are pinned here and in reporting/record.py."""
    assert ('const SCHEMAS = ["adii.run_record/v3", "adii.run_record/v2", '
            '"adii.run_record/v1"]') in code("app.js")
    assert "a shape this page does not read" in code("app.js")


def test_what_the_page_says_about_a_run_is_projected_in_one_place():
    """view.js holds every projection from a record to words and numbers, and fetches
    nothing; app.js draws what it returns. A verdict phrase written in app.js is one the
    projection tests never saw."""
    assert "fetch(" not in code("view.js")
    for phrase in ("Yes. Fix it.", "No. Leave it.", "Not yet. Escalate it.",
                   "Stopped at the spending cap."):
        assert phrase in code("view.js") and phrase not in code("app.js"), phrase
