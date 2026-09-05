"""The briefing is infrastructure, not documentation.

Claude Code auto-loads CLAUDE.md; Codex auto-loads AGENTS.md. Both must carry the same
constraints, or two agents in the same repository work to different rules. Keeping them in
sync by discipline fails the first busy week, so it is a test.
"""
from __future__ import annotations

from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
REPO = SRC.parent
BEGIN, END = "<!-- BEGIN ADII BRIEFING -->", "<!-- END ADII BRIEFING -->"


def block(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    assert BEGIN in text and END in text, f"{path.name} has lost its briefing block"
    return text.split(BEGIN, 1)[1].split(END, 1)[0].strip()


def test_both_agent_entry_points_carry_the_same_briefing():
    source = block(SRC / "docs" / "agent_briefing.md")
    assert block(REPO / "CLAUDE.md") == source, "CLAUDE.md has drifted from the briefing"
    assert block(REPO / "AGENTS.md") == source, "AGENTS.md has drifted from the briefing"


def test_the_briefing_still_states_the_boundaries():
    """A briefing that loses these has stopped doing its job."""
    source = block(SRC / "docs" / "agent_briefing.md")
    for rule in ("tool layer", "not the validator", "different program",
                 "private repository", "contracts", "author-understanding"):
        assert rule.lower() in source.lower(), f"the briefing no longer mentions {rule!r}"
