"""The inspector's design rules, made executable.

The stylesheet's header asserts three things: no disposition is louder than another, right
and wrong are colours only where an authority entitled to a verdict is speaking, and text
a model wrote never executes. The first stylesheet asserted the same things in a comment
and shipped a palette that broke them, plus a table whose numbers were the colour of their
own background. Prose invariants are decoration; these fail the build.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[2] / "adii" / "demo" / "web"
CSS = (WEB / "adii-ui.css").read_text(encoding="utf-8")
BLOCK = re.compile(r"([^{}]+)\{([^{}]*)\}")     # innermost rule blocks: selector, body

# Where a verdict colour may appear: adjudication by an entitled authority.
VALENCE_SCOPES = (".v-ACCEPT", ".v-REJECT", ":root")
# Where a disposition colour may appear: the disposition itself, never a success mark.
DISPOSITION_SCOPES = (".d-REPAIR", ".d-NO_REPAIR", ".d-ESCALATE", ":root")


def code(script: str) -> str:
    """The script without its block comments, which are allowed to name what they forbid."""
    return re.sub(r"/\*.*?\*/", "", (WEB / script).read_text(encoding="utf-8"), flags=re.S)


def test_every_token_used_is_declared():
    """An undeclared custom property voids the whole declaration at computed-value time,
    silently. That is how the mechanism table lost its row separators."""
    declared = set(re.findall(r"(--[a-z0-9_-]+)\s*:", CSS))
    used = set(re.findall(r"var\((--[a-z0-9_-]+)", CSS))
    assert used <= declared, f"used but never declared: {sorted(used - declared)}"


def test_no_surface_token_is_used_as_a_text_colour():
    """--bg-* is what sits behind the text. Text set in it has a contrast of 1:1."""
    hits = re.findall(r"(?<![-\w])color\s*:\s*var\((--bg-[a-z0-9_-]*)\)", CSS)
    assert not hits, f"surface token used as text colour: {hits}"


@pytest.mark.parametrize(("token", "scopes"), [("--verdict-", VALENCE_SCOPES),
                                               ("--disp-", DISPOSITION_SCOPES)])
def test_semantic_colours_stay_where_they_are_entitled(token, scopes):
    """Valence belongs to whoever may pass judgement. A disposition hue must never be spent
    as a success colour on the page that shows dispositions are not successes."""
    leaks = [sel.strip() for sel, body in BLOCK.findall(CSS)
             if token in body and not any(s in sel for s in scopes)]
    assert not leaks, f"{token}* used outside its scope in: {leaks}"


def test_the_view_layer_never_executes_what_it_renders():
    """The day a live provider runs, every string in a record is model-written, and a
    report that executes what the model wrote is inherited defect D12. Text nodes cannot
    execute; innerHTML can."""
    assert "innerHTML" not in code("app.js")


def test_a_dead_backend_is_a_rendered_state_not_a_blank_page():
    """The page starts with a fetch. Unguarded, any failure leaves nothing to read and
    nothing to click. Every fetch goes through load(), every boot through guard(), and
    guard() renders the error state."""
    text = code("app.js")
    assert text.count("fetch(") == 1, "app.js calls fetch outside load(); go through load()"
    assert "guard(" in text, "app.js boots without guard(); a failed load renders nothing"


def test_the_page_refuses_a_record_shape_it_does_not_read():
    """A reader that guesses at an unknown shape is how the archive and the page drift
    apart without anyone noticing. The schema string is pinned on both sides."""
    assert 'const SCHEMA = "adii.run_record/v1"' in code("app.js")
    assert "mismatch(" in code("app.js")
