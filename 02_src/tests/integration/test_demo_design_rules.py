"""The inspector's design rules, made executable.

The stylesheet is the identity handoff's (03_assets/identity), copied into the inspector
by 02_src/scripts/sync_identity.py, plus one page-specific file. The rules the handoff
asserts in prose — no disposition is louder than another, right and wrong are colours only
where an authority entitled to a verdict is speaking, absence is achromatic, text a model
wrote never executes — fail the build here. Prose invariants are decoration; these are not.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / "02_src" / "adii" / "demo" / "web"
HANDOFF = ROOT / "03_assets" / "identity" / "css"
SYNCED = ("tokens.css", "base.css", "components.css")
SHEETS = (*SYNCED, "inspector.css")
CSS = "\n".join((WEB / sheet).read_text(encoding="utf-8") for sheet in SHEETS)
BLOCK = re.compile(r"([^{}]+)\{([^{}]*)\}")     # innermost rule blocks: selector, body

# Where a verdict colour may appear: the validator's check rows, the diff gutter (which
# describes a change rather than judging it), and the token definitions themselves.
VALENCE_SCOPES = (".adii-check", ".adii-diff__line", ":root")
# Where a disposition colour may appear: the disposition chip itself, never a success mark.
DISPOSITION_SCOPES = (".adii-chip--repair", ".adii-chip--no-repair", ".adii-chip--escalate",
                      ":root")

# Every way a browser turns a string into markup or code. Text nodes are the only door.
EXECUTES = ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "srcdoc",
            "eval(", "new Function", "createContextualFragment")


SCRIPTS = ("app.js", "phrasing.js")


def code(script: str) -> str:
    """The script without its block comments, which are allowed to name what they forbid."""
    return re.sub(r"/\*.*?\*/", "", (WEB / script).read_text(encoding="utf-8"), flags=re.S)


@pytest.mark.parametrize("sheet", SYNCED)
def test_the_inspector_stylesheet_is_the_handoff_byte_for_byte(sheet):
    """One source of truth: the handoff. The inspector runs on a copy, and the copy may not
    drift by a byte — run python 02_src/scripts/sync_identity.py after a new delivery."""
    assert (WEB / sheet).read_bytes() == (HANDOFF / sheet).read_bytes(), (
        f"{sheet} differs from 03_assets/identity/css; run 02_src/scripts/sync_identity.py")


def test_every_token_used_is_declared():
    """An undeclared custom property voids the whole declaration at computed-value time,
    silently. The page-specific sheet may only spend tokens the handoff declares."""
    declared = set(re.findall(r"(--adii-[a-z0-9_-]+)\s*:", CSS))
    used = set(re.findall(r"var\((--adii-[a-z0-9_-]+)", CSS))
    assert used <= declared, f"used but never declared: {sorted(used - declared)}"
    assert not re.findall(r"var\((--(?!adii-)[a-z0-9_-]+)", CSS), "a token outside the system"


def test_no_surface_token_is_used_as_a_text_colour():
    """--adii-surface-* is what sits behind the text. Text set in it has a contrast of 1:1."""
    hits = re.findall(r"(?<![-\w])color\s*:\s*var\((--adii-surface-[a-z0-9_-]*)\)", CSS)
    assert not hits, f"surface token used as text colour: {hits}"


@pytest.mark.parametrize(("token", "scopes"), [("--adii-eval-", VALENCE_SCOPES),
                                               ("--adii-disp-", DISPOSITION_SCOPES)])
def test_semantic_colours_stay_where_they_are_entitled(token, scopes):
    """Valence belongs to whoever may pass judgement. A disposition hue must never be spent
    as a success colour on the page that shows dispositions are not successes."""
    leaks = [sel.strip() for sel, body in BLOCK.findall(CSS)
             if token in body and not any(s in sel for s in scopes)]
    assert not leaks, f"{token}* used outside its scope in: {leaks}"


def test_the_page_specific_sheet_introduces_no_colour():
    """inspector.css adds layout. A colour literal there would be a fourth device."""
    own = (WEB / "inspector.css").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgb\(|hsl\(|oklch\(", own), "a colour literal"


def test_the_view_layer_never_executes_what_it_renders():
    """The day a live provider runs, every string in a record is model-written, and a
    report that executes what the model wrote is inherited defect D12. Text nodes cannot
    execute; every name in EXECUTES can."""
    for name in SCRIPTS:
        used = [door for door in EXECUTES if door in code(name)]
        assert not used, f"{name} turns strings into markup or code with {used}"


def test_a_dead_backend_is_a_rendered_state_not_a_blank_page():
    """The page starts with a fetch. Unguarded, any failure leaves nothing to read and
    nothing to click. Every fetch goes through load(), every boot through guard(), and
    guard() renders the transport-failure state."""
    text = code("app.js")
    assert text.count("fetch(") == 1, "app.js calls fetch outside load(); go through load()"
    assert "fetch(" not in code("phrasing.js"), "phrasing.js is a dictionary; it fetches nothing"
    assert "guard(" in text, "app.js boots without guard(); a failed load renders nothing"
    assert "adii-transport" in text, "a dead backend must render as a retrieval failure"


def test_the_page_refuses_a_record_shape_it_does_not_read():
    """A reader that guesses at an unknown shape is how the archive and the page drift
    apart without anyone noticing. The schema string is pinned on both sides."""
    assert 'const SCHEMA = "adii.run_record/v1"' in code("app.js")
    assert "mismatch(" in code("app.js")


def test_absence_and_endings_are_achromatic_and_verdicts_are_the_validators():
    """How a run ended is the loop's report, not anyone's verdict; what is absent is not a
    verdict either. Only the validator's row may carry pass or fail."""
    script = code("app.js")
    assert "adii-state" in script and "g-unresolved" in script
    assert script.count("adii-check--") == 1, "verdict rows outside the validator's record"


def test_every_sentence_the_page_adds_comes_from_the_dictionary():
    """app.js may quote the record and lay it out. The sentences it adds — how a run ended,
    what a step did, what ADII is — come from phrasing.js, one reviewable place. A prose
    sentence assembled in app.js is a sentence the team never saw in the dictionary."""
    script = code("app.js")
    for key in ("PHRASING.ended", "PHRASING.step", "PHRASING.outcome", "PHRASING.product",
                "PHRASING.validation", "PHRASING.disposition"):
        assert key in script, f"app.js does not read {key}"
    assert "The investigator reached" not in script and "The model failed" not in script, (
        "an ending sentence is written in app.js instead of phrasing.js")
