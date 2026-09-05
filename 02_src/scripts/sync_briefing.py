"""Regenerate CLAUDE.md and AGENTS.md from docs/agent_briefing.md.

    python 02_src/scripts/sync_briefing.py

Claude Code auto-loads CLAUDE.md and Codex auto-loads AGENTS.md, so both must carry the
same constraints. One source of truth, mechanically copied, verified by a test.
"""
from __future__ import annotations

from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
REPO = SRC.parent
BEGIN, END = "<!-- BEGIN ADII BRIEFING -->", "<!-- END ADII BRIEFING -->"


def main() -> int:
    source = (SRC / "docs" / "agent_briefing.md").read_text(encoding="utf-8")
    briefing = BEGIN + source.split(BEGIN, 1)[1].split(END, 1)[0] + END
    changed = []
    for name in ("CLAUDE.md", "AGENTS.md"):
        path = REPO / name
        text = path.read_text(encoding="utf-8")
        head, rest = text.split(BEGIN, 1)
        updated = head + briefing + rest.split(END, 1)[1]
        if updated != text:
            path.write_text(updated, encoding="utf-8", newline="\n")
            changed.append(name)
    print(f"synced: {', '.join(changed)}" if changed else "already in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
